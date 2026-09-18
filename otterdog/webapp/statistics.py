#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

"""
Pull request statistics, computed from the data of GitHub.

Nothing is persisted in the database: GitHub is the single source of truth. What is kept in
redis is a per organization digest of the pull request activity of every single day, from
which every interval and time range is derived without querying GitHub again.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import TYPE_CHECKING, Any

from quart import current_app
from quart_redis import get_redis  # type: ignore

from otterdog.providers.github.exception import RateLimitExceededException
from otterdog.utils import unwrap
from otterdog.webapp.utils import current_utc_time, get_graphql_api_for_installation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from otterdog.webapp.db.models import InstallationModel

    # called with the number of organizations processed so far, their total number, and how
    # many of them had to be read from GitHub rather than being served from the cache
    ProgressCallback = Callable[[int, int, int], Awaitable[None]]

logger = getLogger(__name__)

# only pull requests targeting this branch of the configuration repository are taken into
# account, in line with what the FetchAllPullRequestsTask imports
BASE_REF = "main"

# number of organizations that are queried in parallel
_MAX_CONCURRENT_REQUESTS = 10

# stop querying further organizations once this many graphql points are left, leaving room
# for the webhook driven tasks which matter more than a statistics page
_RATE_LIMIT_RESERVE = 200

_ACTIVITY_INTERVALS = ("day", "week", "month")

# number of actors listed in the top openers / closers
_TOP_CONTRIBUTORS = 5

# number of organizations listed in the auto-merge breakdown
_TOP_ORGANIZATIONS = 10

# number of open pull requests listed as the oldest ones
_OLDEST_OPEN_PULL_REQUESTS = 10

# upper bound in days of every aging bucket, the last one catching everything above
_AGING_BUCKETS: tuple[tuple[str, float | None], ...] = (
    ("< 1 day", 1),
    ("1-3 days", 3),
    ("3-7 days", 7),
    ("7-30 days", 30),
    ("> 30 days", None),
)

# how long the state of a running collection is kept in redis, it is refreshed on every
# progress update and thus only expires if the worker running the job disappears
_JOB_TTL_IN_SECONDS = 600

# how long an already aggregated view is reused, short enough to stay in step with a refresh
# of the digests, long enough to make going back and forth between filters instant
_VIEW_TTL_IN_SECONDS = 60

# how long a request waits for a job it just started before answering "still running"
_FAST_PATH_TIMEOUT_IN_SECONDS = 1.5
_FAST_PATH_POLL_IN_SECONDS = 0.05

_APP_BOT_LOGIN: str | None = None
_APP_BOT_LOGIN_LOCK = asyncio.Lock()


@dataclasses.dataclass(frozen=True)
class PullRequestActivity:
    """Number of pull requests opened / merged / closed within a single time period."""

    period: str
    opened: int = 0
    merged: int = 0
    auto_merged: int = 0
    closed: int = 0
    cycle_time_median_hours: float | None = None
    cycle_time_p90_hours: float | None = None


@dataclasses.dataclass(frozen=True)
class Contributor:
    """Number of pull requests a single actor opened or closed."""

    login: str
    count: int
    bot: bool = False


@dataclasses.dataclass(frozen=True)
class OrganizationAutoMerge:
    """How many of the pull requests merged in an organization were merged by the app."""

    org_id: str
    merged: int
    auto_merged: int


@dataclasses.dataclass(frozen=True)
class CycleTime:
    """How long the pull requests of one population took between being opened and merged."""

    label: str
    count: int
    median_hours: float | None = None
    p90_hours: float | None = None


@dataclasses.dataclass(frozen=True)
class AgingBucket:
    """Number of currently open pull requests whose age falls into one bucket."""

    label: str
    count: int


@dataclasses.dataclass(frozen=True)
class OpenPullRequest:
    """A pull request that is open right now, with the age it has reached."""

    org_id: str
    number: int
    title: str
    url: str
    author: str | None
    draft: bool
    age_days: float


@dataclasses.dataclass(frozen=True)
class PullRequestStatistics:
    activities: list[PullRequestActivity]
    open_at_start: int
    top_openers: list[Contributor]
    top_closers: list[Contributor]
    organizations: list[OrganizationAutoMerge]
    cycle_times: list[CycleTime] = dataclasses.field(default_factory=list)
    open_aging: list[AgingBucket] = dataclasses.field(default_factory=list)
    oldest_open: list[OpenPullRequest] = dataclasses.field(default_factory=list)
    cycle_time_median_hours: float | None = None
    cycle_time_p90_hours: float | None = None
    failed_organizations: list[str] = dataclasses.field(default_factory=list)
    rate_limited: bool = False


def _as_naive_utc(moment: datetime) -> datetime:
    """Strips the timezone info to keep all time calculations in UTC."""

    return moment if moment.tzinfo is None else moment.astimezone(UTC).replace(tzinfo=None)


def _truncate_to_interval(moment: datetime, interval: str) -> datetime:
    """Truncates a datetime to the start of the period it belongs to."""

    day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    match interval:
        case "day":
            return day
        case "week":
            return day - timedelta(days=day.weekday())
        case "month":
            return day.replace(day=1)
        case _:
            raise RuntimeError(f"unexpected interval '{interval}'")


def _next_period(moment: datetime, interval: str) -> datetime:
    match interval:
        case "day":
            return moment + timedelta(days=1)
        case "week":
            return moment + timedelta(days=7)
        case "month":
            return (
                moment.replace(year=moment.year + 1, month=1)
                if moment.month == 12
                else moment.replace(month=moment.month + 1)
            )
        case _:
            raise RuntimeError(f"unexpected interval '{interval}'")


def _parse_timestamp(value: str | None) -> datetime | None:
    return None if value is None else _as_naive_utc(datetime.fromisoformat(value))


def _percentile(values: list[float], percentile: float) -> float | None:
    """Nearest rank percentile, which needs no interpolation and is stable on tiny samples."""

    if not values:
        return None

    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def _round_hours(hours: float | None) -> float | None:
    return None if hours is None else round(hours, 1)


def normalize_login(login: str | None) -> str | None:
    """
    Normalizes the login of an actor so that a bot can be recognized in either api.

    The graphql api reports the login of a bot as the plain slug of the app, e.g. 'otterdog',
    while the rest api appends a suffix and reports 'otterdog[bot]' for the very same actor.
    """

    return None if login is None else login.removesuffix("[bot]").lower()


async def get_app_bot_login() -> str:
    """
    Returns the login of the bot associated with the github app, e.g. 'otterdog'.

    Pull requests merged by the app carry this login as their merger, which is what makes a
    merge distinguishable from a manual one without keeping any state of our own.
    """

    global _APP_BOT_LOGIN

    async with _APP_BOT_LOGIN_LOCK:
        if _APP_BOT_LOGIN is None:
            from otterdog.webapp.utils import get_rest_api_for_app

            app = await get_rest_api_for_app().app.get_authenticated_app()
            _APP_BOT_LOGIN = app["slug"]
            logger.info("the github app merges pull requests as '%s[bot]'", _APP_BOT_LOGIN)

    return _APP_BOT_LOGIN


def _actor_of(node: dict[str, Any] | None) -> tuple[str, bool] | None:
    """Returns the login of an actor together with whether it is a bot, if it is known at all."""

    login = (node or {}).get("login")
    if not login:
        # the account may have been deleted, in which case github reports no actor at all
        return None

    return login, (node or {}).get("__typename") == "Bot"


def _closing_actor(pull_request: dict[str, Any]) -> tuple[str, bool] | None:
    """
    Returns the actor that closed a pull request.

    For a merged pull request this is whoever merged it, otherwise it is the actor of the
    closing event, which is the only place where github reports it.
    """

    if pull_request.get("mergedAt") is not None:
        return _actor_of(pull_request.get("mergedBy"))

    events = (pull_request.get("timelineItems") or {}).get("nodes") or []
    return _actor_of(events[-1].get("actor")) if events else None


def _empty_day() -> dict[str, Any]:
    return {
        "opened": 0,
        "merged": 0,
        "auto_merged": 0,
        "closed": 0,
        # kept apart, as a pull request merged by the app and one merged by hand have nothing
        # comparable about how long they took
        "durations_auto": [],
        "durations_manual": [],
        "openers": {},
        "closers": {},
    }


def build_organization_digest(
    org_id: str,
    pull_requests: list[dict[str, Any]],
    bot_login: str,
) -> dict[str, Any]:
    """
    Condenses the pull requests of one organization into per day counters.

    Every interval and time range offered by the ui is an aggregation of these days, so a single
    digest per organization serves all of them and only has to be refreshed once a day.

    The pull requests still open are kept as they are: their age has to be measured against the
    moment the page is looked at, not against the moment the digest was built.
    """

    days: dict[str, dict[str, Any]] = {}
    bots: set[str] = set()
    open_pull_requests: list[dict[str, Any]] = []

    def day_of(moment: datetime) -> dict[str, Any]:
        return days.setdefault(moment.date().isoformat(), _empty_day())

    def count_actor(counters: dict[str, int], actor: tuple[str, bool] | None) -> None:
        if actor is None:
            return

        login, is_bot = actor
        counters[login] = counters.get(login, 0) + 1
        if is_bot:
            bots.add(login)

    for pull_request in pull_requests:
        created_at = unwrap(_parse_timestamp(pull_request["createdAt"]))
        merged_at = _parse_timestamp(pull_request["mergedAt"])
        closed_at = _parse_timestamp(pull_request["closedAt"])

        day = day_of(created_at)
        day["opened"] += 1
        count_actor(day["openers"], _actor_of(pull_request.get("author")))

        if merged_at is not None:
            day = day_of(merged_at)
            day["merged"] += 1
            count_actor(day["closers"], _closing_actor(pull_request))

            duration = int((merged_at - created_at).total_seconds())
            merged_by = pull_request.get("mergedBy") or {}

            if normalize_login(merged_by.get("login")) == normalize_login(bot_login):
                day["auto_merged"] += 1
                day["durations_auto"].append(duration)
            else:
                day["durations_manual"].append(duration)
        elif closed_at is not None:
            day = day_of(closed_at)
            day["closed"] += 1
            count_actor(day["closers"], _closing_actor(pull_request))
        else:
            author = _actor_of(pull_request.get("author"))
            open_pull_requests.append(
                {
                    "org_id": org_id,
                    "number": pull_request["number"],
                    "title": pull_request.get("title") or "",
                    "url": pull_request.get("url") or "",
                    "draft": bool(pull_request.get("isDraft")),
                    "author": author[0] if author is not None else None,
                    "created_at": created_at.isoformat(),
                }
            )

    return {
        "org_id": org_id,
        "open_now": len(open_pull_requests),
        "open": open_pull_requests,
        "days": days,
        "bots": sorted(bots),
        "collected_at": current_utc_time().isoformat(),
    }


def _digest_key(org_id: str) -> str:
    # the version guards against reading a digest written in an older, incompatible format
    return f"pull-request-activity:org:v3:{org_id}"


async def _collect_organization_digest(installation: InstallationModel, bot_login: str) -> dict[str, Any]:
    """Retrieves the complete pull request history of the configuration repository of one org."""

    org_id = installation.github_id
    config_repo = unwrap(installation.config_repo)

    graphql_api = await get_graphql_api_for_installation(installation.installation_id)
    try:
        pull_requests = await graphql_api.get_pull_requests(org_id, config_repo, BASE_REF)

        remaining = graphql_api.rate_limit_remaining
        if remaining is not None and remaining < _RATE_LIMIT_RESERVE:
            raise RateLimitExceededException(
                f"only {remaining} graphql points left after querying org '{org_id}'",
                graphql_api.rate_limit_reset_at,
            )

        return build_organization_digest(org_id, pull_requests, bot_login)
    finally:
        await graphql_api.close()


async def _read_cached_digests(
    installations: list[InstallationModel],
) -> tuple[list[dict[str, Any]], list[InstallationModel]]:
    """
    Reads the cached digests of all given organizations in a single round trip.

    Asking redis once rather than once per organization is what keeps a fully cached view at a
    handful of milliseconds even with hundreds of organizations.
    """

    ttl = current_app.config["PULL_REQUEST_STATISTICS_CACHE_TTL"]
    if ttl <= 0 or not installations:
        return [], list(installations)

    redis = get_redis()
    values = await redis.mget([_digest_key(x.github_id) for x in installations])

    cached = []
    missing = []

    for installation, value in zip(installations, values, strict=True):
        if value is None:
            missing.append(installation)
        else:
            cached.append(json.loads(value))

    return cached, missing


async def _store_digest(org_id: str, digest: dict[str, Any]) -> None:
    ttl = current_app.config["PULL_REQUEST_STATISTICS_CACHE_TTL"]
    if ttl > 0:
        await get_redis().set(_digest_key(org_id), json.dumps(digest), ex=ttl)


async def collect_organization_digests(
    installations: list[InstallationModel],
    bot_login: str,
    progress: ProgressCallback | None = None,
    refresh: bool = False,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    """
    Returns the digests of the given organizations, along with those that could not be read.

    Once the rate limit is exhausted every further request would fail as well, so the remaining
    organizations are left alone and reported as failed rather than hammering GitHub.
    """

    total = len(installations)

    digests: list[dict[str, Any]]

    if refresh:
        digests, missing = [], list(installations)
    else:
        digests, missing = await _read_cached_digests(installations)

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)
    processed = len(digests)
    fetched = 0
    rate_limited = False

    if progress is not None:
        await progress(processed, total, fetched)

    async def collect(installation: InstallationModel) -> dict[str, Any] | None:
        nonlocal processed, fetched, rate_limited

        async with semaphore:
            try:
                if rate_limited:
                    return None

                digest = await _collect_organization_digest(installation, bot_login)
                await _store_digest(installation.github_id, digest)
                fetched += 1

                return digest
            except RateLimitExceededException as ex:
                if rate_limited is False:
                    logger.warning("the github rate limit is exhausted, skipping the remaining organizations: %s", ex)
                rate_limited = True
                return None
            except Exception as ex:
                # a single organization failing should not take down the whole statistics view
                logger.warning("failed retrieving pull requests for org '%s': %s", installation.github_id, ex)
                return None
            finally:
                processed += 1
                if progress is not None:
                    await progress(processed, total, fetched)

    results = await asyncio.gather(*[collect(x) for x in missing])

    digests.extend(x for x in results if x is not None)
    failed = [installation.github_id for installation, result in zip(missing, results, strict=True) if result is None]

    return digests, failed, rate_limited


def open_pull_request_aging(
    digests: list[dict[str, Any]],
    now: datetime,
) -> tuple[list[AgingBucket], list[OpenPullRequest]]:
    """
    Buckets the currently open pull requests by age and returns the oldest ones.

    The age is measured against now rather than against the moment the digest was built, so a
    stale digest reports an age that is still correct.
    """

    counts = dict.fromkeys((label for label, _ in _AGING_BUCKETS), 0)
    open_pull_requests = []

    for digest in digests:
        for pull_request in digest.get("open", []):
            created_at = _parse_timestamp(pull_request["created_at"])
            if created_at is None:
                continue

            age_days = (now - created_at).total_seconds() / 86400

            for label, upper_bound in _AGING_BUCKETS:
                if upper_bound is None or age_days < upper_bound:
                    counts[label] += 1
                    break

            open_pull_requests.append(
                OpenPullRequest(
                    org_id=pull_request.get("org_id") or digest["org_id"],
                    number=pull_request["number"],
                    title=pull_request.get("title") or "",
                    url=pull_request.get("url") or "",
                    author=pull_request.get("author"),
                    draft=bool(pull_request.get("draft")),
                    age_days=round(age_days, 1),
                )
            )

    open_pull_requests.sort(key=lambda x: (-x.age_days, x.org_id, x.number))

    return (
        [AgingBucket(label=label, count=counts[label]) for label, _ in _AGING_BUCKETS],
        open_pull_requests[:_OLDEST_OPEN_PULL_REQUESTS],
    )


def _top_contributors(counter: Counter[str], bots: set[str]) -> list[Contributor]:
    return [
        Contributor(login=login, count=count, bot=login in bots)
        for login, count in counter.most_common(_TOP_CONTRIBUTORS)
    ]


def aggregate_digests(
    digests: list[dict[str, Any]],
    interval: str,
    since: datetime | None = None,
    failed_organizations: list[str] | None = None,
    rate_limited: bool = False,
) -> PullRequestStatistics:
    """
    Aggregates per organization digests into the series shown by the ui.

    This is pure arithmetic over already collected data, which is what makes switching the
    interval or the time range free of any request to GitHub.
    """

    if interval not in _ACTIVITY_INTERVALS:
        raise RuntimeError(f"unexpected interval '{interval}'")

    naive_since = None if since is None else _truncate_to_interval(_as_naive_utc(since), "day")

    counters: dict[datetime, dict[str, Any]] = {}
    openers: Counter[str] = Counter()
    closers: Counter[str] = Counter()
    bots: set[str] = set()
    organizations: list[OrganizationAutoMerge] = []
    earliest: datetime | None = None
    open_now = 0

    for digest in digests:
        open_now += digest.get("open_now", 0)
        bots.update(digest.get("bots", []))

        org_merged = 0
        org_auto_merged = 0

        for day, activity in digest.get("days", {}).items():
            moment = datetime.fromisoformat(day)

            if earliest is None or moment < earliest:
                earliest = moment

            if naive_since is not None and moment < naive_since:
                continue

            counter = counters.setdefault(_truncate_to_interval(moment, interval), _empty_day())

            for field in ("opened", "merged", "auto_merged", "closed"):
                counter[field] += activity.get(field, 0)

            counter["durations_auto"].extend(activity.get("durations_auto", []))
            counter["durations_manual"].extend(activity.get("durations_manual", []))

            for login, count in activity.get("openers", {}).items():
                openers[login] += count

            for login, count in activity.get("closers", {}).items():
                closers[login] += count

            org_merged += activity.get("merged", 0)
            org_auto_merged += activity.get("auto_merged", 0)

        if org_merged > 0:
            organizations.append(
                OrganizationAutoMerge(org_id=digest["org_id"], merged=org_merged, auto_merged=org_auto_merged)
            )

    now = _truncate_to_interval(_as_naive_utc(current_utc_time()), interval)

    if naive_since is not None:
        start = _truncate_to_interval(naive_since, interval)
    elif earliest is not None:
        start = _truncate_to_interval(earliest, interval)
    else:
        start = now

    activities = []
    auto_durations: list[float] = []
    manual_durations: list[float] = []
    period = start

    while period <= now:
        counter = counters.get(period, _empty_day())

        period_auto = [x / 3600 for x in counter["durations_auto"]]
        period_manual = [x / 3600 for x in counter["durations_manual"]]
        durations = period_auto + period_manual

        auto_durations.extend(period_auto)
        manual_durations.extend(period_manual)

        activities.append(
            PullRequestActivity(
                period=period.date().isoformat(),
                opened=counter["opened"],
                merged=counter["merged"],
                auto_merged=counter["auto_merged"],
                closed=counter["closed"],
                cycle_time_median_hours=_round_hours(_percentile(durations, 0.5)),
                cycle_time_p90_hours=_round_hours(_percentile(durations, 0.9)),
            )
        )
        period = _next_period(period, interval)

    # the number of pull requests being open at the end of the last period is known, so the
    # backlog of all earlier periods is obtained by walking backwards through the activity
    open_at_start = open_now
    for activity in reversed(activities):
        open_at_start += activity.merged + activity.closed - activity.opened

    organizations.sort(key=lambda x: (-x.merged, x.org_id))

    aging, oldest_open = open_pull_request_aging(digests, _as_naive_utc(current_utc_time()))
    all_durations = auto_durations + manual_durations

    cycle_times = [
        CycleTime(
            label="Auto-merge",
            count=len(auto_durations),
            median_hours=_round_hours(_percentile(auto_durations, 0.5)),
            p90_hours=_round_hours(_percentile(auto_durations, 0.9)),
        ),
        CycleTime(
            label="Manual merge",
            count=len(manual_durations),
            median_hours=_round_hours(_percentile(manual_durations, 0.5)),
            p90_hours=_round_hours(_percentile(manual_durations, 0.9)),
        ),
    ]

    return PullRequestStatistics(
        activities=activities,
        open_at_start=open_at_start,
        top_openers=_top_contributors(openers, bots),
        top_closers=_top_contributors(closers, bots),
        organizations=organizations[:_TOP_ORGANIZATIONS],
        cycle_times=cycle_times,
        open_aging=aging,
        oldest_open=oldest_open,
        cycle_time_median_hours=_round_hours(_percentile(all_durations, 0.5)),
        cycle_time_p90_hours=_round_hours(_percentile(all_durations, 0.9)),
        failed_organizations=failed_organizations or [],
        rate_limited=rate_limited,
    )


async def _installations_for(org_id: str | None) -> list[InstallationModel]:
    from otterdog.webapp.db.service import get_active_installations, get_installation_by_github_id

    if org_id is None:
        return await get_active_installations()

    installation = await get_installation_by_github_id(org_id)
    return [installation] if installation is not None and installation.config_repo is not None else []


async def get_pull_request_activity(
    interval: str = "month",
    since: datetime | None = None,
    org_id: str | None = None,
    progress: ProgressCallback | None = None,
) -> PullRequestStatistics:
    """
    Aggregates the pull request activity per time period, based on the data of GitHub.

    A pull request counts as auto-merged if it has been merged by the bot of the github app,
    which is exactly what happens when a MergePullRequestTask performs the merge.
    """

    bot_login = await get_app_bot_login()
    installations = await _installations_for(org_id)

    digests, failed, rate_limited = await collect_organization_digests(installations, bot_login, progress)

    return aggregate_digests(digests, interval, since, failed, rate_limited)


async def refresh_organization_digests() -> None:
    """
    Refreshes the cached digest of every active organization.

    Meant to be triggered out of band, e.g. by /internal/init, so that opening the statistics
    page never has to wait for hundreds of organizations to be queried.
    """

    bot_login = await get_app_bot_login()
    installations = await _installations_for(None)

    logger.info("refreshing the pull request digests of %d organization(s)", len(installations))

    digests, failed, rate_limited = await collect_organization_digests(installations, bot_login, refresh=True)

    logger.info(
        "refreshed the pull request digests of %d organization(s), %d failed%s",
        len(digests),
        len(failed),
        ", the rate limit was exhausted" if rate_limited else "",
    )


def statistics_to_json(statistics: PullRequestStatistics, interval: str, time_range: str) -> dict[str, Any]:
    return {
        "interval": interval,
        "range": time_range,
        "open_at_start": statistics.open_at_start,
        "data": [dataclasses.asdict(x) for x in statistics.activities],
        "top_openers": [dataclasses.asdict(x) for x in statistics.top_openers],
        "top_closers": [dataclasses.asdict(x) for x in statistics.top_closers],
        "organizations": [dataclasses.asdict(x) for x in statistics.organizations],
        "cycle_times": [dataclasses.asdict(x) for x in statistics.cycle_times],
        "open_aging": [dataclasses.asdict(x) for x in statistics.open_aging],
        "oldest_open": [dataclasses.asdict(x) for x in statistics.oldest_open],
        "cycle_time_median_hours": statistics.cycle_time_median_hours,
        "cycle_time_p90_hours": statistics.cycle_time_p90_hours,
        "failed_organizations": statistics.failed_organizations,
        "rate_limited": statistics.rate_limited,
    }


def _job_key(interval: str, time_range: str, org_id: str | None) -> str:
    return f"pull-request-activity-job:{org_id or 'all'}:{interval}:{time_range}"


def _view_key(interval: str, time_range: str, org_id: str | None) -> str:
    return f"pull-request-activity-view:{org_id or 'all'}:{interval}:{time_range}"


async def _run_pull_request_activity_job(
    key: str,
    interval: str,
    time_range: str,
    since: datetime | None,
    org_id: str | None,
) -> None:
    redis = get_redis()

    async def store(state: dict[str, Any]) -> None:
        await redis.set(key, json.dumps(state), ex=_JOB_TTL_IN_SECONDS)

    async def progress(processed: int, total: int, fetched: int) -> None:
        await store({"status": "running", "processed": processed, "total": total, "fetched": fetched})

    try:
        statistics = await get_pull_request_activity(interval, since, org_id, progress)
        result = statistics_to_json(statistics, interval, time_range)

        # aggregating hundreds of digests is pure cpu work, but not free: going back to a filter
        # that was just looked at should not pay for it again
        if _VIEW_TTL_IN_SECONDS > 0:
            await redis.set(_view_key(interval, time_range, org_id), json.dumps(result), ex=_VIEW_TTL_IN_SECONDS)

        await store({"status": "done", "result": result})
    except Exception as ex:
        logger.exception("failed collecting pull request statistics for key '%s'", key, exc_info=ex)
        await store({"status": "failed", "error": str(ex)})


async def _wait_for_job(key: str, timeout: float) -> dict[str, Any] | None:
    """Waits for a freshly started job to reach a terminal state, up to the given timeout."""

    redis = get_redis()
    deadline = asyncio.get_running_loop().time() + timeout

    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(_FAST_PATH_POLL_IN_SECONDS)

        state = await redis.get(key)
        if state is None:
            return None

        state = json.loads(state)
        if state.get("status") in ("done", "failed"):
            await redis.delete(key)
            return state

    return None


async def get_pull_request_activity_job(
    interval: str,
    time_range: str,
    since: datetime | None,
    org_id: str | None,
) -> dict[str, Any]:
    """
    Returns the state of the collection of the pull request activity, starting it if needed.

    Collecting the data of all organizations takes far longer than any reverse proxy is willing
    to keep a request open, so the work happens in the background while the client polls this
    with short requests. The state is kept in redis and thus shared between all workers.
    """

    redis = get_redis()

    cached_view = await redis.get(_view_key(interval, time_range, org_id))
    if cached_view is not None:
        return {"status": "done", "result": json.loads(cached_view)}

    key = _job_key(interval, time_range, org_id)
    initial_state = {"status": "running", "processed": 0, "total": 0, "fetched": 0}

    # claiming the key atomically makes sure that only one worker starts the collection
    claimed = await redis.set(key, json.dumps(initial_state), nx=True, ex=_JOB_TTL_IN_SECONDS)
    if claimed:
        logger.info("collecting pull request statistics for key '%s'", key)
        current_app.add_background_task(_run_pull_request_activity_job, key, interval, time_range, since, org_id)

        # when every digest is cached the whole job takes milliseconds, waiting for it here saves
        # the client a further round trip and the page appears at once
        finished_state = await _wait_for_job(key, _FAST_PATH_TIMEOUT_IN_SECONDS)
        return finished_state if finished_state is not None else initial_state

    state = await redis.get(key)
    if state is None:
        # the job expired between the two calls, let the client ask again
        return initial_state

    state = json.loads(state)

    # a terminal state is only of interest once, dropping it lets a later request start over
    if state.get("status") in ("done", "failed"):
        await redis.delete(key)

    return state
