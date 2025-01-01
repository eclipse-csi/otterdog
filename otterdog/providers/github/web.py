#  *******************************************************************************
#  Copyright (c) 2023-2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import re
from asyncio import gather
from contextlib import asynccontextmanager
from functools import cached_property
from typing import TYPE_CHECKING

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, async_playwright

from otterdog.logging import get_logger, is_debug_enabled
from otterdog.utils import unwrap

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

    from otterdog.credentials import Credentials

_logger = get_logger(__name__)


class WebClient:
    # use 10s as default timeout
    _DEFAULT_TIMEOUT = 10000

    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    @cached_property
    def web_settings_definition(self) -> dict[str, Any]:
        from importlib_resources import files

        from otterdog import resources
        from otterdog.utils import jsonnet_evaluate_file

        # load the definition file which describes how the web settings
        # can be retrieved / modified.
        _logger.trace("getting web_settings config using jsonnet")

        web_settings_config = files(resources).joinpath("github-web-settings.jsonnet")
        return jsonnet_evaluate_file(str(web_settings_config))

    async def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        _logger.debug("retrieving settings via web interface")

        async with async_playwright() as playwright:
            try:
                browser = await playwright.firefox.launch()
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            context = await browser.new_context()

            login_page = await context.new_page()
            login_page.set_default_timeout(self._DEFAULT_TIMEOUT)
            await self._login_if_required(login_page)

            async def process_page(page_url, page_def) -> dict[str, Any]:
                page = await context.new_page()
                page.set_default_timeout(self._DEFAULT_TIMEOUT)
                return await self._retrieve_settings(org_id, page_url, page_def, included_keys, page)

            tasks = [process_page(page_url, page_def) for page_url, page_def in self._get_pages(included_keys)]
            settings_list = await gather(*tasks)
            settings = {k: v for d in settings_list for k, v in d.items()}

            await self._logout(login_page)

            await login_page.close()
            await context.close()
            await browser.close()

            return settings

    def _get_pages(self, included_keys: set[str]) -> Iterator[tuple[str, Any]]:
        for page_url, page_def in self.web_settings_definition.items():
            # check if the page contains any setting that is requested
            if not any(x in included_keys for x in [x["name"] for x in page_def]):
                continue
            else:
                yield page_url, page_def

    @staticmethod
    async def _retrieve_settings(
        org_id: str, page_url: str, page_def: Any, included_keys: set[str], page: Page
    ) -> dict[str, Any]:
        settings: dict[str, Any] = {}

        _logger.trace("loading page '%s'", page_url)
        response = await page.goto(f"https://github.com/organizations/{org_id}/{page_url}")
        response = unwrap(response)
        if not response.ok:
            raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

        for setting_def in page_def:
            setting = setting_def["name"]
            optional = setting_def["optional"]
            _logger.trace("checking setting '%s'", setting)

            if setting not in included_keys:
                continue

            parent = setting_def.get("parent", None)
            if parent is not None:
                parent_value = settings[parent]
                if isinstance(parent_value, bool) and parent_value is False:
                    settings[setting] = None
                    continue

            try:
                setting_type = setting_def["type"]
                match setting_type:
                    case "checkbox":
                        selector = setting_def["selector"]

                    case "radio":
                        selector = f"{setting_def['selector']}:checked"

                    case "select-menu":
                        selector = f"{setting_def['selector']}"

                    case "text":
                        selector = setting_def["selector"]

                    case _:
                        raise RuntimeError(f"not supported setting type '{setting_type}'")

                pre_selector = setting_def["preSelector"]
                if pre_selector is not None:
                    await page.click(pre_selector)
                    await page.wait_for_selector(selector, state="attached")

                value = await page.eval_on_selector(
                    selector,
                    "(el, property) => el[property]",
                    setting_def["valueSelector"],
                )

                if isinstance(value, str):
                    value = value.strip()

                settings[setting] = value
                _logger.trace("retrieved setting for '%s' = '%s'", setting, value)

            except Exception as e:
                if optional:
                    continue

                if is_debug_enabled():
                    page_name = page_url.split("/")[-1]
                    screenshot_file = f"screenshot_{page_name}.png"
                    await page.screenshot(path=screenshot_file)
                    _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

                _logger.warning(f"failed to retrieve setting '{setting}' via web ui:\n{e!s}")

        return settings

    async def update_org_settings(self, org_id: str, data: dict[str, Any]) -> None:
        _logger.debug("updating settings via web interface")

        async with async_playwright() as playwright:
            try:
                browser = await playwright.firefox.launch()
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            page = await browser.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            await self._login_if_required(page)
            await self._update_settings(org_id, data, page)
            await self._logout(page)

            await page.close()
            await browser.close()

            _logger.debug(f"updated {len(data)} setting(s) via web interface")

    async def _update_settings(self, org_id: str, settings: dict[str, Any], page: Page) -> None:
        # first, collect the set of pages that are need to be loaded
        pages_to_load: dict[str, dict[str, Any]] = {}
        for page_url, page_def in self.web_settings_definition.items():
            for setting_def in page_def:
                setting = setting_def["name"]
                if setting in settings:
                    _logger.trace("adding page '%s' with setting '%s'", page_url, setting)
                    page_dict = pages_to_load.get(page_url, {})
                    page_dict[setting] = setting_def
                    pages_to_load[page_url] = page_dict

        # second, load the required pages and modify the settings
        for page_url, page_dict in pages_to_load.items():
            _logger.trace("loading page '%s'", page_url)
            response = await page.goto(f"https://github.com/organizations/{org_id}/{page_url}")
            response = unwrap(response)
            if not response.ok:
                raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

            for setting, setting_def in page_dict.items():
                _logger.trace("updating setting '%s'", setting)
                new_value = settings[setting]

                try:
                    setting_type = setting_def["type"]
                    match setting_type:
                        case "checkbox":
                            await page.set_checked(setting_def["selector"], new_value == "True" or new_value)

                        case "radio":
                            await page.set_checked(f"{setting_def['selector']}[value='{new_value}']", True)

                        case "select-menu":
                            pre_selector = setting_def["preSelector"]
                            await page.click(pre_selector)

                            selector = f"{setting_def['saveSelector']}"
                            await page.wait_for_selector(selector, state="attached")
                            handles = await page.query_selector_all(selector)
                            for handle in handles:
                                if new_value == (await handle.inner_text()).strip():
                                    await handle.click()
                                    break

                        case "text":
                            await page.fill(setting_def["selector"], new_value)

                        case _:
                            raise RuntimeError(f"not supported setting type '{setting_type}'")

                    delay_save = setting_def.get("delay_save", None)
                    if delay_save is not None and delay_save in settings:
                        continue

                    # do a trial run first as this will wait till the button is enabled
                    # this might be needed for some text input forms that perform input validation.
                    await page.click(setting_def["save"], trial=True)
                    await page.click(setting_def["save"], trial=False)

                    _logger.trace("updated setting for '%s' = '%s'", setting, new_value)
                except Exception as e:
                    if is_debug_enabled():
                        page_name = page_url.split("/")[-1]
                        screenshot_file = f"screenshot_{page_name}.png"
                        await page.screenshot(path=screenshot_file)
                        _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

                    _logger.warning(f"failed to update setting '{setting}' via web ui:\n{e!s}")
                    raise e

    async def open_browser_with_logged_in_user(self, org_id: str) -> None:
        _logger.trace("opening browser window")

        async with async_playwright() as playwright:
            try:
                browser = await playwright.firefox.launch(headless=False)
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            context = await browser.new_context(no_viewport=True)

            page = await context.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            # ensure that dialogs pop up
            page.on("dialog", lambda x: None)

            await self._login_if_required(page)

            await page.goto(f"https://github.com/{org_id}")
            input("Enter anything to logout and close browser.\n")

            await self._logout(page)

            await page.close()
            await context.close()
            await browser.close()

    async def install_github_app(self, org_int_id: str, app_slug: str) -> None:
        _logger.debug("installing github app '%s'", app_slug)

        async with async_playwright() as playwright:
            try:
                browser = await playwright.firefox.launch(headless=True)
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            context = await browser.new_context(no_viewport=True)

            page = await context.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            await self._login_if_required(page)

            await page.goto(
                f"https://github.com/apps/{app_slug}/installations/new/permissions"
                f"?target_id={org_int_id}&target_type=Organization"
            )

            await page.locator('button:text("Install")').click()

            await self._logout(page)

            await page.close()
            await context.close()
            await browser.close()

    async def uninstall_github_app(self, org_id: str, installation_id: str) -> None:
        _logger.debug("deleting app installation with id '%s'", installation_id)

        async with async_playwright() as playwright:
            try:
                browser = await playwright.firefox.launch(headless=True)
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            context = await browser.new_context(no_viewport=True)

            page = await context.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            await self._login_if_required(page)

            async def accept_dialog(dialog):
                await dialog.accept()

            page.on("dialog", accept_dialog)

            await page.goto(f"https://github.com/organizations/{org_id}/settings/installations/{installation_id}")
            await page.locator('input:text("Uninstall")').click()
            await self._logout(page)

            await page.close()
            await context.close()
            await browser.close()

    @asynccontextmanager
    async def get_logged_in_page(self):
        context_manager = async_playwright()

        page = None
        context = None
        browser = None

        try:
            playwright = await context_manager.start()

            try:
                browser = await playwright.firefox.launch(headless=True)
            except Exception as e:
                tb = e.__traceback__
                raise RuntimeError(
                    "unable to launch browser, make sure you have installed required dependencies using: "
                    "'otterdog install-deps'"
                ).with_traceback(tb) from None

            context = await browser.new_context(no_viewport=True)

            page = await context.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            await self._login_if_required(page)

            yield page
        finally:
            if page is not None:
                await self._logout(page)
                await page.close()

            if context is not None:
                await context.close()

            if browser is not None:
                await browser.close()

            await context_manager.__aexit__()

    async def get_requested_permission_updates(self, org_id: str, page: Page) -> dict[str, dict[str, str]]:
        _logger.debug("getting GitHub app permission updates for '%s'", org_id)

        await page.goto(f"https://github.com/organizations/{org_id}/settings/installations")

        elements = await page.get_by_role("link", name="Review request").all()

        requested_app_permissions = {}

        urls = []
        for element in elements:
            url = await element.get_attribute("href")
            if url is None or not url.endswith("/permissions/update"):
                continue
            else:
                urls.append(url)

        for url in urls:
            await page.goto(f"https://github.com{url}")

            if await page.title() == "Confirm access":
                await page.type("#app_totp", self.credentials.totp)

            m = re.search(
                r"/organizations/([a-zA-Z0-9-]+)/settings/installations/(\d+)/permissions/update",
                url,
            )

            installation_id = m.group(2) if m is not None else None

            permissions = (
                await page.locator(".Box")
                .locator(".Box-row")
                .locator("visible=true")
                .filter(has=page.locator("span"), has_not=page.locator("svg"))
                .all()
            )

            if len(permissions) == 0:
                if is_debug_enabled():
                    screenshot_file = f"screenshot_get_permissions_{org_id}.png"
                    await page.screenshot(path=screenshot_file)
                    _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

                _logger.warning(f"no permissions found when reviewing requested permission updates at url '{url}'")

            permissions_by_app: dict[str, str] = {}
            for permission in permissions:
                permission_text = await permission.inner_text()
                permission_text = permission_text.removesuffix("New request")
                permission_text = permission_text.removesuffix("Was read-only")
                permission_text = permission_text.strip()

                m = re.search(r"(Read-only|Read and write|Admin) access to ([a-zA-Z ]+)", permission_text)

                access_level = {"read": 1, "write": 2, "admin": 3}

                if m is not None:
                    access_type = m.group(1)
                    if access_type == "Read-only":
                        new_access_type = "read"
                    elif access_type == "Admin":
                        new_access_type = "admin"
                    else:
                        new_access_type = "write"

                    permission_type = m.group(2).lower()

                    current_access_type = permissions_by_app.get(permission_type)
                    if current_access_type is not None:
                        if access_level[current_access_type] > access_level[new_access_type]:
                            new_access_type = ""

                    if new_access_type:
                        permissions_by_app[permission_type] = new_access_type
                else:
                    _logger.debug(f"unmatched permission: {permission_text}, url: {url}")

            requested_app_permissions[str(installation_id)] = permissions_by_app

        return requested_app_permissions

    @staticmethod
    async def approve_requested_permission_updates(org_id: str, installation_id: str, page: Page) -> None:
        _logger.debug("approving requested permission updates for '%s'", installation_id)

        async def accept_dialog(dialog):
            await dialog.accept()

        try:
            page.on("dialog", accept_dialog)

            await page.goto(
                f"https://github.com/organizations/{org_id}/settings/installations/{installation_id}/permissions/update"
            )

            button = page.locator('button:text("Accept new permissions")')
            await button.wait_for(state="visible")
            await button.click()
            await page.wait_for_url(
                f"https://github.com/organizations/{org_id}/settings/installations/{installation_id}"
            )
        except PlaywrightError as e:
            if is_debug_enabled():
                screenshot_file = f"screenshot_approve_{org_id}.png"
                await page.screenshot(path=screenshot_file)
                _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

            raise e

    async def _login_if_required(self, page: Page) -> None:
        actor = await self._logged_in_as(page)

        if actor is None:
            await self._login(page)
        elif actor != self.credentials.username:
            raise RuntimeError(f"logged in with unexpected user {actor}")

    @staticmethod
    async def _logged_in_as(page: Page) -> str:
        response = await page.goto("https://github.com/settings/profile")
        response = unwrap(response)
        if not response.ok:
            raise RuntimeError(f"unable to load github profile page: {response.status}")

        try:
            meta_element = page.locator('meta[name="octolytics-actor-login"]')
            actor = await meta_element.evaluate("element => element.content", timeout=1)
        except PlaywrightError:
            actor = None

        return actor

    async def _login(self, page: Page) -> None:
        response = await page.goto("https://github.com/login")
        response = unwrap(response)
        if not response.ok:
            raise RuntimeError(f"unable to load github login page: {response.status}")

        await page.type("#login_field", self.credentials.username)
        await page.type("#password", self.credentials.password)
        await page.click('input[name="commit"]')

        await page.goto("https://github.com/sessions/two-factor")
        await page.type("#app_totp", self.credentials.totp)

        try:
            meta_element = page.locator('meta[name="octolytics-actor-login"]')
            actor = await meta_element.evaluate("element => element.content")
            _logger.trace("logged in as '%s'", actor)

            if await page.title() == "Verify two-factor authentication":
                verify_button = page.get_by_role("button", name="Verify 2FA now")
                if verify_button is not None:
                    await verify_button.click()

                    if await page.is_visible('button[text="Confirm"]'):
                        confirm_button = page.get_by_role("button", name="Confirm")
                        if confirm_button is not None:
                            await confirm_button.click()

                    if await page.title() == "Confirm your account recovery settings":
                        confirm_button = page.get_by_role("button", name="Confirm")
                        if confirm_button is not None:
                            await confirm_button.click()

                    await page.type("#app_totp", self.credentials.totp)
        except PlaywrightError as e:
            raise RuntimeError(f"could not log in to web UI: {e!s}") from e

    async def _logout(self, page: Page) -> None:
        actor = await self._logged_in_as(page)

        response = await page.goto("https://github.com/logout")
        response = unwrap(response)
        if not response.ok:
            response = await page.goto("https://github.com/settings/profile")
            response = unwrap(response)
            if not response.ok:
                raise RuntimeError("unable to load github logout page")

            try:
                selector = f'summary.Header-link > img[alt = "@{actor}"]'
                await page.eval_on_selector(selector, "el => el.click()")
                await page.wait_for_selector('button[type="submit"].dropdown-signout')
                await page.eval_on_selector('button[type="submit"].dropdown-signout', "el => el.click()")
            except Exception as e:
                if is_debug_enabled():
                    screenshot_file = "screenshot_profile.png"
                    await page.screenshot(path=screenshot_file)
                    _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

                _logger.warning(f"failed to logout via web ui: {e!s}")
        else:
            try:
                selector = 'input[value = "Sign out"]'
                await page.eval_on_selector(selector, "el => el.click()")
            except Exception as e:
                if is_debug_enabled():
                    screenshot_file = "screenshot_profile.png"
                    await page.screenshot(path=screenshot_file)
                    _logger.warning(f"saved page screenshot to file '{screenshot_file}'")

                _logger.warning(f"failed to logout via web ui: {e!s}")
