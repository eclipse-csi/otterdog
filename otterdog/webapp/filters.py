#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************
import json


def register_filters(app):
    @app.template_filter("status")
    def status_color(status):
        from otterdog.webapp.db.models import InstallationStatus

        match status:
            case InstallationStatus.INSTALLED:
                return "success"
            case InstallationStatus.NOT_INSTALLED:
                return "danger"
            case InstallationStatus.SUSPENDED:
                return "warning"
            case _:
                return "info"

    @app.template_filter("int_status")
    def int_status_color(value):
        if value == 0:
            return "success"
        else:
            return "warning"

    @app.template_filter("from_json")
    def from_json(value):
        return json.loads(value)

    @app.template_filter("is_dict")
    def is_dict(value):
        return isinstance(value, dict)

    @app.template_filter("length_to_color")
    def length_to_color(value):
        if len(value) == 0:
            return "primary"
        else:
            return "success"

    @app.template_filter("has_dummy_secret")
    def has_dummy_secret(value):
        return value.has_dummy_secret()

    @app.template_filter("has_dummy_secrets")
    def any_has_dummy_secrets(value):
        return any(map(lambda x: x.has_dummy_secret(), value))

    @app.template_filter("pretty_format_model")
    def pretty_format_model(value):
        from otterdog.models import ModelObject
        from otterdog.utils import PrettyFormatter

        assert isinstance(value, ModelObject)
        return PrettyFormatter().format(value.to_model_dict(False, False))

    @app.template_filter("short_name")
    def project_short_name(value):
        return value.split(".")[-1]
