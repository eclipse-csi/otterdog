#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Restricts the secrets that the configuration of an organization can reference in a credential provider, e.g. to
prevent an organization from using the secrets of another one stored in the same pass vault.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from otterdog.credentials import SECRET_PROVIDER_TYPES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from otterdog.credentials import CredentialPlaceHolders

# a segment of a reference: no '/', no shell metacharacter, no whitespace
_SEGMENT = re.compile(r"[A-Za-z0-9._@+-]+")
# the parts of a segment of a pattern that are not matched literally
_PATTERN_TOKEN = re.compile(r"\{([A-Za-z_]+)\}|\*")

# values to check the syntax of patterns when loading the configuration, before knowing the organization
_SYNTAX_PLACEHOLDERS = {"org_name": "org", "github_id": "org"}


class SecretAccessMode(StrEnum):
    WARN = "warn"
    ENFORCE = "enforce"


class _Pattern:
    """
    A pattern of the references allowed for an organization, matched segment by segment: '*' matches any part of
    a segment, '**' matches one or more segments at the end of the pattern, zero or more elsewhere, and the
    placeholders '{org_name}' and '{github_id}' match the values of the organization literally.
    """

    def __init__(self, pattern: str, placeholders: Mapping[str, str]):
        self._segments: list[re.Pattern[str] | None] = []
        displayed_segments: list[str] = []

        for segment in pattern.split("/"):
            if segment == "**":
                self._segments.append(None)
                displayed_segments.append(segment)
                continue

            if segment in ("", ".", ".."):
                raise ValueError(f"invalid pattern '{pattern}': empty, '.' and '..' segments are not allowed")
            if "**" in segment:
                raise ValueError(f"invalid pattern '{pattern}': '**' must be a whole segment")

            regex = ""
            displayed = ""
            position = 0
            for token in _PATTERN_TOKEN.finditer(segment):
                literal = segment[position : token.start()]
                regex += self._literal(pattern, literal)
                displayed += literal

                if token.group(0) == "*":
                    regex += "[^/]*"
                    displayed += "*"
                else:
                    name = token.group(1)
                    value = placeholders.get(name)
                    if value is None:
                        raise ValueError(
                            f"invalid pattern '{pattern}': unknown placeholder '{{{name}}}', "
                            f"supported placeholders are '{{org_name}}' and '{{github_id}}'"
                        )
                    # the value of a placeholder is matched literally, whatever it contains
                    regex += re.escape(value)
                    displayed += value

                position = token.end()

            literal = segment[position:]
            regex += self._literal(pattern, literal)
            displayed += literal

            self._segments.append(re.compile(regex))
            displayed_segments.append(displayed)

        self._displayed = "/".join(displayed_segments)

    @staticmethod
    def _literal(pattern: str, literal: str) -> str:
        if literal and _SEGMENT.fullmatch(literal) is None:
            raise ValueError(
                f"invalid pattern '{pattern}': only letters, digits, '.', '_', '@', '+', '-', '*' and placeholders "
                f"are allowed in a segment"
            )
        return re.escape(literal)

    def matches(self, segments: Sequence[str]) -> bool:
        return self._matches(0, segments, 0)

    def _matches(self, pattern_index: int, segments: Sequence[str], segment_index: int) -> bool:
        if pattern_index == len(self._segments):
            return segment_index == len(segments)

        pattern_segment = self._segments[pattern_index]
        if pattern_segment is None:
            # '**' ending the pattern matches at least one segment, e.g. 'bots/{org_name}/**' not 'bots/{org_name}'
            is_last = pattern_index == len(self._segments) - 1
            first = segment_index + 1 if is_last else segment_index
            return any(self._matches(pattern_index + 1, segments, i) for i in range(first, len(segments) + 1))

        return (
            segment_index < len(segments)
            and pattern_segment.fullmatch(segments[segment_index]) is not None
            and self._matches(pattern_index + 1, segments, segment_index + 1)
        )

    def __str__(self) -> str:
        return self._displayed


