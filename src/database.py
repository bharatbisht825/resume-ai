from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select

from src.models import Resume, ResumeCategory
from src.settings import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    pass


class DatabaseConflictError(RuntimeError):
    pass


settings = get_settings()
engine = create_async_engine(
    settings.sqlalchemy_database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
)
session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def require_database() -> None:
    if not settings.database_configured:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured")


async def initialize_database() -> None:
    require_database()
    async with engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


async def _upsert_category(session: AsyncSession, name: str) -> ResumeCategory:
    statement = (
        insert(ResumeCategory)
        .values(name=name)
        .on_conflict_do_update(
            index_elements=[ResumeCategory.name],
            set_={"name": name},
        )
        .returning(ResumeCategory)
    )
    result = await session.exec(statement)
    return result.one()


async def create_category(name: str) -> ResumeCategory:
    require_database()
    async with session_factory() as session:
        category = await _upsert_category(session, name)
        await session.commit()
        return category


async def list_categories() -> list[ResumeCategory]:
    require_database()
    async with session_factory() as session:
        result = await session.exec(
            select(ResumeCategory).order_by(ResumeCategory.name)
        )
        return list(result.all())


async def _resolve_category(
    session: AsyncSession,
    category_id: UUID | None,
    category_name: str | None,
) -> ResumeCategory:
    if category_id is not None:
        category = await session.get(ResumeCategory, category_id)
        if category is None:
            raise ValueError("Category not found")
        return category
    return await _upsert_category(session, category_name or "Master")


async def create_resume(
    *,
    category_id: UUID | None,
    category_name: str | None,
    company_name: str | None,
    job_title: str | None,
    latex_source: str,
    is_master: bool,
) -> Resume:
    require_database()
    async with session_factory() as session:
        try:
            async with session.begin():
                category = await _resolve_category(
                    session, category_id, category_name
                )
                if is_master:
                    await session.exec(
                        update(Resume)
                        .where(
                            Resume.category_id == category.id,
                            Resume.is_master.is_(True),
                        )
                        .values(is_master=False)
                    )
                resume = Resume(
                    category_id=category.id,
                    company_name=company_name,
                    job_title=job_title,
                    latex_source=latex_source,
                    is_master=is_master,
                )
                session.add(resume)
                await session.flush()
            return resume
        except IntegrityError as error:
            raise DatabaseConflictError(
                "Another master resume was created for this category concurrently"
            ) from error


async def list_resumes(
    category_id: UUID | None = None,
    is_master: bool | None = None,
) -> list[Resume]:
    require_database()
    async with session_factory() as session:
        statement: Any = select(Resume)
        if category_id is not None:
            statement = statement.where(Resume.category_id == category_id)
        if is_master is not None:
            statement = statement.where(Resume.is_master == is_master)
        result = await session.exec(statement.order_by(Resume.created_at.desc()))
        return list(result.all())


async def get_resume(resume_id: UUID) -> Resume | None:
    require_database()
    async with session_factory() as session:
        return await session.get(Resume, resume_id)
