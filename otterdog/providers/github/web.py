#  *******************************************************************************
#  Copyright (c) 2023-2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from functools import cached_property
from typing import Any

from importlib_resources import files
from playwright.sync_api import Error, Page, sync_playwright

from otterdog import resources, utils
from otterdog.credentials import Credentials


class WebClient:
    # use 10s as default timeout
    _DEFAULT_TIMEOUT = 15000

    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    @cached_property
    def web_settings_definition(self) -> dict[str, Any]:
        # load the definition file which describes how the web settings
        # can be retrieved / modified.
        utils.print_trace("getting web_settings config using jsonnet")

        web_settings_config = files(resources).joinpath("github-web-settings.jsonnet")
        return utils.jsonnet_evaluate_file(str(web_settings_config))

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, Any]:
        utils.print_debug("retrieving settings via web interface")

        with sync_playwright() as playwright:
            browser = playwright.firefox.launch()

            page = browser.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            self._login_if_required(page)
            settings = self._retrieve_settings(org_id, included_keys, page)
            self._logout(page)

            page.close()
            browser.close()

            return settings

    def _retrieve_settings(self, org_id: str, included_keys: set[str], page: Page) -> dict[str, Any]:
        settings: dict[str, Any] = {}

        for page_url, page_def in self.web_settings_definition.items():
            # check if the page contains any setting that is requested
            if not any(x in included_keys for x in list(map(lambda x: x["name"], page_def))):
                continue

            utils.print_trace(f"loading page '{page_url}'")
            response = page.goto("https://github.com/organizations/{}/{}".format(org_id, page_url))
            assert response is not None
            if not response.ok:
                raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

            for setting_def in page_def:
                setting = setting_def["name"]
                optional = setting_def["optional"]
                utils.print_trace(f"checking setting '{setting}'")

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
                        page.click(pre_selector)
                        page.wait_for_selector(selector, state="attached")

                    value = page.eval_on_selector(
                        selector,
                        "(el, property) => el[property]",
                        setting_def["valueSelector"],
                    )

                    if isinstance(value, str):
                        value = value.strip()

                    settings[setting] = value
                    utils.print_trace(f"retrieved setting for '{setting}' = '{value}'")

                except Exception as e:
                    if optional:
                        continue

                    if utils.is_debug_enabled():
                        page_name = page_url.split("/")[-1]
                        screenshot_file = f"screenshot_{page_name}.png"
                        page.screenshot(path=screenshot_file)
                        utils.print_warn(f"saved page screenshot to file '{screenshot_file}'")

                    utils.print_warn(f"failed to retrieve setting '{setting}' via web ui:\n{str(e)}")

        return settings

    def update_org_settings(self, org_id: str, data: dict[str, Any]) -> None:
        utils.print_debug("updating settings via web interface")

        with sync_playwright() as playwright:
            browser = playwright.firefox.launch()

            page = browser.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            self._login_if_required(page)
            self._update_settings(org_id, data, page)
            self._logout(page)

            page.close()
            browser.close()

            utils.print_debug(f"updated {len(data)} setting(s) via web interface")

    def _update_settings(self, org_id: str, settings: dict[str, Any], page: Page) -> None:
        # first, collect the set of pages that are need to be loaded
        pages_to_load: dict[str, dict[str, Any]] = {}
        for page_url, page_def in self.web_settings_definition.items():
            for setting_def in page_def:
                setting = setting_def["name"]
                if setting in settings:
                    utils.print_trace(f"adding page '{page_url}' with setting '{setting}'")
                    page_dict = pages_to_load.get(page_url, {})
                    page_dict[setting] = setting_def
                    pages_to_load[page_url] = page_dict

        # second, load the required pages and modify the settings
        for page_url, page_dict in pages_to_load.items():
            utils.print_trace(f"loading page '{page_url}'")
            response = page.goto("https://github.com/organizations/{}/{}".format(org_id, page_url))
            assert response is not None
            if not response.ok:
                raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

            for setting, setting_def in page_dict.items():
                utils.print_trace(f"updating setting '{setting}'")
                new_value = settings[setting]

                try:
                    setting_type = setting_def["type"]
                    match setting_type:
                        case "checkbox":
                            page.set_checked(setting_def["selector"], new_value == "True" or new_value)

                        case "radio":
                            page.set_checked(f"{setting_def['selector']}[value='{new_value}']", True)

                        case "select-menu":
                            pre_selector = setting_def["preSelector"]
                            page.click(pre_selector)

                            selector = f"{setting_def['saveSelector']}"
                            page.wait_for_selector(selector, state="attached")
                            handles = page.query_selector_all(selector)
                            for handle in handles:
                                if new_value == handle.inner_text().strip():
                                    handle.click()
                                    break

                        case "text":
                            page.fill(setting_def["selector"], new_value)

                        case _:
                            raise RuntimeError(f"not supported setting type '{setting_type}'")

                    delay_save = setting_def.get("delay_save", None)
                    if delay_save is not None and delay_save in settings:
                        continue

                    # do a trial run first as this will wait till the button is enabled
                    # this might be needed for some text input forms that perform input validation.
                    page.click(setting_def["save"], trial=True)
                    page.click(setting_def["save"], trial=False)

                    utils.print_trace(f"updated setting for '{setting}' = '{new_value}'")
                except Exception as e:
                    if utils.is_debug_enabled():
                        page_name = page_url.split("/")[-1]
                        screenshot_file = f"screenshot_{page_name}.png"
                        page.screenshot(path=screenshot_file)
                        utils.print_warn(f"saved page screenshot to file '{screenshot_file}'")

                    utils.print_warn(f"failed to update setting '{setting}' via web ui:\n{str(e)}")
                    raise e

    def open_browser_with_logged_in_user(self, org_id: str) -> None:
        utils.print_debug("opening browser window")

        with sync_playwright() as playwright:
            browser = playwright.firefox.launch(headless=False)
            context = browser.new_context(no_viewport=True)

            page = context.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            self._login_if_required(page)

            page.goto("https://github.com/{}".format(org_id))
            input("Enter anything to logout and close browser.\n")

            self._logout(page)

            page.close()
            context.close()
            browser.close()

    def _login_if_required(self, page: Page) -> None:
        actor = self._logged_in_as(page)

        if actor is None:
            self._login(page)
        elif actor != self.credentials.username:
            raise RuntimeError(f"logged in with unexpected user {actor}")

    @staticmethod
    def _logged_in_as(page: Page) -> str:
        response = page.goto("https://github.com/settings/profile")
        assert response is not None
        if not response.ok:
            raise RuntimeError(f"unable to load github profile page: {response.status}")

        try:
            actor = page.eval_on_selector('meta[name="octolytics-actor-login"]', "element => element.content")
        except Error:
            actor = None

        return actor

    def _login(self, page: Page) -> None:
        response = page.goto("https://github.com/login")
        assert response is not None
        if not response.ok:
            raise RuntimeError(f"unable to load github login page: {response.status}")

        page.type("#login_field", self.credentials.username)
        page.type("#password", self.credentials.password)
        page.click('input[name="commit"]')

        page.goto("https://github.com/sessions/two-factor")
        page.type("#app_totp", self.credentials.totp)

        try:
            actor = page.eval_on_selector('meta[name="octolytics-actor-login"]', "element => element.content")
            utils.print_trace(f"logged in as {actor}")

            if page.title() == "Verify two-factor authentication":
                verify_button = page.get_by_role("button", name="Verify 2FA now")
                if verify_button is not None:
                    verify_button.click()

                    if page.is_visible('button[text="Confirm"]'):
                        confirm_button = page.get_by_role("button", name="Confirm")
                        if confirm_button is not None:
                            confirm_button.click()

                    if page.title() == "Confirm your account recovery settings":
                        confirm_button = page.get_by_role("button", name="Confirm")
                        if confirm_button is not None:
                            confirm_button.click()

                    page.type("#app_totp", self.credentials.totp)
        except Error as e:
            raise RuntimeError(f"could not log in to web UI: {str(e)}")

    def _logout(self, page: Page) -> None:
        actor = self._logged_in_as(page)

        response = page.goto("https://github.com/logout")
        assert response is not None
        if not response.ok:
            response = page.goto("https://github.com/settings/profile")
            assert response is not None
            if not response.ok:
                raise RuntimeError("unable to load github logout page")

            try:
                selector = 'summary.Header-link > img[alt = "@{}"]'.format(actor)
                page.eval_on_selector(selector, "el => el.click()")
                page.wait_for_selector('button[type="submit"].dropdown-signout')
                page.eval_on_selector('button[type="submit"].dropdown-signout', "el => el.click()")
            except Exception as e:
                if utils.is_debug_enabled():
                    screenshot_file = "screenshot_profile.png"
                    page.screenshot(path=screenshot_file)
                    utils.print_warn(f"saved page screenshot to file '{screenshot_file}'")

                raise RuntimeError(f"failed to logout via web ui: {str(e)}")
        else:
            try:
                selector = 'input[value = "Sign out"]'
                page.eval_on_selector(selector, "el => el.click()")
            except Exception as e:
                if utils.is_debug_enabled():
                    screenshot_file = "screenshot_profile.png"
                    page.screenshot(path=screenshot_file)
                    utils.print_warn(f"saved page screenshot to file '{screenshot_file}'")

                raise RuntimeError(f"failed to logout via web ui: {str(e)}")
