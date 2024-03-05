#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class RequestStatistics:
    total_requests: int = 0
    cached_responses: int = 0
    remaining_rate_limit: int = -1

    def merge(self, other: RequestStatistics) -> None:
        self.total_requests += other.total_requests
        self.cached_responses += other.cached_responses

        if self.remaining_rate_limit == -1:
            self.remaining_rate_limit = other.remaining_rate_limit
        elif other.remaining_rate_limit == -1:
            self.remaining_rate_limit = self.remaining_rate_limit
        else:
            self.remaining_rate_limit = min(self.remaining_rate_limit, other.remaining_rate_limit)

    def sent_request(self) -> None:
        self.total_requests += 1

    def received_cached_response(self) -> None:
        self.cached_responses += 1

    def update_remaining_rate_limit(self, remaining: int) -> None:
        self.remaining_rate_limit = remaining
