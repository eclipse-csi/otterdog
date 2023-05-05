# *******************************************************************************
# Copyright (c) 2023 Eclipse Foundation and others.
# This program and the accompanying materials are made available
# under the terms of the MIT License
# which is available at https://spdx.org/licenses/MIT.html
# SPDX-License-Identifier: MIT
# *******************************************************************************

from functools import cached_property
from typing import Any

from importlib_resources import files
from playwright.sync_api import sync_playwright, Page, Error

from otterdog import resources
from otterdog import utils
from otterdog.credentials import Credentials


class WebClient:
    # use 10s as default timeout
    _DEFAULT_TIMEOUT = 10000

    def __init__(self, credentials: Credentials):
        self.credentials = credentials

    @cached_property
    def web_settings_definition(self) -> dict[str, Any]:
        # load the definition file which describes how the web settings
        # can be retrieved / modified.
        utils.print_trace(f"getting web_settings config using jsonnet")

        web_settings_config = files(resources).joinpath("github-web-settings.jsonnet")
        return utils.jsonnet_evaluate_file(str(web_settings_config))

    def get_org_settings(self, org_id: str, included_keys: set[str]) -> dict[str, str]:
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

    def _retrieve_settings(self, org_id: str, included_keys: set[str], page: Page) -> dict[str, str]:
        settings = {}

        for page_url, page_def in self.web_settings_definition.items():
            # check if the page contains any setting that is requested
            if not any(x in included_keys for x in page_def.keys()):
                continue

            utils.print_trace(f"loading page '{page_url}'")
            response = page.goto("https://github.com/organizations/{}/{}".format(org_id, page_url))
            if not response.ok:
                raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

            for setting, setting_def in page_def.items():
                if setting not in included_keys:
                    continue

                try:
                    value = page.eval_on_selector(setting_def['selector'],
                                                  "(el, property) => el[property]",
                                                  setting_def['valueSelector'])

                    utils.print_trace(f"retrieved setting for '{setting}' = '{value}'")

                except Exception as e:
                    if utils.is_debug_enabled():
                        page_name = page_url.split("/")[-1]
                        screenshot_file = f"screenshot_{page_name}.png"
                        page.screenshot(path=screenshot_file)
                        utils.print_warn(f"saved page screenshot to file '{screenshot_file}'")

                    raise RuntimeError(f"failed to retrieve setting '{setting}' via web ui: {str(e)}")

                settings[setting] = value

        return settings

    def update_org_settings(self, org_id: str, data: dict[str, str]) -> None:
        utils.print_debug("updating settings via web interface")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            page = browser.new_page()
            page.set_default_timeout(self._DEFAULT_TIMEOUT)

            self._login_if_required(page)
            self._update_settings(org_id, data, page)
            self._logout(page)

            page.close()
            browser.close()

            utils.print_debug(f"updated {len(data)} setting(s) via web interface")

    def _update_settings(self, org_id: str, settings: dict[str, str], page: Page) -> None:
        # first, collect the set of pages that are need to be loaded
        pages_to_load = {}
        for page_url, page_def in self.web_settings_definition.items():
            for setting, setting_def in page_def.items():
                if setting in settings:
                    utils.print_trace(f"adding page '{page_url}' with setting '{setting}'")
                    page_dict = pages_to_load.get(page_url, {})
                    page_dict[setting] = setting_def
                    pages_to_load[page_url] = page_dict

        # second, load the required pages and modify the settings
        for page_url, page_dict in pages_to_load.items():
            utils.print_trace(f"loading page '{page_url}'")
            response = page.goto("https://github.com/organizations/{}/{}".format(org_id, page_url))
            if not response.ok:
                raise RuntimeError(f"unable to access github page '{page_url}': {response.status}")

            for setting, setting_def in page_dict.items():
                new_value = settings[setting]

                if isinstance(new_value, bool):
                    page.set_checked(setting_def['selector'], new_value == 'True' or new_value)
                elif isinstance(new_value, str):
                    page.fill(setting_def['selector'], new_value)
                else:
                    raise RuntimeError(f"not yet supported value type '{type(new_value)}'")

                # do a trial run first as this will wait till the button is enabled
                # this might be needed for some text input forms that perform input validation.
                page.click(setting_def['save'], trial=True)
                page.click(setting_def['save'], trial=False)

                utils.print_trace(f"updated setting for '{setting}' = '{new_value}'")

    def _login_if_required(self, page: Page) -> None:
        actor = self._logged_in_as(page)

        if actor is None:
            self._login(page)
        elif actor != self.credentials.username:
            raise RuntimeError(f"logged in with unexpected user {actor}")

    def _logged_in_as(self, page: Page) -> str:
        response = page.goto("https://github.com/settings/profile")

        if not response.ok:
            raise RuntimeError(f"unable to load github profile page: {response.status}")

        try:
            actor = page.eval_on_selector('meta[name="octolytics-actor-login"]',
                                          "element => element.content")
        except Error:
            actor = None

        return actor

    def _login(self, page: Page) -> None:
        response = page.goto("https://github.com/login")

        if not response.ok:
            raise RuntimeError(f"unable to load github login page: {response.status}")

        page.type("#login_field", self.credentials.username)
        page.type("#password", self.credentials.password)
        page.click('input[name="commit"]')

        page.goto("https://github.com/sessions/two-factor")
        page.type("#app_totp", self.credentials.get_totp())

    def _logout(self, page: Page) -> None:
        actor = self._logged_in_as(page)
        response = page.goto("https://github.com/settings/profile")

        if not response.ok:
            raise RuntimeError("unable to load github logout page")

        selector = 'div.Header-item > details.details-overlay > summary.Header-link > img[alt = "@{}"]'.format(actor)
        page.eval_on_selector(selector, "el => el.click()")
        page.wait_for_selector('button[type="submit"].dropdown-signout')
        page.eval_on_selector('button[type="submit"].dropdown-signout', "el => el.click()")
