"""
Syllabus Design Agent — CLI Entry Point
Deployed on Google Gemini (gemini-2.0-flash)

Usage:
  python main.py                        # interactive wizard
  python main.py --json sample_input.json
  python main.py --regen lesson_plan    # regenerate one section
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table as RichTable
from rich.text import Text

import config
from agent import SyllabusAgent, assemble_markdown, save_full_markdown
from models import CourseInput
from pdf_generator import generate_pdf

load_dotenv()
console = Console()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║         SYLLABUS DESIGN AGENT  ·  Powered by Gemini         ║
║    OBE · NBA/NAAC · Revised Bloom's · SDG-Aligned           ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────────────────────────
# Input helpers
# ─────────────────────────────────────────────────────────────────
def _ask(label: str, default: str = "") -> str:
    d = f" [dim](default: {default})[/dim]" if default else ""
    val = Prompt.ask(f"[cyan]{label}[/cyan]{d}").strip()
    return val or default


def _ask_int(label: str, default: int) -> int:
    return IntPrompt.ask(f"[cyan]{label}[/cyan]", default=default)


def collect_course_input() -> CourseInput:
    console.print("\n[bold yellow]── Course Information ──[/bold yellow]")
    course = CourseInput(
        course_title         = _ask("Course Title"),
        course_code          = _ask("Course Code", "CS-501"),
        class_year           = _ask("Class (FY/SY/TY/B.Tech/M.Tech)", "TY"),
        department           = _ask("Department", "Computer Engineering"),
        program              = _ask("Program (B.Tech/M.Tech/BCA/MCA)", "B.Tech"),
        discipline           = _ask("Discipline / Specialization", "Computer Engineering"),
        university           = _ask("University / Institute Name", ""),
        course_type          = _ask("Course Type (Theory/Lab/Hybrid)", "Theory"),
        lectures_per_week    = _ask_int("Lectures per week (L)", 3),
        tutorials_per_week   = _ask_int("Tutorials per week (T)", 1),
        practicals_per_week  = _ask_int("Practicals per week (P)", 0),
        total_credits        = _ask_int("Total Credits", 4),
        total_contact_hours  = _ask_int("Total Contact Hours", 48),
        num_units            = _ask_int("Number of Units", 5),
        semester_duration_weeks = _ask_int("Semester Duration (Weeks)", 16),
        prerequisites        = _ask("Prerequisites (comma-separated or None)", "None"),
        pso_count            = _ask_int("Number of PSOs", 3),
    )
    if course.has_lab:
        course.num_lab_modules    = _ask_int("Number of Lab Modules", 4)
        course.num_lab_assignments= _ask_int("Number of Lab Assignments", 10)

    return course


def load_course_from_json(path: str) -> CourseInput:
    data = json.loads(Path(path).read_text())
    return CourseInput(**data)


# ─────────────────────────────────────────────────────────────────
# Summary display
# ─────────────────────────────────────────────────────────────────
def show_course_summary(course: CourseInput) -> None:
    t = RichTable(title="Course Configuration", style="bold", border_style="blue")
    t.add_column("Field", style="cyan", no_wrap=True)
    t.add_column("Value", style="white")
    rows = [
        ("Course Title",    course.course_title),
        ("Course Code",     course.course_code),
        ("Class",           course.class_year),
        ("Program",         course.program),
        ("Department",      course.department),
        ("Course Type",     course.course_type),
        ("L-T-P",           course.ltp),
        ("Credits",         str(course.total_credits)),
        ("Contact Hours",   str(course.total_contact_hours)),
        ("Units",           str(course.num_units)),
        ("Semester Weeks",  str(course.semester_duration_weeks)),
        ("Has Lab",         "Yes" if course.has_lab else "No"),
    ]
    for k, v in rows:
        t.add_row(k, v)
    console.print(t)


# ─────────────────────────────────────────────────────────────────
# Main flow
# ─────────────────────────────────────────────────────────────────
def main() -> None:
    console.print(Text(BANNER, style="bold blue"))

    # ── Argument parsing (simple, no argparse dependency) ──
    args = sys.argv[1:]
    json_file  = None
    regen_key  = None
    output_dir = config.OUTPUT_DIR

    i = 0
    while i < len(args):
        if args[i] == "--json" and i + 1 < len(args):
            json_file = args[i + 1]; i += 2
        elif args[i] == "--regen" and i + 1 < len(args):
            regen_key = args[i + 1]; i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output_dir = args[i + 1]; i += 2
        else:
            i += 1

    # ── Load or collect course input ──
    if json_file:
        console.print(f"[green]Loading course from[/green] {json_file}")
        course = load_course_from_json(json_file)
    else:
        course = collect_course_input()

    show_course_summary(course)

    if not Confirm.ask("\n[bold yellow]Proceed with generation?[/bold yellow]", default=True):
        console.print("[red]Aborted.[/red]")
        return

    # ── Instantiate agent ──
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        api_key = Prompt.ask("[yellow]Enter your Gemini API key[/yellow]", password=True)

    agent = SyllabusAgent(api_key=api_key)

    # ── Regenerate single section or full syllabus ──
    if regen_key:
        console.print(Panel(f"[bold cyan]Regenerating section: {regen_key}[/bold cyan]"))
        # Load existing core output for context
        from agent import _safe_filename, _extract_co_unit_context
        slug     = _safe_filename(course.course_title)
        core_md  = (Path(output_dir) / f"{slug}_core.md")
        co_ctx   = _extract_co_unit_context(core_md.read_text()) if core_md.exists() else ""
        text     = agent.regenerate_section(regen_key, course, co_ctx)
        (Path(output_dir) / f"{slug}_{regen_key}.md").write_text(text, encoding="utf-8")
        console.print(f"[green]Section saved:[/green] {output_dir}/{slug}_{regen_key}.md")
        return

    # ── Full generation ──
    console.print(Panel(
        "[bold green]Starting full syllabus generation…[/bold green]\n"
        "Streaming output will appear below. Each section is auto-saved.",
        title="Syllabus Design Agent", expand=False
    ))

    sections = agent.generate(course, output_dir)

    # ── Assemble & save full markdown ──
    md_path = save_full_markdown(sections, course, output_dir)
    console.print(f"\n[bold green]Full Markdown saved:[/bold green] {md_path}")

    # ── PDF generation ──
    if Confirm.ask("\n[bold yellow]Generate PDF?[/bold yellow]", default=True):
        from agent import _safe_filename
        slug     = _safe_filename(course.course_title)
        pdf_path = Path(output_dir) / f"{slug}_FULL_SYLLABUS.pdf"
        meta = {
            "Program"       : f"{course.program} — {course.discipline}",
            "Department"    : course.department,
            "Course Code"   : course.course_code,
            "Class"         : course.class_year,
            "Credits"       : str(course.total_credits),
            "L-T-P"         : course.ltp,
            "Contact Hours" : str(course.total_contact_hours),
        }
        if course.university:
            meta["University"] = course.university

        console.print("[cyan]Generating PDF…[/cyan]")
        full_md = md_path.read_text(encoding="utf-8")
        generate_pdf(full_md, pdf_path, course_title=course.course_title, meta=meta)
        console.print(f"[bold green]PDF saved:[/bold green] {pdf_path}")

    console.print(Panel(
        f"[bold green]Syllabus generation complete![/bold green]\n"
        f"Output directory: [cyan]{output_dir}/[/cyan]",
        title="Done", expand=False
    ))


if __name__ == "__main__":
    main()
