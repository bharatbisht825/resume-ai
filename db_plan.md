# Resume Storage and Organization Plan

## 1. Purpose

Build a simple database-backed system for storing a master resume and
multiple job-specific resume versions.

The system should make it easy to tailor a resume for different
companies and roles without losing track of what was submitted to each
employer.

The initial implementation will use **two PostgreSQL tables**:

-   `resume_categories` --- groups resumes by professional
    specialization.
-   `resumes` --- stores the LaTeX source and metadata for each resume.

This is intentionally a small design. It avoids introducing Git-style
branching, parent-resume relationships, or a complex document-versioning
model before those capabilities are needed.

## 2. Why we are doing this

When applying to multiple jobs, a single resume is often not suitable
for every role. For example, an AI Engineer position may benefit from
emphasizing machine-learning projects, while a Backend Engineer position
may need more emphasis on APIs, databases, and distributed systems.

Keeping all tailored resumes as unrelated files makes it difficult to
organize them and identify which resume was used for a particular
company.

Using Git branches for every job application would also introduce
unnecessary complexity. These resumes are not successive changes to one
codebase: they are separate documents organized by specialization.

The proposed design provides:

1.  **A central master resume per category.** Each category can have a
    resume designated as its master.
2.  **Independent job-specific resumes.** A resume for one company does
    not need to be a child or revision of a resume for another company.
3.  **A clear organizational structure.** Categories such as AI,
    Backend, and Full Stack group related resumes.
4.  **Historical context.** The stored LaTeX source preserves the exact
    resume content that was generated or submitted, even if the master
    resume changes later.
5.  **A straightforward starting point.** Two tables are sufficient for
    the current requirements and can be extended later.

## 3. Data model

### 3.1 `resume_categories`

Stores the categories used to organize resumes.

Examples:

-   Master
-   AI
-   Backend
-   Full Stack
-   Data Engineering

The `Master` category is an ordinary category identified by its name. It
does not need a special flag or parent relationship.

Proposed schema:

``` sql
CREATE TABLE resume_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.2 `resumes`

Stores each resume's LaTeX source and its associated category.

-   `category_id` identifies the category to which the resume belongs.
-   `company_name` identifies the employer for a job-specific resume. It
    can be NULL for a master resume.
-   `job_title` records the position targeted by a job-specific resume.
    It can be NULL for a master resume.
-   `latex_source` stores the complete LaTeX document as PostgreSQL
    `TEXT`.
-   `is_master` indicates whether this record is the current master
    resume for its category.
-   `created_at` records when the resume record was created.

Proposed schema:

``` sql
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    category_id UUID NOT NULL
        REFERENCES resume_categories(id),

    company_name VARCHAR(255),

    job_title VARCHAR(255),

    latex_source TEXT NOT NULL,

    is_master BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 4. Master-resume rules

A master resume is a resume record marked with `is_master = TRUE`.

The intended rules are:

1.  Each category can have at most one master resume.
2.  A new resume with no category explicitly selected is assigned to the
    `Master` category.
3.  When a new master resume is uploaded for a category, it replaces the
    existing master resume for that category.
4.  Job-specific resumes are stored as separate records and do not
    replace the category's master resume.
5.  Replacing a master should not silently delete the old record. The
    old record should be retained with `is_master = FALSE`, preserving
    its LaTeX source and creation date.

The last rule is important: the application should replace the *current
master designation*, not destroy the previous resume. This preserves
historical context.

### Database constraint

A partial unique index enforces the one-master-per-category rule:

``` sql
CREATE UNIQUE INDEX uq_resume_master_per_category
ON resumes (category_id)
WHERE is_master = TRUE;
```

This allows any number of non-master resumes in a category while
preventing two records in the same category from both being marked as
master.

## 5. Replacing a master resume safely

The application should perform master replacement in a database
transaction.

Example:

