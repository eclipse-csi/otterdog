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


class _SegmentPattern:
    """
    A segment of a pattern other than '**': literal parts separated by '*', each '*' matching any part of a segment.
    It is matched without regular expressions, so that several '*' can not backtrack on a long segment.
    """

    def __init__(self, pattern: str, segment: str, placeholders: Mapping[str, str]):
        if segment in ("", ".", ".."):
            raise ValueError(f"invalid pattern '{pattern}': empty, '.' and '..' segments are not allowed")
        if "**" in segment:
            raise ValueError(f"invalid pattern '{pattern}': '**' must be a whole segment")

        parts = [""]
        position = 0
        for token in _PATTERN_TOKEN.finditer(segment):
            parts[-1] += _literal(pattern, segment[position : token.start()])
            if token.group(0) == "*":
                parts.append("")
            else:
                # the value of a placeholder is matched literally, whatever it contains
                parts[-1] += _placeholder_value(pattern, token.group(1), placeholders)
            position = token.end()
        parts[-1] += _literal(pattern, segment[position:])

        self._parts = tuple(parts)

    def matches(self, segment: str) -> bool:
        if len(self._parts) == 1:
            return segment == self._parts[0]

        first, *middle, last = self._parts
        if len(segment) < len(first) + len(last) or not segment.startswith(first) or not segment.endswith(last):
            return False

        # the leftmost occurrence of each part leaves the most room to the next ones
        position, end = len(first), len(segment) - len(last)
        for part in middle:
            index = segment.find(part, position, end)
            if index < 0:
                return False
            position = index + len(part)

        return True

    def __str__(self) -> str:
        return "*".join(self._parts)


def _literal(pattern: str, literal: str) -> str:
    if literal and _SEGMENT.fullmatch(literal) is None:
        raise ValueError(
            f"invalid pattern '{pattern}': only letters, digits, '.', '_', '@', '+', '-', '*' and placeholders "
            f"are allowed in a segment"
        )
    return literal


def _placeholder_value(pattern: str, name: str, placeholders: Mapping[str, str]) -> str:
    value = placeholders.get(name)
    if value is None:
        raise ValueError(
            f"invalid pattern '{pattern}': unknown placeholder '{{{name}}}', "
            f"supported placeholders are '{{org_name}}' and '{{github_id}}'"
        )
    return value


class _Pattern:
    """
    A pattern of the references allowed for an organization, matched segment by segment: '*' matches any part of
    a segment, '**' matches one or more segments at the end of the pattern, zero or more elsewhere, and the
    placeholders '{org_name}' and '{github_id}' match the values of the organization literally.
    """

    def __init__(self, pattern: str, placeholders: Mapping[str, str]):
        # None for '**'
        self._segments = [
            None if segment == "**" else _SegmentPattern(pattern, segment, placeholders)
            for segment in pattern.split("/")
        ]
        self._displayed = "/".join("**" if segment is None else str(segment) for segment in self._segments)

    def matches(self, segments: Sequence[str]) -> bool:
        # the positions in the segments reachable after matching the segments of the pattern seen so far, each
        # segment being matched at most once per segment of the pattern, whatever the number of '**'
        positions = {0}
        last_index = len(self._segments) - 1

        for index, pattern_segment in enumerate(self._segments):
            if len(positions) == 0:
                return False

            if pattern_segment is None:
                # '**' ending the pattern matches at least one segment, e.g. 'bots/{org_name}/**' not 'bots/{org_name}'
                first = min(positions) + (1 if index == last_index else 0)
                positions = set(range(first, len(segments) + 1))
            else:
                positions = {
                    position + 1
                    for position in positions
                    if position < len(segments) and pattern_segment.matches(segments[position])
                }

        return len(segments) in positions

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
            # 'item_id@field': access is granted per item, the provider expects a single '@'
            subject, separator, field = reference.partition("@")
            if not separator or not subject or not field or "@" in field:
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
