"""Gemini-powered Syllabus Design Agent."""

import os
import re
import time
from pathlib import Path
from typing import Optional

import google.genai as genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel

import config
import prompts
from models import CourseInput

console = Console()


# ─────────────────────────────────────────────────────────────────
# Retry helper — parse API retryDelay + exponential backoff + model fallback
# ─────────────────────────────────────────────────────────────────
def _is_quota_error(exc: Exception) -> bool:
    """Return True for any 429 / RESOURCE_EXHAUSTED error."""
    msg = str(exc).upper()
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg


def _parse_retry_delay(exc: Exception) -> int | None:
    """
    Gemini embeds the suggested wait in the error body, e.g.:
      'retryDelay': '62s'   or   'retry_delay { seconds: 62 }'
    Extract that value so we wait exactly what the API asks for
    instead of guessing with exponential backoff.
    Returns seconds as int, or None if not found.
    """
    text = str(exc)
    # Format 1: retryDelay: '62s'
    m = re.search(r"retryDelay['\"\s:]+(\d+)s", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Format 2: retry_delay { seconds: 62 }
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Format 3: plain number followed by 's' anywhere near 'retry'
    m = re.search(r"retry.*?(\d+)\s*s\b", text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if 5 <= val <= 300:   # sanity range
            return val
    return None


def _generate_with_retry(
    client: genai.Client,
    gen_cfg: types.GenerateContentConfig,
    prompt: str,
    stream: bool = True,
) -> str:
    """
    Walk each model in the fallback chain.
    Per model: up to RETRY_MAX_ATTEMPTS tries with smart wait.

    Wait priority (highest wins):
      1. retryDelay from API error body  ← exact value the server requests
      2. Exponential backoff             ← fallback when API gives no hint
    """
    models_to_try = [config.GEMINI_MODEL] + config.FALLBACK_MODELS

    for model in models_to_try:
        backoff = config.RETRY_BASE_DELAY   # grows: 30 → 60 → 120 → 120

        for attempt in range(1, config.RETRY_MAX_ATTEMPTS + 1):
            try:
                return _call_model(client, gen_cfg, model, prompt, stream)

            except Exception as exc:
                if not _is_quota_error(exc):
                    raise               # non-quota errors surface immediately

                if attempt == config.RETRY_MAX_ATTEMPTS:
                    console.print(
                        f"\n[yellow]⚠  {model} exhausted after "
                        f"{attempt} attempts — switching model…[/yellow]"
                    )
                    break

                # Prefer the API's own suggested delay; fall back to backoff
                api_delay = _parse_retry_delay(exc)
                wait      = api_delay if api_delay else min(backoff, config.RETRY_MAX_DELAY)

                source = f"API says {api_delay}s" if api_delay else f"backoff {wait}s"
                console.print(
                    f"\n[yellow]⚠  429 on [bold]{model}[/bold] "
                    f"(attempt {attempt}/{config.RETRY_MAX_ATTEMPTS}) — "
                    f"waiting [bold]{wait}s[/bold] ({source})…[/yellow]"
                )
                time.sleep(wait)
                backoff = min(backoff * 2, config.RETRY_MAX_DELAY)

    raise RuntimeError(
        "\n[red]All Gemini models returned 429 RESOURCE_EXHAUSTED.[/red]\n\n"
        "Your free-tier daily quota is fully drained. Next steps:\n\n"
        "  Option 1 — Wait for quota reset (resets at midnight Pacific time)\n"
        "             Then re-run: python main.py --json sample_input.json --regen <section>\n"
        "             Already-saved sections will NOT be regenerated.\n\n"
        "  Option 2 — Add billing at console.cloud.google.com → quotas increase 10–100x\n\n"
        "  Option 3 — Use a second free API key\n"
        "             export GEMINI_API_KEY='your-second-key'\n"
        "             python main.py --json sample_input.json --regen <next-section>\n\n"
        "  Sections saved so far: check outputs/ folder."
    )


def _call_model(
    client: genai.Client,
    gen_cfg: types.GenerateContentConfig,
    model: str,
    prompt: str,
    stream: bool,
) -> str:
    """Single call to one model — streaming or blocking."""
    full = ""
    if stream:
        for chunk in client.models.generate_content_stream(
            model=model, contents=prompt, config=gen_cfg
        ):
            if chunk.text:
                console.print(chunk.text, end="", markup=False, highlight=False)
                full += chunk.text
        console.print()
    else:
        resp = client.models.generate_content(
            model=model, contents=prompt, config=gen_cfg
        )
        full = resp.text or ""
    return full


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
        return _generate_with_retry(self._client, self._gen_cfg, prompt, stream)

    # ── public: generate full syllabus ───────────────────────────
    def generate(self, course: CourseInput, output_dir: str = config.OUTPUT_DIR) -> dict[str, str]:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        sections: dict[str, str] = {}
        co_ctx = ""

        for idx, (key, label) in enumerate(self.SECTIONS):
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

            # Save immediately — if later sections 429-fail, nothing is lost
            _save_section(key, text, output_dir, course.course_title)

            # Build shared context once core section is done
            if key == "core":
                co_ctx = _extract_co_unit_context(text)

            # Polite pause between calls to stay under RPM limits
            if idx < len(self.SECTIONS) - 1:
                console.print(
                    f"[dim]  ⏸  Waiting {config.INTER_SECTION_DELAY}s before next section "
                    f"(rate-limit protection)…[/dim]"
                )
                time.sleep(config.INTER_SECTION_DELAY)

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
