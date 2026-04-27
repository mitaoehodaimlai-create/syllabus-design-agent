import os

# Primary model — gemini-1.5-flash-8b has the highest free-tier RPD (requests/day)
# and a separate quota bucket from gemini-2.0-flash, so it survives when 2.0-flash is drained
GEMINI_MODEL = "gemini-1.5-flash-8b"

# Fallback chain — walked in order when the current model returns 429
# Each is a completely independent quota bucket on Google's side
FALLBACK_MODELS = [
    "gemini-1.5-flash",     # separate bucket, 15 RPM free
    "gemini-2.0-flash",     # original primary — try again after others
    "gemini-1.5-pro",       # lowest RPM (2/min) but rarely exhausted
]

# Halved from 8192 → cuts per-request token cost, reduces quota pressure
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE       = 0.35
OUTPUT_DIR        = "outputs"

# ── Retry / rate-limit tuning ─────────────────────────────────────
RETRY_MAX_ATTEMPTS  = 4    # tries per model before moving to next fallback
RETRY_BASE_DELAY    = 30   # seconds — Gemini free quota window is ~60s, start at half
RETRY_MAX_DELAY     = 120  # cap: never wait more than 2 minutes per attempt
INTER_SECTION_DELAY = 30   # seconds between the 5 section calls (keeps RPM << 15)

SYSTEM_INSTRUCTION = """You are an expert academic curriculum designer specializing in:
- Outcome-Based Education (OBE) aligned with NBA/NAAC accreditation standards
- Revised Bloom's Taxonomy (RBT) for learning outcome design
- Instructional design: lesson planning, assessment frameworks, pedagogical strategies
- Industry-academia integration, SDG alignment, and learner differentiation

Generate structured, audit-ready academic content in clean Markdown format.
Always use standard Markdown tables (| col | col |) for tabular data.
Use ## for section headings, ### for sub-section headings.
Be concise, measurable, and directly usable for accreditation documentation.
"""
