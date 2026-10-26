#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rich.markup import escape

from . import ApiUsage

if TYPE_CHECKING:
    from typing import Any

    from rich.console import Console

    from . import RateLimit, RequestStatistics

_TOP_ORGANIZATIONS = 10
_TOP_ENDPOINTS = 10

_REQUESTS_COLUMN = "Requests"
_QUOTA_COST_COLUMN = "Quota cost"
_COLUMNS = [_REQUESTS_COLUMN, "Retries", "Errors", "Cached", _QUOTA_COST_COLUMN]


class ApiUsageReport:
    """
    The usage of the GitHub apis during the execution of a command, overall and per organization.
    """

    def __init__(self, command: str | None = None) -> None:
        self.command = command
        self.total = ApiUsage()
        self.organizations: dict[str, ApiUsage] = {}
        self.outcome = "running"

        self._started_at = time.monotonic()
        self._finished_at: float | None = None

    def organization(self, github_id: str) -> ApiUsage:
        return self.organizations.setdefault(github_id, ApiUsage())

    def finish(self, outcome: str) -> None:
        self.outcome = outcome
        self._finished_at = time.monotonic()

    @property
    def duration(self) -> float:
        finished_at = self._finished_at if self._finished_at is not None else time.monotonic()
        return finished_at - self._started_at

    def rate_limits(self) -> list[RateLimit]:
        return sorted(self.total.combined().rate_limits.values(), key=lambda x: x.resource)

    def to_json(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "outcome": self.outcome,
            "duration_seconds": round(self.duration, 3),
            "total": self.total.combined().to_json(include_endpoints=False),
            "apis": {api: statistics.to_json() for api, statistics in self.total.items()},
            "rate_limits": {x.resource: x.to_json() for x in self.rate_limits()},
            "organizations": {
                github_id: {api: statistics.to_json(include_endpoints=False) for api, statistics in usage.items()}
                for github_id, usage in self.organizations.items()
            },
        }

    def write_json(self, file_name: str) -> None:
        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(self.to_json(), file, indent=2)
            file.write("\n")

    def print(self, console: Console, detailed: bool = False) -> None:
        """
        Prints the report, in detail all organizations and the top endpoints, otherwise only the top organizations.
        """
        from rich import box
        from rich.table import Table

        total = self.total.combined()

        console.print()
        console.print(f"[bold]GitHub API usage[/] · {self._title()}")

        table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        table.add_column("API")
        for column in _COLUMNS:
            table.add_column(column, justify="right")

        table.add_row("REST", *self._counters(self.total.rest), self._rest_quota_cost(self.total.rest))
        table.add_row("GraphQL", *self._counters(self.total.graphql), self._graphql_quota_cost(self.total.graphql))
        if self.total.web.total_requests > 0:
            table.add_row("Web UI", *self._counters(self.total.web), "—")
        table.add_section()
        table.add_row("Total", *self._counters(total), "", style="bold")

        console.print(table)

        details = self._details(total)
        if len(details) > 0:
            console.print()
            for label, value in details:
                # a detail without label continues the previous one
                prefix = f"{label}:" if label is not None else ""
                console.print(f"  {prefix:<13}{value}")

        self._print_organizations(console, show_all=detailed)

        if detailed:
            self._print_endpoints(console)

    def _details(self, total: RequestStatistics) -> list[tuple[str | None, str]]:
        details: list[tuple[str | None, str]] = []

        if total.error_count > 0:
            errors = sorted(total.errors.items(), key=lambda x: (-x[1], x[0]))
            details.append(("Errors", " · ".join(f"{escape(k)}: {v:,}" for k, v in errors)))

        if total.interrupted_requests > 0:
            details.append(("Interrupted", f"{total.interrupted_requests:,} request(s) cancelled"))

        if len(total.unsent_attempts) > 0:
            unsent = sorted(total.unsent_attempts.items(), key=lambda x: (-x[1], x[0]))
            failures = " · ".join(f"{escape(k)}: {v:,}" for k, v in unsent)
            details.append(("Not sent", f"{failures} (failed before being sent, not counted as requests)"))

        for index, line in enumerate(self._format_rate_limits()):
            details.append(("Rate limit" if index == 0 else None, line))

        return details

    def _title(self) -> str:
        parts = []

        if self.command is not None:
            parts.append(escape(self.command))

        organization_count = len(self.organizations)
        parts.append(f"{organization_count} organization{'' if organization_count == 1 else 's'}")
        parts.append(_format_duration(self.duration))

        match self.outcome:
            case "failed":
                parts.append("[red]failed[/]")
            case "interrupted":
                parts.append("[yellow]interrupted[/]")

        return " · ".join(parts)

    @staticmethod
    def _counters(statistics: RequestStatistics) -> list[str]:
        return [
            f"{statistics.total_requests:,}",
            f"{statistics.retried_requests:,}",
            f"{statistics.error_count:,}",
            f"{statistics.cached_responses:,}",
        ]

    @staticmethod
    def _rest_quota_cost(statistics: RequestStatistics) -> str:
        if len(statistics.quota_cost) == 0:
            return "—"

        # estimated from the responses, as GitHub does not report the cost of a REST request
        return "~" + ", ".join(f"{cost:,} {resource}" for resource, cost in sorted(statistics.quota_cost.items()))

    @staticmethod
    def _graphql_quota_cost(statistics: RequestStatistics) -> str:
        cost = sum(statistics.quota_cost.values())
        unpriced = statistics.unpriced_requests

        if cost == 0 and unpriced == 0:
            return "—"
        elif unpriced == 0:
            return f"{cost:,} points"
        else:
            return f"{cost:,} points + {unpriced:,} unpriced"

    @classmethod
    def _quota_cost(cls, usage: ApiUsage) -> str:
        costs = [cls._rest_quota_cost(usage.rest), cls._graphql_quota_cost(usage.graphql)]
        used_costs = [x for x in costs if x != "—"]
        return " · ".join(used_costs) if len(used_costs) > 0 else "—"

    def _format_rate_limits(self) -> list[str]:
        """Formats one line per rate limit resource, aligned as columns."""

        rate_limits = self.rate_limits()
        if len(rate_limits) == 0:
            return []

        quotas = [f"{x.remaining:,}/{x.limit:,}" for x in rate_limits]
        resource_width = max(len(x.resource) for x in rate_limits)
        quota_width = max(len(x) for x in quotas)

        result = []
        for rate_limit, quota in zip(rate_limits, quotas, strict=True):
            line = f"{escape(rate_limit.resource.ljust(resource_width))}  {quota.rjust(quota_width)} left"
            if rate_limit.reset > 0:
                line += f"  resets {datetime.fromtimestamp(rate_limit.reset, UTC):%H:%M} UTC"
            result.append(line)

        return result

    def _print_organizations(self, console: Console, show_all: bool) -> None:
        from rich import box
        from rich.table import Table

        # a single organization is accounted by the totals already
        if len(self.organizations) < 2:
            return

        organizations = sorted(
            ((github_id, usage, usage.combined()) for github_id, usage in self.organizations.items()),
            key=lambda x: (-x[2].total_requests, x[0]),
        )

        shown = organizations if show_all else organizations[:_TOP_ORGANIZATIONS]
        hidden = len(organizations) - len(shown)

        table = Table(
            title="Per organization" if hidden == 0 else f"Top {len(shown)} of {len(organizations)} organizations",
            title_justify="left",
            caption="use -v to list all organizations" if hidden > 0 else None,
            caption_justify="left",
            box=box.SIMPLE_HEAD,
            show_edge=False,
        )
        table.add_column("Organization")
        for column in _COLUMNS:
            table.add_column(column, justify="right")

        for github_id, usage, total in shown:
            table.add_row(escape(github_id), *self._counters(total), self._quota_cost(usage))

        console.print()
        console.print(table)

    def _print_endpoints(self, console: Console) -> None:
        from rich import box
        from rich.table import Table

        endpoints = [
            (endpoint, endpoint_statistics)
            for api in ["rest", "graphql"]
            for endpoint, endpoint_statistics in self.total.of(api).endpoints.items()
        ]

        if len(endpoints) == 0:
            return

        endpoints.sort(key=lambda x: (-x[1].requests, x[0]))

        table = Table(title="Top endpoints", title_justify="left", box=box.SIMPLE_HEAD, show_edge=False)
        table.add_column("Endpoint")
        table.add_column(_REQUESTS_COLUMN, justify="right")
        table.add_column(_QUOTA_COST_COLUMN, justify="right")

        for endpoint, endpoint_statistics in endpoints[:_TOP_ENDPOINTS]:
            table.add_row(escape(endpoint), f"{endpoint_statistics.requests:,}", f"{endpoint_statistics.quota_cost:,}")

        console.print()
        console.print(table)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes, seconds = divmod(round(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {seconds:02d}s"