``` sql
BEGIN;

UPDATE resumes
SET is_master = FALSE
WHERE category_id = 'CATEGORY_UUID'
  AND is_master = TRUE;

INSERT INTO resumes (
    category_id,
    company_name,
    job_title,
    latex_source,
    is_master
)
VALUES (
    'CATEGORY_UUID',
    NULL,
    NULL,
    'NEW_LATEX_SOURCE',
    TRUE
);

COMMIT;
```

The transaction ensures that the old master is unmarked and the new
master is inserted as one operation. If the insert fails, the
transaction can be rolled back so the existing master remains in place.

The unique index is a final database-level safeguard. Application code
should still handle concurrent replacement attempts and any resulting
uniqueness violation.

## 6. Example organization

``` text
Resume Categories
|
+-- Master
|   +-- Current Master Resume
|   +-- Previous Master Resume (is_master = FALSE)
|
+-- AI
|   +-- Current AI Master Resume
|   +-- Google - AI Engineer
|   +-- OpenAI - ML Engineer
|
+-- Backend
|   +-- Current Backend Master Resume
|   +-- Amazon - Backend Engineer
|   +-- Microsoft - Python Developer
|
+-- Full Stack
    +-- Current Full Stack Master Resume
    +-- Company A - Full Stack Engineer
```

The category tree is conceptual organization, not document inheritance.
A job-specific resume is independently stored; it does not need a
parent-resume ID.

## 7. Typical application workflow

### Creating the initial master resume

1.  Ensure the `Master` category exists.
2.  Store the uploaded or created LaTeX source in `resumes`.
3.  Set `is_master = TRUE`.

### Creating a category master

1.  Select or create a category, such as `AI`.
2.  Generate or provide the category-specific master resume.
3.  In a transaction, unmark the existing master for that category, if
    one exists.
4.  Insert the new resume with `is_master = TRUE`.

### Creating a job-specific resume

1.  Select a category, such as `AI`.
2.  Provide the company name and job title.
3.  Use the relevant master resume as the source context for tailoring.
4.  Generate the tailored LaTeX source.
5.  Insert it as a new resume with `is_master = FALSE`.

The tailored resume remains an independent record. Later changes to the
master do not alter it.

## 8. Scope and future extensions

The first implementation deliberately stores only the LaTeX source and
basic identifying metadata. It does not require a separate revision
table, job-description table, application-tracking table, or
parent-resume relationship.

Possible future additions, if the workflow requires them:

-   Store the original job description associated with a tailored
    resume.
-   Store the generated PDF in file or object storage and save its path
    in the database.
-   Track application status and submission date.
-   Store generation metadata such as model, prompt version, and source
    master ID.
-   Add tags for resumes that fit more than one specialization.
-   Add an explicit audit or revision history if more detailed editing
    history is needed.

These should be introduced when there is a concrete need, rather than
making the initial schema more complicated.

## 9. Summary of design decisions

  -----------------------------------------------------------------------
  Decision                            Reason
  ----------------------------------- -----------------------------------
  Use PostgreSQL                      Stores resume metadata and LaTeX
                                      source reliably.

  Store LaTeX in `TEXT`               LaTeX is plain text; no special
                                      database type is required.

  Use categories                      Groups resumes by specialization.

  Keep `Master` as an ordinary        Avoids special category hierarchy
  category                            or verification logic.

  Put `is_master` on `resumes`        Identifies the current master
                                      resume within each category.

  Use a partial unique index          Enforces at most one master resume
                                      per category.

  Retain replaced masters             Preserves prior content and
                                      historical context.

  Keep job-specific resumes           Avoids unnecessary parent-child
  independent                         dependencies between applications.

  Keep the initial design to two      Meets current requirements without
  tables                              premature complexity.
  -----------------------------------------------------------------------

**Core principle:** Categories organize resumes; `is_master` identifies
the current source resume within a category; each job-specific resume is
stored independently as a durable snapshot.
