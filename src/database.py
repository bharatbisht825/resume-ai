from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class DatabaseNotConfiguredError(RuntimeError):
    pass


class DatabaseConflictError(RuntimeError):
    pass


def database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseNotConfiguredError("DATABASE_URL is not configured")
    return value


async def initialize_database() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    async with await psycopg.AsyncConnection.connect(database_url()) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(schema)
        await connection.commit()


async def create_category(name: str) -> dict[str, Any]:
    async with await psycopg.AsyncConnection.connect(database_url()) as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                INSERT INTO resume_categories (name)
                VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id, name, created_at
                """,
                (name,),
            )
            result = await cursor.fetchone()
        await connection.commit()
    if result is None:
        raise RuntimeError("Category was not returned after creation")
    return result


async def list_categories() -> list[dict[str, Any]]:
    async with await psycopg.AsyncConnection.connect(database_url()) as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT id, name, created_at
                FROM resume_categories
                ORDER BY name
                """
            )
            result = await cursor.fetchall()
    return list(result)


async def _category_id(
    cursor: psycopg.AsyncCursor[dict[str, Any]],
    category_id: UUID | None,
    category_name: str | None,
) -> UUID:
    if category_id is not None:
        await cursor.execute(
            "SELECT id FROM resume_categories WHERE id = %s",
            (category_id,),
        )
        category = await cursor.fetchone()
        if category is None:
            raise ValueError("Category not found")
        return category["id"]

    name = category_name or "Master"
    await cursor.execute(
        """
        INSERT INTO resume_categories (name)
        VALUES (%s)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (name,),
    )
    category = await cursor.fetchone()
    if category is None:
        raise RuntimeError("Category was not returned after creation")
    return category["id"]


async def create_resume(
    *,
    category_id: UUID | None,
    category_name: str | None,
    company_name: str | None,
    job_title: str | None,
    latex_source: str,
    is_master: bool,
) -> dict[str, Any]:
    try:
        async with await psycopg.AsyncConnection.connect(database_url()) as connection:
            async with connection.transaction():
                async with connection.cursor(row_factory=dict_row) as cursor:
                    resolved_category_id = await _category_id(
                        cursor, category_id, category_name
                    )
                    if is_master:
                        await cursor.execute(
                            """
                            UPDATE resumes
                            SET is_master = FALSE
                            WHERE category_id = %s AND is_master = TRUE
                            """,
                            (resolved_category_id,),
                        )
                    await cursor.execute(
                        """
                        INSERT INTO resumes (
                            category_id, company_name, job_title,
                            latex_source, is_master
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id, category_id, company_name, job_title,
                                  latex_source, is_master, created_at
                        """,
                        (
                            resolved_category_id,
                            company_name,
                            job_title,
                            latex_source,
                            is_master,
                        ),
                    )
                    result = await cursor.fetchone()
            if result is None:
                raise RuntimeError("Resume was not returned after creation")
            return result
    except psycopg.errors.UniqueViolation as error:
        raise DatabaseConflictError(
            "Another master resume was created for this category concurrently"
        ) from error


async def list_resumes(
    category_id: UUID | None = None,
    is_master: bool | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    values: list[Any] = []
    if category_id is not None:
        conditions.append("category_id = %s")
        values.append(category_id)
    if is_master is not None:
        conditions.append("is_master = %s")
        values.append(is_master)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with await psycopg.AsyncConnection.connect(database_url()) as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                f"""
                SELECT id, category_id, company_name, job_title,
                       latex_source, is_master, created_at
                FROM resumes
                {where}
                ORDER BY created_at DESC
                """,
                values,
            )
            result = await cursor.fetchall()
    return list(result)


async def get_resume(resume_id: UUID) -> dict[str, Any] | None:
    async with await psycopg.AsyncConnection.connect(database_url()) as connection:
        async with connection.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT id, category_id, company_name, job_title,
                       latex_source, is_master, created_at
                FROM resumes
                WHERE id = %s
                """,
                (resume_id,),
            )
            return await cursor.fetchone()
