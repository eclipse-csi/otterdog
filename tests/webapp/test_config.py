#  *******************************************************************************
#  Copyright (c) 2025 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import pytest

from otterdog.webapp.config import (
    REQUIRED_NON_EMPTY_SETTINGS,
    TestingConfig,
    config,
    validate_required_settings,
)


def test_config_strips_whitespace_from_string_values(monkeypatch):
    monkeypatch.setenv("SOME_TEST_SETTING", "  value-with-spaces  \n")
    assert config("SOME_TEST_SETTING") == "value-with-spaces"


def test_config_leaves_non_string_defaults_untouched(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_SETTING", raising=False)
    assert config("SOME_MISSING_SETTING", default=False) is False


def _stub_config(**overrides):
    """A config class with every required setting set to a dummy value, independent of any .env file."""
    values = {name: f"dummy-{name}" for name in REQUIRED_NON_EMPTY_SETTINGS}
    values.update(overrides)
    return type("StubConfig", (), values)


def test_validate_required_settings_accepts_fully_populated_config():
    validate_required_settings(_stub_config())


def test_required_settings_are_defined_on_testing_config():
    # guards against typos in REQUIRED_NON_EMPTY_SETTINGS not matching a real config attribute
    for name in REQUIRED_NON_EMPTY_SETTINGS:
        assert hasattr(TestingConfig, name), f"{name} is not a valid config attribute"


@pytest.mark.parametrize("empty_value", ["", None])
def test_validate_required_settings_rejects_empty_values(empty_value):
    name = REQUIRED_NON_EMPTY_SETTINGS[0]
    config_cls = _stub_config(**{name: empty_value})

    with pytest.raises(ValueError, match=name):
        validate_required_settings(config_cls)


def test_validate_required_settings_rejects_missing_attribute():
    name = REQUIRED_NON_EMPTY_SETTINGS[0]
    values = {n: f"dummy-{n}" for n in REQUIRED_NON_EMPTY_SETTINGS if n != name}
    config_cls = type("StubConfig", (), values)

    with pytest.raises(ValueError, match=name):
        validate_required_settings(config_cls)
