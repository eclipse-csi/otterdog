#  *******************************************************************************
#  Copyright (c) 2026 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from datetime import UTC, datetime

import pytest


@pytest.fixture
def fixed_now(monkeypatch):
    from otterdog.webapp import statistics

    monkeypatch.setattr(statistics, "current_utc_time", lambda: datetime(2026, 3, 11, 12, 0, tzinfo=UTC))


def _pull_request(
    created_at, closed_at=None, merged_at=None, merged_by=None, author=None, closed_by=None, number=1, title="a change"
):
    pull_request = {
        "number": number,
        "title": title,
        "url": f"https://github.com/eclipse-test/.eclipsefdn/pull/{number}",
        "isDraft": False,
        "createdAt": created_at,
        "updatedAt": merged_at or closed_at or created_at,
        "closedAt": closed_at,
        "mergedAt": merged_at,
        "mergedBy": None if merged_by is None else {"login": merged_by[0], "__typename": merged_by[1]},
        "author": None if author is None else {"login": author, "__typename": "User"},
    }

    if closed_by is not None:
        pull_request["timelineItems"] = {"nodes": [{"actor": {"login": closed_by, "__typename": "User"}}]}

    return pull_request


def _digest(pull_requests, org_id="eclipse-test", bot_login="otterdog"):
    from otterdog.webapp.statistics import build_organization_digest

    return build_organization_digest(org_id, pull_requests, bot_login)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ("day", datetime(2026, 3, 11, tzinfo=UTC)),
        # 2026-03-11 is a wednesday, the week starts on monday
        ("week", datetime(2026, 3, 9, tzinfo=UTC)),
        ("month", datetime(2026, 3, 1, tzinfo=UTC)),
    ],
)
def test_truncate_to_interval(interval, expected):
    from otterdog.webapp.statistics import _truncate_to_interval

    assert _truncate_to_interval(datetime(2026, 3, 11, 17, 42, 13, tzinfo=UTC), interval) == expected


@pytest.mark.parametrize(
    ("interval", "moment", "expected"),
    [
        ("day", datetime(2026, 3, 11, tzinfo=UTC), datetime(2026, 3, 12, tzinfo=UTC)),
        ("week", datetime(2026, 3, 9, tzinfo=UTC), datetime(2026, 3, 16, tzinfo=UTC)),
        ("month", datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 4, 1, tzinfo=UTC)),
        # rolling over to the next year
        ("month", datetime(2026, 12, 1, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
    ],
)
def test_next_period(interval, moment, expected):
    from otterdog.webapp.statistics import _next_period

    assert _next_period(moment, interval) == expected


def test_unsupported_interval():
    from otterdog.webapp.statistics import _next_period, _truncate_to_interval

    moment = datetime(2026, 3, 11, tzinfo=UTC)

    with pytest.raises(RuntimeError):
        _truncate_to_interval(moment, "year")

    with pytest.raises(RuntimeError):
        _next_period(moment, "year")


@pytest.mark.parametrize(
    ("values", "percentile", "expected"),
    [
        ([], 0.5, None),
        ([5.0], 0.9, 5.0),
        ([1.0, 2.0, 3.0, 4.0], 0.5, 2.0),
        ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], 0.9, 9.0),
    ],
)
def test_percentile(values, percentile, expected):
    from otterdog.webapp.statistics import _percentile

    assert _percentile(values, percentile) == expected


def test_aggregate_pull_request_activity(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        # opened and merged within the window, by the app and by a user
        _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("otterdog", "Bot")),
        _pull_request("2026-03-09T09:00:00Z", "2026-03-10T09:00:00Z", "2026-03-10T09:00:00Z", ("some-user", "User")),
        # closed without being merged
        _pull_request("2026-03-10T10:00:00Z", "2026-03-11T10:00:00Z"),
        # still open
        _pull_request("2026-03-11T11:00:00Z"),
        # opened before the window, merged within it
        _pull_request("2026-03-01T08:00:00Z", "2026-03-11T08:00:00Z", "2026-03-11T08:00:00Z", ("otterdog", "Bot")),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert [x.period for x in statistics.activities] == ["2026-03-09", "2026-03-10", "2026-03-11"]
    assert [x.opened for x in statistics.activities] == [2, 1, 1]
    assert [x.merged for x in statistics.activities] == [0, 2, 1]
    assert [x.auto_merged for x in statistics.activities] == [0, 1, 1]
    assert [x.closed for x in statistics.activities] == [0, 0, 1]

    # only the pull request opened before the window was open when it started
    assert statistics.open_at_start == 1


