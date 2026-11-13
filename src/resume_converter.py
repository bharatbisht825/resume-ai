from __future__ import annotations

import re


SECTION_NAMES = {
    "summary",
    "profile",
    "objective",
    "experience",
    "work experience",
    "education",
    "skills",
    "projects",
    "certifications",
    "achievements",
    "awards",
    "volunteer experience",
    "interests",
}

LATEX_SPECIAL_CHARACTERS = str.maketrans(
    {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
)


def escape_latex(value: str) -> str:
    """Escape user-provided text so it can safely appear in LaTeX."""
    return value.translate(LATEX_SPECIAL_CHARACTERS)


def _is_section_heading(line: str) -> bool:
    normalized = line.strip().rstrip(":").casefold()
    return normalized in SECTION_NAMES or (
        len(line.strip()) <= 45 and line.strip().isupper()
    )


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^\s*(?:[-*+]|\u2022)\s+", line))


def _bullet_text(line: str) -> str:
    return re.sub(r"^\s*(?:[-*+]|\u2022)\s+", "", line).strip()


def convert_resume_to_latex(resume: str) -> str:
    """Convert a plain-text resume into a compilable, ATS-friendly LaTeX document."""
    lines = [line.strip() for line in resume.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("Resume must contain at least one non-empty line")

    output = [
        r"\documentclass[10pt]{article}",
        r"\usepackage[margin=0.7in]{geometry}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\usepackage{enumitem}",
        r"\setlist[itemize]{leftmargin=*, nosep}",
        r"\setlength{\parindent}{0pt}",
        r"\begin{document}",
        "",
    ]

    index = 0
    output.append(rf"\begin{{center}}\Large\textbf{{{escape_latex(lines[0])}}}\end{{center}}")
    index = 1

    while index < len(lines):
        line = lines[index]
        if _is_section_heading(line):
            output.extend(["", rf"\section*{{{escape_latex(line.rstrip(':'))}}}"])
            index += 1
            continue

        if _is_bullet(line):
            output.append(r"\begin{itemize}")
            while index < len(lines) and _is_bullet(lines[index]):
                output.append(rf"\item {escape_latex(_bullet_text(lines[index]))}")
                index += 1
            output.append(r"\end{itemize}")
            continue

        output.append(escape_latex(line) + r"\\")
        index += 1

    output.extend(["", r"\end{document}", ""])
    return "\n".join(output)
