from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeCategory(SQLModel, table=True):
    __tablename__: ClassVar[str] = "resume_categories"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    )


class Resume(SQLModel, table=True):
    __tablename__: ClassVar[str] = "resumes"
    __table_args__ = (
        Index(
            "uq_resume_master_per_category",
            "category_id",
            unique=True,
            postgresql_where=text("is_master = TRUE"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    category_id: UUID = Field(foreign_key="resume_categories.id", nullable=False)
    company_name: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    latex_source: str
    is_master: bool = False
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    )
