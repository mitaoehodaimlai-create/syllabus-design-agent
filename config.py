import os

# Primary model — fastest, highest free-tier RPM
GEMINI_MODEL = "gemini-2.0-flash"

# Fallback chain tried in order when 429 is hit on the primary model
FALLBACK_MODELS = [
    "gemini-1.5-flash",        # older flash — separate quota bucket
    "gemini-1.5-flash-8b",     # smallest/cheapest — highest free RPM
    "gemini-1.5-pro",          # pro — lower RPM but separate bucket
]

MAX_OUTPUT_TOKENS = 8192
TEMPERATURE = 0.35
OUTPUT_DIR = "outputs"

# Retry / rate-limit settings
RETRY_MAX_ATTEMPTS  = 5       # attempts per model before moving to fallback
RETRY_BASE_DELAY    = 10      # seconds — first wait after a 429
RETRY_MAX_DELAY     = 120     # seconds — cap on exponential growth
INTER_SECTION_DELAY = 8       # seconds to pause between the 5 section calls

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
