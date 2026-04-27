"""Gemini-powered Syllabus Design Agent."""

import os
import re
from pathlib import Path
from typing import Optional

import google.genai as genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

import config
import prompts
from models import CourseInput

console = Console()


# ─────────────────────────────────────────────────────────────────
# Helper: extract COs + Unit titles from Section 1–4 output
# ─────────────────────────────────────────────────────────────────
def _extract_co_unit_context(core_text: str) -> str:
    """Pull CO table and unit titles out of the core section output."""
    lines = core_text.split("\n")
    context_lines: list[str] = []

    in_co_table = False
    for line in lines:
        # Capture the CO table
        if "## 2." in line or "COURSE OUTCOMES" in line.upper():
            in_co_table = True
        if in_co_table:
            context_lines.append(line)
            if line.startswith("## 3") or line.startswith("## 4"):
                in_co_table = False

        # Capture unit titles
        if re.match(r"### Unit \d+", line):
            context_lines.append(line)

    return "\n".join(context_lines) if context_lines else core_text[:2000]


# ─────────────────────────────────────────────────────────────────
# Main Agent Class
# ─────────────────────────────────────────────────────────────────
class SyllabusAgent:
    SECTIONS = [
        ("core",             "Sections 1–4: Course Profile, COs, SDGs, Unit Syllabus"),
        ("lesson_plan",      "Section 5: Lesson Plan"),
        ("lab_strategy",     "Sections 6–8: Lab Design, Teaching Strategy, Assessment"),
        ("assignments",      "Sections 9–11: Assignments, Rubrics, CO–PO–PSO Mapping"),
        ("resources",        "Sections 12–15: Question Bank, Resources, Learner Support, Cross-cutting"),
    ]

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it as an environment variable or pass api_key=."
            )
        self._client = genai.Client(api_key=key)
        self._gen_cfg = types.GenerateContentConfig(
            temperature=config.TEMPERATURE,
            max_output_tokens=config.MAX_OUTPUT_TOKENS,
            system_instruction=config.SYSTEM_INSTRUCTION,
        )

    # ── low-level generation ──────────────────────────────────────
    def _generate(self, prompt: str, stream: bool = True) -> str:
        full = ""
        if stream:
            for chunk in self._client.models.generate_content_stream(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=self._gen_cfg,
            ):
                if chunk.text:
                    console.print(chunk.text, end="", markup=False, highlight=False)
                    full += chunk.text
            console.print()
        else:
            resp = self._client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=self._gen_cfg,
            )
            full = resp.text or ""
        return full

    # ── public: generate full syllabus ───────────────────────────
    def generate(self, course: CourseInput, output_dir: str = config.OUTPUT_DIR) -> dict[str, str]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        sections: dict[str, str] = {}
        co_ctx = ""

        for key, label in self.SECTIONS:
            console.print(Panel(f"[bold cyan]{label}[/bold cyan]", expand=False))

            if key == "core":
                p = prompts.core_prompt(course)
            elif key == "lesson_plan":
                p = prompts.lesson_plan_prompt(course, co_ctx)
            elif key == "lab_strategy":
                p = prompts.lab_strategy_assessment_prompt(course, co_ctx)
            elif key == "assignments":
                p = prompts.assignments_rubrics_mapping_prompt(course, co_ctx)
            else:
                p = prompts.resources_support_prompt(course, co_ctx)

            text = self._generate(p)
            sections[key] = text

            # Save section immediately so progress isn't lost
            _save_section(key, text, output_dir, course.course_title)

            # Build context from core section for all subsequent prompts
            if key == "core":
                co_ctx = _extract_co_unit_context(text)

        return sections

    # ── public: generate single section ──────────────────────────
    def regenerate_section(
        self, section_key: str, course: CourseInput, co_ctx: str = ""
    ) -> str:
        dispatch = {
            "core":        lambda: prompts.core_prompt(course),
            "lesson_plan": lambda: prompts.lesson_plan_prompt(course, co_ctx),
            "lab_strategy":lambda: prompts.lab_strategy_assessment_prompt(course, co_ctx),
            "assignments": lambda: prompts.assignments_rubrics_mapping_prompt(course, co_ctx),
            "resources":   lambda: prompts.resources_support_prompt(course, co_ctx),
        }
        if section_key not in dispatch:
            raise ValueError(f"Unknown section key: {section_key}")
        return self._generate(dispatch[section_key]())


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _safe_filename(title: str) -> str:
    return re.sub(r"[^\w\-_]", "_", title).strip("_")[:60]


def _save_section(key: str, text: str, output_dir: str, course_title: str) -> None:
    slug = _safe_filename(course_title)
    path = Path(output_dir) / f"{slug}_{key}.md"
    path.write_text(text, encoding="utf-8")


def assemble_markdown(sections: dict[str, str], course: CourseInput) -> str:
    title_block = (
        f"# {course.course_title}\n"
        f"**Course Code:** {course.course_code}  \n"
        f"**Program:** {course.program} — {course.discipline}  \n"
        f"**Department:** {course.department}  \n"
        f"**Class:** {course.class_year} | **Credits:** {course.total_credits} "
        f"| **L-T-P:** {course.ltp} | **Contact Hours:** {course.total_contact_hours}\n\n"
        f"---\n\n"
    )
    order = ["core", "lesson_plan", "lab_strategy", "assignments", "resources"]
    body = "\n\n---\n\n".join(sections.get(k, "") for k in order if k in sections)
    return title_block + body


def save_full_markdown(sections: dict[str, str], course: CourseInput, output_dir: str) -> Path:
    slug = _safe_filename(course.course_title)
    md_path = Path(output_dir) / f"{slug}_FULL_SYLLABUS.md"
    md_path.write_text(assemble_markdown(sections, course), encoding="utf-8")
    return md_path
