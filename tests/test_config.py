#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from otterdog.config import OtterdogConfig, load_json_or_jsonnet

# Type alias for the temporary file creation function
CreateTmpFile = Callable[[str, str], Path]


@pytest.fixture
def create_tmp_file():
    """Factory fixture to create temporary files."""
    with TemporaryDirectory() as temp_dir:

        def _create(filename: str, content: str) -> Path:
            test_file = Path(temp_dir) / filename
            _ = test_file.write_text(content)
            return test_file

        yield _create


def test_config_loading():
    """Test that loading from JSON and Jsonnet yields the same configuration."""

    def _get_config_file(filename: str) -> str:
        return str(Path(__file__).parent / filename)

    config_json = OtterdogConfig.from_file(_get_config_file("models/resources/otterdog.json"), False)
    config_jsonnet = OtterdogConfig.from_file(_get_config_file("models/resources/otterdog.jsonnet"), False)

    # Compare the actual configuration data, not object identity
    assert config_json.configuration == config_jsonnet.configuration
    assert config_json.local_mode == config_jsonnet.local_mode
    assert config_json.project_names == config_jsonnet.project_names
    assert config_json.organization_names == config_jsonnet.organization_names


def test_load_json(create_tmp_file: CreateTmpFile):
    """Test loading a valid JSON file."""
    test_file = create_tmp_file("test.json", '{"key": "value", "nested": {"data": 123}}')

    data = load_json_or_jsonnet(test_file)

    assert data == {"key": "value", "nested": {"data": 123}}


def test_load_jsonnet(create_tmp_file: CreateTmpFile):
    """Test loading a valid Jsonnet file."""
    test_file = create_tmp_file("test.jsonnet", 'local V=123; { key: "value", nested: { data: V } }')

    data = load_json_or_jsonnet(test_file)

    assert data == {"key": "value", "nested": {"data": 123}}


def test_load_json_invalid(create_tmp_file: CreateTmpFile):
    """Ensure invalid JSON syntax raises a human readable error."""

    test_file = create_tmp_file("invalid.json", '{"invalid": "json" "missing": "comma"}')

    with pytest.raises(RuntimeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "failed to parse json file" in error_message
    assert "invalid.json" in error_message


def test_load_jsonnet_invalid(create_tmp_file: CreateTmpFile):
    """Ensure invalid Jsonnet raises a human readable error."""

    test_file = create_tmp_file("invalid.jsonnet", "{ key: undefined_variable }")

    with pytest.raises(RuntimeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "failed to evaluate jsonnet file" in error_message
    assert "invalid.jsonnet" in error_message


def test_load_json_not_object(create_tmp_file: CreateTmpFile):
    """Ensure that JSON containing a non-object (array) raises a human readable error."""

    test_file = create_tmp_file("array.json", '["this", "is", "an", "array"]')

    with pytest.raises(RuntimeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "expected JSON object" in error_message
    assert "array.json" in error_message


def test_load_jsonnet_not_object(create_tmp_file: CreateTmpFile):
    """Ensure that Jsonnet evaluating to a non-object (array) raises a human readable error."""

    test_file = create_tmp_file("array.jsonnet", '["this", "is", "an", "array"]')

    with pytest.raises(RuntimeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "expected JSON object" in error_message
    assert "array.jsonnet" in error_message
