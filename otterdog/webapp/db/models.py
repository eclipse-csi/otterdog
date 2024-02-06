#  *******************************************************************************
#  Copyright (c) 2024 Eclipse Foundation and others.
#  This program and the accompanying materials are made available
#  under the terms of the Eclipse Public License 2.0
#  which is available at http://www.eclipse.org/legal/epl-v20.html
#  SPDX-License-Identifier: EPL-2.0
#  *******************************************************************************

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Organization(Base):  # type: ignore
    __tablename__ = "Organization"

    installation_id: Mapped[int] = mapped_column(primary_key=True)
    github_id: Mapped[str] = mapped_column(String(255), unique=True)
    project_name: Mapped[Optional[str]] = mapped_column(String(255), unique=True, default=None)

    def __repr__(self) -> str:
        return (
            f"Organization(installation_id={self.installation_id!r}, project_name={self.project_name!r}, "
            f"github_id={self.github_id!r})"
        )


class DBTask(Base):
    __tablename__ = "Task"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    type: Mapped[str] = mapped_column(String(255))
    org_id: Mapped[str] = mapped_column(String(255))
    repo_name: Mapped[str] = mapped_column(String(255))
    pull_request: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(server_default=func.now(), onupdate=func.now())

    def __init__(self, **kwargs):
        if "id" not in kwargs:
            kwargs["id"] = uuid.uuid4()
        super().__init__(**kwargs)
