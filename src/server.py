from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from src import database
from src.resume_converter import convert_resume_to_latex
from src.settings import get_settings


class ConvertResumeRequest(BaseModel):
    resume: str = Field(min_length=1)


class ConvertedResume(BaseModel):
    latex: str


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryResponse(CategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class ResumeCreate(BaseModel):
    category_id: UUID | None = None
    category_name: str | None = Field(default=None, min_length=1, max_length=100)
    company_name: str | None = Field(default=None, max_length=255)
    job_title: str | None = Field(default=None, max_length=255)
    latex_source: str = Field(min_length=1)
    is_master: bool = False


class ResumeResponse(ResumeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().database_configured:
        await database.initialize_database()
    yield


app = FastAPI(title="Resume LaTeX Converter", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True, "database_configured": get_settings().database_configured}


@app.post("/api/convert-to-latex", response_model=ConvertedResume)
async def convert_to_latex(payload: ConvertResumeRequest) -> ConvertedResume:
    try:
        return ConvertedResume(latex=convert_resume_to_latex(payload.resume))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def database_error_response(error: database.DatabaseNotConfiguredError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(error))


@app.post("/api/categories", response_model=CategoryResponse)
async def add_category(payload: CategoryCreate) -> CategoryResponse:
    try:
        return CategoryResponse.model_validate(await database.create_category(payload.name))
    except database.DatabaseNotConfiguredError as error:
        raise database_error_response(error) from error


@app.get("/api/categories", response_model=list[CategoryResponse])
async def get_categories() -> list[CategoryResponse]:
    try:
        categories = await database.list_categories()
        return [CategoryResponse.model_validate(category) for category in categories]
    except database.DatabaseNotConfiguredError as error:
        raise database_error_response(error) from error


@app.post("/api/resumes", response_model=ResumeResponse, status_code=201)
async def add_resume(payload: ResumeCreate) -> ResumeResponse:
    try:
        resume = await database.create_resume(**payload.model_dump())
        return ResumeResponse.model_validate(resume)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except database.DatabaseConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except database.DatabaseNotConfiguredError as error:
        raise database_error_response(error) from error


@app.get("/api/resumes", response_model=list[ResumeResponse])
async def get_resumes(
    category_id: UUID | None = Query(default=None),
    is_master: bool | None = Query(default=None),
) -> list[ResumeResponse]:
    try:
        resumes = await database.list_resumes(category_id, is_master)
        return [ResumeResponse.model_validate(resume) for resume in resumes]
    except database.DatabaseNotConfiguredError as error:
        raise database_error_response(error) from error


@app.get("/api/resumes/{resume_id}", response_model=ResumeResponse)
async def get_resume(resume_id: UUID) -> ResumeResponse:
    try:
        resume = await database.get_resume(resume_id)
    except database.DatabaseNotConfiguredError as error:
        raise database_error_response(error) from error
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return ResumeResponse.model_validate(resume)