def test_aggregate_backlog_ends_at_the_current_number_of_open_pull_requests(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("otterdog", "Bot")),
        _pull_request("2026-03-10T10:00:00Z"),
        _pull_request("2026-03-11T11:00:00Z"),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    # walking forward through the activity, as the chart does, must end at open_now
    backlog = statistics.open_at_start
    for activity in statistics.activities:
        backlog += activity.opened - activity.merged - activity.closed

    assert backlog == 2


def test_aggregate_without_time_range_starts_at_the_oldest_pull_request(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-01-15T08:00:00Z", "2026-02-02T08:00:00Z", "2026-02-02T08:00:00Z", ("a-user", "User"))
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month")

    assert [x.period for x in statistics.activities] == ["2026-01-01", "2026-02-01", "2026-03-01"]
    assert [x.opened for x in statistics.activities] == [1, 0, 0]
    assert [x.merged for x in statistics.activities] == [0, 1, 0]
    assert [x.auto_merged for x in statistics.activities] == [0, 0, 0]


@pytest.mark.parametrize("login", ["otterdog", "otterdog[bot]", "Otterdog"])
def test_a_pull_request_merged_by_the_app_counts_as_auto_merged(fixed_now, login):
    """The graphql api reports a bot as 'otterdog', the rest api as 'otterdog[bot]'."""

    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", (login, "Bot"))
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert [x.merged for x in statistics.activities] == [0, 1, 0]
    assert [x.auto_merged for x in statistics.activities] == [0, 1, 0]


def test_a_pull_request_merged_by_a_user_does_not_count_as_auto_merged(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("some-user", "User"))
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert [x.merged for x in statistics.activities] == [0, 1, 0]
    assert [x.auto_merged for x in statistics.activities] == [0, 0, 0]


def test_top_openers_and_closers(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request(
            "2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("otterdog", "Bot"), "alice"
        ),
        _pull_request(
            "2026-03-09T09:00:00Z", "2026-03-10T09:00:00Z", "2026-03-10T09:00:00Z", ("otterdog", "Bot"), "alice"
        ),
        _pull_request("2026-03-09T10:00:00Z", "2026-03-10T10:00:00Z", "2026-03-10T10:00:00Z", ("carol", "User"), "bob"),
        # closed without being merged, the actor of the closing event is the one closing it
        _pull_request("2026-03-10T08:00:00Z", "2026-03-11T08:00:00Z", author="bob", closed_by="carol"),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert sorted((x.login, x.count) for x in statistics.top_openers) == [("alice", 2), ("bob", 2)]
    # both closed two pull requests, the order between ties is not meaningful
    assert sorted((x.login, x.count) for x in statistics.top_closers) == [("carol", 2), ("otterdog", 2)]
    assert [(x.login, x.bot) for x in statistics.top_closers if x.login == "otterdog"] == [("otterdog", True)]


def test_top_contributors_are_limited_to_five(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [_pull_request("2026-03-09T08:00:00Z", author=f"user-{index}") for index in range(8)]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert len(statistics.top_openers) == 5


def test_pull_requests_without_an_author_are_ignored_in_the_top_contributors(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    # github reports no actor at all once an account has been deleted
    statistics = aggregate_digests(
        [_digest([_pull_request("2026-03-09T08:00:00Z")])],
        "day",
        datetime(2026, 3, 9, tzinfo=UTC),
    )

    assert statistics.top_openers == []
    assert [x.opened for x in statistics.activities] == [1, 0, 0]


def test_cycle_time_is_reported_per_period_and_overall(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        # merged after 2 hours, 4 hours and 10 hours on the same day
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T02:00:00Z", "2026-03-10T02:00:00Z", ("a-user", "User")),
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T04:00:00Z", "2026-03-10T04:00:00Z", ("a-user", "User")),
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T10:00:00Z", "2026-03-10T10:00:00Z", ("a-user", "User")),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert [x.cycle_time_median_hours for x in statistics.activities] == [None, 4.0, None]
    assert [x.cycle_time_p90_hours for x in statistics.activities] == [None, 10.0, None]
    assert statistics.cycle_time_median_hours == 4.0
    assert statistics.cycle_time_p90_hours == 10.0


def test_auto_merge_rate_is_reported_per_organization(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    first = _digest(
        [
            _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("otterdog", "Bot")),
            _pull_request("2026-03-09T09:00:00Z", "2026-03-10T09:00:00Z", "2026-03-10T09:00:00Z", ("a-user", "User")),
        ],
        org_id="org-with-two",
    )
    second = _digest(
        [_pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("a-user", "User"))],
        org_id="org-with-one",
    )
    # an organization without any merge is not listed at all
    third = _digest([_pull_request("2026-03-09T08:00:00Z")], org_id="org-without-merge")

    statistics = aggregate_digests([second, first, third], "day", datetime(2026, 3, 9, tzinfo=UTC))

    assert [(x.org_id, x.merged, x.auto_merged) for x in statistics.organizations] == [
        ("org-with-two", 2, 1),
        ("org-with-one", 1, 0),
    ]


def test_switching_the_interval_reuses_the_same_digest(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-02T08:00:00Z", "2026-03-03T08:00:00Z", "2026-03-03T08:00:00Z", ("otterdog", "Bot")),
        _pull_request("2026-03-09T08:00:00Z", "2026-03-10T08:00:00Z", "2026-03-10T08:00:00Z", ("otterdog", "Bot")),
    ]
    digests = [_digest(pull_requests)]

    daily = aggregate_digests(digests, "day", datetime(2026, 3, 1, tzinfo=UTC))
    monthly = aggregate_digests(digests, "month", datetime(2026, 3, 1, tzinfo=UTC))

    assert sum(x.merged for x in daily.activities) == sum(x.merged for x in monthly.activities) == 2
    assert len(monthly.activities) == 1


def test_failed_organizations_are_reported(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    statistics = aggregate_digests([], "month", None, ["org-a", "org-b"], rate_limited=True)

    assert statistics.failed_organizations == ["org-a", "org-b"]
    assert statistics.rate_limited is True


@pytest.mark.parametrize("parameters", ["interval=year", "range=100y"])
async def test_statistics_endpoints_reject_unsupported_parameters(app, parameters):
    """
    Exercised through a request context rather than a test client.

    Booting the app would run its startup hooks, which expect a running mongodb.
    """

    from otterdog.webapp.api.routes import pullrequest_statistics, pullrequest_statistics_progress

    for view in (pullrequest_statistics, pullrequest_statistics_progress):
        async with app.test_request_context(f"/api/pullrequests/statistics?{parameters}"):
            body, status = await view()

            assert status == 400
            assert "unsupported" in body["error"]


def _ranges_offered_by_the_template() -> list[str]:
    import pathlib
    import re

    template = pathlib.Path("otterdog/webapp/templates/home/pullrequests.html").read_text()
    select = re.search(r'id="stats-range">(.*?)</select>', template, re.DOTALL)
    assert select is not None

    return re.findall(r'value="([^"]+)"', select.group(1))


@pytest.mark.parametrize("time_range", _ranges_offered_by_the_template())
def test_statistics_endpoint_accepts_every_offered_range(time_range):
    """Every range of the select must be known to the api, an unknown one answers with a 400."""

    from otterdog.webapp.api.routes import _STATISTICS_RANGES, _validate_statistics_parameters

    assert time_range in _STATISTICS_RANGES
    assert _validate_statistics_parameters("month", time_range) is None


def test_aggregating_many_organizations_stays_fast(fixed_now):
    """Guards the aggregation against turning quadratic as the number of organizations grows."""

    import time

    from otterdog.webapp.statistics import aggregate_digests

    digests = [
        _digest(
            [
                _pull_request(
                    f"2026-0{1 + index % 2}-1{index % 9}T08:00:00Z",
                    f"2026-0{2 + index % 2}-1{index % 9}T08:00:00Z",
                    f"2026-0{2 + index % 2}-1{index % 9}T08:00:00Z",
                    ("otterdog", "Bot"),
                    f"user-{index % 20}",
                )
                for index in range(20)
            ],
            org_id=f"org-{org}",
        )
        for org in range(400)
    ]

    started_at = time.perf_counter()
    statistics = aggregate_digests(digests, "month", None)
    duration = time.perf_counter() - started_at

    assert sum(x.merged for x in statistics.activities) == 400 * 20
    assert duration < 2


def test_open_pull_requests_are_bucketed_by_age(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    # ages measured against the frozen now of 2026-03-11 12:00
    pull_requests = [
        _pull_request("2026-03-11T06:00:00Z", number=1),  # 6 hours
        _pull_request("2026-03-10T06:00:00Z", number=2),  # 1.25 days
        _pull_request("2026-03-06T12:00:00Z", number=3),  # 5 days
        _pull_request("2026-03-01T12:00:00Z", number=4),  # 10 days
        _pull_request("2025-12-01T12:00:00Z", number=5),  # 100 days
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month", None)

    assert [(x.label, x.count) for x in statistics.open_aging] == [
        ("< 1 day", 1),
        ("1-3 days", 1),
        ("3-7 days", 1),
        ("7-30 days", 1),
        ("> 30 days", 1),
    ]


def test_the_oldest_open_pull_requests_come_first(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-10T12:00:00Z", number=1),
        _pull_request("2025-12-01T12:00:00Z", number=2),
        _pull_request("2026-03-01T12:00:00Z", number=3),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month", None)

    assert [x.number for x in statistics.oldest_open] == [2, 3, 1]
    assert statistics.oldest_open[0].age_days == 100.0
    assert statistics.oldest_open[0].url.endswith("/pull/2")


def test_merged_and_closed_pull_requests_are_not_counted_as_open(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-01T12:00:00Z", "2026-03-02T12:00:00Z", "2026-03-02T12:00:00Z", ("a-user", "User")),
        _pull_request("2026-03-01T12:00:00Z", "2026-03-02T12:00:00Z"),
        _pull_request("2026-03-01T12:00:00Z", number=3),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month", None)

    assert sum(x.count for x in statistics.open_aging) == 1
    assert [x.number for x in statistics.oldest_open] == [3]


def test_the_age_of_an_open_pull_request_does_not_depend_on_the_selected_range(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    # opened long before any range the ui offers, it still has to show up as open
    digests = [_digest([_pull_request("2025-01-01T12:00:00Z", number=7)])]

    within_a_week = aggregate_digests(digests, "day", datetime(2026, 3, 4, tzinfo=UTC))
    everything = aggregate_digests(digests, "month", None)

    assert [x.number for x in within_a_week.oldest_open] == [7]
    assert within_a_week.oldest_open[0].age_days == everything.oldest_open[0].age_days


def test_cycle_time_separates_auto_merged_from_manually_merged(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        # merged by the app after 15 minutes and 1 hour
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T00:15:00Z", "2026-03-10T00:15:00Z", ("otterdog", "Bot")),
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T01:00:00Z", "2026-03-10T01:00:00Z", ("otterdog", "Bot")),
        # merged by hand after 2 and 4 days
        _pull_request("2026-03-06T00:00:00Z", "2026-03-08T00:00:00Z", "2026-03-08T00:00:00Z", ("a-user", "User")),
        _pull_request("2026-03-06T00:00:00Z", "2026-03-10T00:00:00Z", "2026-03-10T00:00:00Z", ("a-user", "User")),
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month", None)

    by_label = {x.label: x for x in statistics.cycle_times}

    # nearest rank, so the median of two values is the lower one
    assert by_label["Auto-merge"].count == 2
    assert by_label["Auto-merge"].median_hours == 0.2
    assert by_label["Auto-merge"].p90_hours == 1.0
    assert by_label["Manual merge"].count == 2
    assert by_label["Manual merge"].median_hours == 48.0
    assert by_label["Manual merge"].p90_hours == 96.0

    # the overall figures still cover both populations together
    assert statistics.cycle_time_median_hours == 1.0


def test_cycle_time_of_a_population_without_any_merge_is_undefined(fixed_now):
    from otterdog.webapp.statistics import aggregate_digests

    pull_requests = [
        _pull_request("2026-03-10T00:00:00Z", "2026-03-10T00:15:00Z", "2026-03-10T00:15:00Z", ("otterdog", "Bot"))
    ]

    statistics = aggregate_digests([_digest(pull_requests)], "month", None)

    by_label = {x.label: x for x in statistics.cycle_times}

    assert by_label["Manual merge"].count == 0
    assert by_label["Manual merge"].median_hours is None
    assert by_label["Manual merge"].p90_hours is None
