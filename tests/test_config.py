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
from otterdog.jsonnet import JsonnetConfig
from otterdog.models.github_organization import GitHubOrganization
from otterdog.utils import restrict_jsonnet_imports

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

    with pytest.raises(TypeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "expected JSON object" in error_message
    assert "array.json" in error_message


def test_load_jsonnet_not_object(create_tmp_file: CreateTmpFile):
    """Ensure that Jsonnet evaluating to a non-object (array) raises a human readable error."""

    test_file = create_tmp_file("array.jsonnet", '["this", "is", "an", "array"]')

    with pytest.raises(TypeError) as exc_info:
        _ = load_json_or_jsonnet(test_file)

    error_message = str(exc_info.value)
    assert "expected JSON object" in error_message
    assert "array.jsonnet" in error_message


_MINIMAL_OTTERDOG_JSON = """\
{
  "defaults": {
    "jsonnet": {
      "base_template": "https://github.com/test/test#test.libsonnet@main",
      "config_dir": "."
    }
  },
  "organizations": []
}
"""


def test_from_file_loads_defaults_override_when_present(create_tmp_file: CreateTmpFile):
    """from_file() must merge .otterdog-defaults.json into configuration["defaults"]."""
    config_file = create_tmp_file("otterdog.json", _MINIMAL_OTTERDOG_JSON)
    create_tmp_file(
        ".otterdog-defaults.json",
        '{"pass": {"password_store_dir": "/custom/store"}}',
    )

    config = OtterdogConfig.from_file(str(config_file), False)

    assert config.configuration["defaults"]["pass"]["password_store_dir"] == "/custom/store"


def test_from_file_skips_defaults_override_when_absent(create_tmp_file: CreateTmpFile):
    """from_file() must not fail and must leave defaults untouched when .otterdog-defaults.json is absent."""
    config_file = create_tmp_file("otterdog.json", _MINIMAL_OTTERDOG_JSON)

    config = OtterdogConfig.from_file(str(config_file), False)

    assert "pass" not in config.configuration.get("defaults", {})


def test_from_file_loads_defaults_override_even_with_explicit_working_dir(create_tmp_file: CreateTmpFile):
    """from_file() must load .otterdog-defaults.json from config_file_dir regardless of working_dir.

    Regression test: previously the load was gated on `working_dir is None`, which caused
    .otterdog-defaults.json to never be loaded when OTTERDOG_CONFIG_ROOT was set (because
    working_dir was always populated from os.curdir in cli.py).
    """
    config_file = create_tmp_file("otterdog.json", _MINIMAL_OTTERDOG_JSON)
    create_tmp_file(
        ".otterdog-defaults.json",
        '{"pass": {"password_store_dir": "/custom/store"}}',
    )
    different_working_dir = str(config_file.parent)

    config = OtterdogConfig.from_file(str(config_file), False, working_dir=different_working_dir)

    assert config.configuration["defaults"]["pass"]["password_store_dir"] == "/custom/store"


def _config_with_defaults(defaults: dict) -> OtterdogConfig:
    with TemporaryDirectory() as temp_dir:
        return OtterdogConfig.from_dict({"defaults": defaults, "organizations": []}, False, temp_dir)


def test_cost_policy_defaults_to_github_free_cache_size():
    assert _config_with_defaults({}).cost_policy.free_max_cache_size_gb == 10


def test_cost_policy_reads_configured_free_cache_size():
    config = _config_with_defaults({"cost_policy": {"free_max_cache_size_gb": 25}})

    assert config.cost_policy.free_max_cache_size_gb == 25


@pytest.mark.parametrize("value", [-1, "10", 1.5, True, None])
def test_cost_policy_rejects_invalid_free_cache_size(value):
    config = _config_with_defaults({"cost_policy": {"free_max_cache_size_gb": value}})

    with pytest.raises(RuntimeError, match="free_max_cache_size_gb"):
        _ = config.cost_policy


@pytest.mark.parametrize("local_mode", [False, True])
async def test_bundled_defaults_load_without_writing_vendor_files(tmp_path, local_mode, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = OtterdogConfig.from_dict(
        {"organizations": [{"name": "sample", "github_id": "sample"}]}, local_mode, str(tmp_path)
    )
    organization_config = config.get_organization_config("sample")
    assert organization_config.base_template is None
    jsonnet_config = organization_config.jsonnet_config
    existing_paths = set(tmp_path.rglob("*"))
    await jsonnet_config.init_template()
    assert jsonnet_config.default_org_config["settings"]["default_repository_permission"] == "read"

    config_file = Path(jsonnet_config.org_config_file)
    config_file.parent.mkdir(parents=True)
    config_file.write_text(f"({jsonnet_config.import_statement}).newOrg('sample', 'sample')\n")

    with restrict_jsonnet_imports(jsonnet_config.org_dir):
        organization = GitHubOrganization.load_from_file("sample", str(config_file))
        defaults = jsonnet_config.default_org_config_for_org_id("sample", "sample")

    assert organization.github_id == "sample"
    assert organization.settings.default_repository_permission == "read"
    assert defaults["settings"]["default_repository_permission"] == "read"
    assert set(tmp_path.rglob("*")) == existing_paths | {config_file.parent, config_file}


async def test_missing_custom_template_is_not_replaced_with_bundled_defaults(tmp_path):
    jsonnet_config = JsonnetConfig(
        "sample", str(tmp_path), "https://github.com/example/custom#custom.libsonnet@main", local_only=True
    )
    with pytest.raises(RuntimeError, match=r"template file .* does not exist"):
        await jsonnet_config.init_template()


async def test_bundled_defaults_leave_existing_vendor_files_untouched(tmp_path):
    jsonnet_config = JsonnetConfig("sample", str(tmp_path), None, local_only=False)
    vendor_file = Path(jsonnet_config.org_dir) / "vendor" / "otterdog" / "otterdog-defaults.libsonnet"
    vendor_file.parent.mkdir(parents=True)
    vendor_file.write_text("{ custom: true }\n")

    await jsonnet_config.init_template()

    assert vendor_file.read_text() == "{ custom: true }\n"
    assert jsonnet_config.default_org_config["settings"]["default_repository_permission"] == "read"


async def test_global_and_organization_base_template_overrides_are_evaluated(tmp_path):
    # An explicitly configured upstream URL keeps its repository path, even for an older layout.
    global_template = "https://github.com/eclipse-csi/otterdog#examples/template/otterdog-defaults.libsonnet@main"
    organization_template = "https://github.com/example/org#custom.libsonnet@v1"
    config = OtterdogConfig.from_dict(
        {
            "defaults": {"jsonnet": {"base_template": global_template}},
            "organizations": [
                {"name": "inherited", "github_id": "inherited"},
                {"name": "custom", "github_id": "custom", "base_template": organization_template},
            ],
        },
        True,
        str(tmp_path),
    )

    inherited = config.get_organization_config("inherited")
    custom = config.get_organization_config("custom")
    assert inherited.base_template == global_template
    assert inherited.jsonnet_config.base_template_repo_name == "otterdog"
    assert custom.base_template == organization_template
    assert custom.jsonnet_config.base_template_repo_name == "org"

    for jsonnet_config, file_name, value in (
        (inherited.jsonnet_config, "examples/template/otterdog-defaults.libsonnet", "global"),
        (custom.jsonnet_config, "custom.libsonnet", "organization"),
    ):
        template_file = Path(jsonnet_config.org_dir) / "vendor" / jsonnet_config.base_template_repo_name / file_name
        assert Path(jsonnet_config.template_file) == template_file
        template_file.parent.mkdir(parents=True, exist_ok=True)
        template_file.write_text(f"{{ newOrg(name, id): {{ settings: {{ source: '{value}' }} }} }}\n")
        await jsonnet_config.init_template()

    assert inherited.jsonnet_config.default_org_config_for_org_id("inherited", "inherited")["settings"]["source"] == (
        "global"
    )
    assert custom.jsonnet_config.default_org_config_for_org_id("custom", "custom")["settings"]["source"] == (
        "organization"
    )