class SecretAccessPolicy:
    """
    The secrets that the configuration of an organization can reference, for each credential provider. The secrets
    of a provider without allowed references cannot be referenced at all.
    """

    def __init__(
        self,
        mode: SecretAccessMode,
        allowed_references: Mapping[str, Sequence[str]],
        placeholders: CredentialPlaceHolders,
    ):
        self._mode = mode
        values = {"org_name": placeholders["org_name"], "github_id": placeholders["github_id"]}
        self._patterns = {
            provider_type: tuple(_Pattern(pattern, values) for pattern in patterns)
            for provider_type, patterns in allowed_references.items()
        }

    @property
    def mode(self) -> SecretAccessMode:
        return self._mode

    @property
    def is_enforced(self) -> bool:
        return self._mode == SecretAccessMode.ENFORCE

    def check(self, secret_data: str) -> str | None:
        """
        Returns why the organization cannot reference the given secret, e.g. 'pass:path/to/secret', None if it can,
        or if the value does not reference a secret of a credential provider.
        """

        provider_type, separator, reference = secret_data.partition(":")
        if not separator or provider_type not in SECRET_PROVIDER_TYPES:
            return None

        if provider_type == "bitwarden":
            # 'item_id@field': access is granted per item
            subject, separator, field = reference.partition("@")
            if not separator or not subject or not field:
                return f"'{reference}' is not a valid bitwarden reference, expected '<item id>@<field>'"
        else:
            subject = reference

        segments = subject.split("/")
        if any(segment in (".", "..") or _SEGMENT.fullmatch(segment) is None for segment in segments):
            return (
                f"'{subject}' is not a valid reference, it must consist of segments separated by '/' that only "
                f"contain letters, digits, '.', '_', '@', '+' and '-', and are not '.' or '..'"
            )

        patterns = self._patterns.get(provider_type, ())
        if len(patterns) == 0:
            return f"no secret of provider '{provider_type}' is allowed"

        if any(pattern.matches(segments) for pattern in patterns):
            return None

        allowed = ", ".join(f"'{pattern}'" for pattern in patterns)
        return f"'{subject}' does not match the allowed references of provider '{provider_type}': {allowed}"

    @staticmethod
    def parse_mode(value: Any, key: str) -> SecretAccessMode:
        if value is None:
            return SecretAccessMode.ENFORCE

        try:
            return SecretAccessMode(value)
        except ValueError:
            allowed = ", ".join(f"'{mode}'" for mode in SecretAccessMode)
            raise RuntimeError(f"invalid '{key}': expected one of {allowed}, got {value!r}") from None

    @staticmethod
    def parse_allowed_references(value: Any, key: str) -> dict[str, tuple[str, ...]]:
        """
        Parses and checks the syntax of the allowed references of the configuration, e.g.
        {"pass": ["bots/{org_name}/**"], "vault": ["{org_name}/**"]}.
        """

        if value is None:
            return {}
        if not isinstance(value, dict):
            raise TypeError(f"invalid '{key}': expected an object, got {value!r}")

        result: dict[str, tuple[str, ...]] = {}
        for provider_type, patterns in value.items():
            if provider_type not in SECRET_PROVIDER_TYPES:
                allowed = ", ".join(f"'{p}'" for p in sorted(SECRET_PROVIDER_TYPES))
                raise RuntimeError(f"invalid '{key}': unknown provider '{provider_type}', expected one of {allowed}")
            if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
                raise TypeError(f"invalid '{key}.{provider_type}': expected a list of strings, got {patterns!r}")

            for pattern in patterns:
                try:
                    _Pattern(pattern, _SYNTAX_PLACEHOLDERS)
                except ValueError as e:
                    raise RuntimeError(f"invalid '{key}.{provider_type}': {e}") from None

            result[provider_type] = tuple(patterns)

        return result
