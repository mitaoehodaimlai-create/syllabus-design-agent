"""All prompt-factory functions for the Syllabus Design Agent."""

from models import CourseInput


# ─────────────────────────────────────────────
# PROMPT 1 — Core Academic Design (Sections 1–4)
# ─────────────────────────────────────────────
def core_prompt(c: CourseInput) -> str:
    lab_note = (
        f"This course includes a lab component ({c.num_lab_modules} modules, "
        f"{c.num_lab_assignments} assignments)."
        if c.has_lab else ""
    )
    return f"""
You are designing a complete OBE-aligned course for the following parameters:

{c.summary()}
{lab_note}

Generate **Sections 1 through 4** of the course design exactly as specified below.
Use clean Markdown. Use ## for section titles, ### for sub-titles. Use standard Markdown tables.

---

## 1. COURSE PROFILE

### 1.1 Course Description
Write 3–4 sentences: scope, industry relevance, what students will achieve.

### 1.2 Course Objectives
List 5 measurable objectives using action verbs. Number them CO1–CO5.

---

## 2. COURSE OUTCOMES (COs)

Define exactly 5–6 COs. Use measurable Revised Bloom's Taxonomy (RBT) action verbs.
Present as a table:

| CO# | Course Outcome Statement | RBT Level | Domain |
|-----|--------------------------|-----------|--------|
| CO1 | ...                      | L2-Understand | Cognitive |

---

## 3. SDG ALIGNMENT

Identify 2–4 relevant UN SDGs. Present as a table:

| SDG # | SDG Name | Related COs | Related Units | Justification |
|-------|----------|-------------|---------------|---------------|

---

## 4. UNIT-WISE SYLLABUS

For each of the {c.num_units} units, provide the following structure exactly:

### Unit X: [Title]

**Learning Objectives:** (3–4 bullet points)

**Contact Hours:** [N hours]

**CO & Bloom's Mapping:** CO1(L3), CO2(L4) …

**Structured Content:**
1. Topic 1
   - Subtopic 1.1
   - Subtopic 1.2
2. Topic 2
   …

**Case Study:**
> Title: [Real-world industry/research case]
> Description: 2–3 sentences explaining the case and its relevance.

**Self-Learning Topics:**
- Topic A
- Topic B

**Further Reading:**
- Book / Paper / Link (with author/year)
- …

---
(Repeat for all {c.num_units} units)
"""


# ─────────────────────────────────────────────
# PROMPT 2 — Lesson Planning (Section 5)
# ─────────────────────────────────────────────
def lesson_plan_prompt(c: CourseInput, co_unit_context: str) -> str:
    total_theory_hrs = c.lectures_per_week * c.semester_duration_weeks
    total_tutorial_hrs = c.tutorials_per_week * c.semester_duration_weeks
    return f"""
Course: {c.course_title} | L-T-P: {c.ltp} | Weeks: {c.semester_duration_weeks} | Units: {c.num_units}
Total Theory Hours ≈ {total_theory_hrs} | Tutorial Hours ≈ {total_tutorial_hrs}
Total Contact Hours: {c.total_contact_hours}

COURSE OUTCOMES & UNITS ALREADY DEFINED:
{co_unit_context}

---

## 5. LESSON PLAN

### 5.1 Week-wise & Hour-wise Lesson Plan

Generate a complete lesson plan table for ALL {c.semester_duration_weeks} weeks.
Include mid-semester review (Week 8) and buffer/revision sessions.

| Week | Unit | Topic / Sub-topic | Hours | COs | Bloom's Level | Teaching Method | Teaching Aid | Engagement Activity | Formative Assessment | Homework / Self-Learning |
|------|------|-------------------|-------|-----|---------------|-----------------|--------------|---------------------|----------------------|--------------------------|
| 1    | U1   | …                 | {c.lectures_per_week}L+{c.tutorials_per_week}T | CO1 | L2 | Lecture + Discussion | PPT, Whiteboard | Think-Pair-Share | MCQ Quiz | Read Ch.1 |

Fill all {c.semester_duration_weeks} rows. Include mid-sem review and revision weeks explicitly.

### 5.2 Unit-wise Hour Summary

| Unit | Unit Title | Allocated Hours | COs Covered |
|------|------------|-----------------|-------------|

### 5.3 Mid-Semester Review Plan
Describe in 3–4 bullet points: what is reviewed, how, assessment method.

### 5.4 Buffer & Revision Sessions
List 2–3 buffer/revision sessions with week numbers and purpose.
"""


# ─────────────────────────────────────────────
# PROMPT 3 — Lab Design + Teaching Strategy + Assessment (Sections 6–8)
# ─────────────────────────────────────────────
def lab_strategy_assessment_prompt(c: CourseInput, co_unit_context: str) -> str:
    lab_section = ""
    if c.has_lab:
        lab_section = f"""
## 6. LAB / PRACTICAL DESIGN

### 6.1 Lab Overview
- Number of Modules: {c.num_lab_modules}
- Number of Assignments: {c.num_lab_assignments}
- Tools / Platforms: (list appropriate tools for the course)

### 6.2 Lab Experiments / Assignments

| # | Experiment / Assignment Title | Module | CO Mapping | Bloom's Level | Tools/Platform | Hours |
|---|-------------------------------|--------|------------|---------------|----------------|-------|

Generate {c.num_lab_assignments} lab assignments covering all COs progressively.
Include a mix of: setup/installation, algorithm implementation, analysis, project-based tasks.

---
"""
    return f"""
Course: {c.course_title} | Type: {c.course_type} | Credits: {c.total_credits}
{co_unit_context}

---
{lab_section}
## 7. TEACHING–LEARNING STRATEGY

### 7.1 Pedagogical Approaches
List and describe 5–6 specific methods used in this course:
- Active Learning (Flipped Classroom, Think-Pair-Share, etc.)
- Problem-Based Learning
- Case Study Method
- Project-Based Learning
- Experiential Learning
- ICT-Enabled Learning

For each method, specify: approach, when used (unit/week), expected outcome.

### 7.2 Industry Integration
- 2–3 mini-project ideas with industry relevance
- Real-world datasets or open-source tools to be used
- Guest lecture / industry visit suggestions

---

## 8. ASSESSMENT FRAMEWORK

### 8.1 Internal Assessment (CIE) — Weightage: 50 Marks
Present as a table:

| Component | Marks | Frequency | CO Coverage | Description |
|-----------|-------|-----------|-------------|-------------|

### 8.2 External Assessment (ESE) — Weightage: 50 Marks
Present as a table:

| Component | Marks | Duration | CO Coverage | Description |
|-----------|-------|----------|-------------|-------------|

### 8.3 Continuous Evaluation Strategy
- Portfolio / e-Portfolio approach
- Formative checkpoints (per unit)
- Peer & self-assessment opportunities
"""


# ─────────────────────────────────────────────
# PROMPT 4 — Assignments + Rubrics + CO–PO–PSO (Sections 9–11)
# ─────────────────────────────────────────────
def assignments_rubrics_mapping_prompt(c: CourseInput, co_unit_context: str) -> str:
    po_list = "\n".join(
        f"PO{i+1}: {po}" for i, po in enumerate(c.program_outcomes)
    ) if c.program_outcomes else "Use standard NBA PO1–PO12 for B.Tech programs."

    return f"""
Course: {c.course_title}
{co_unit_context}

Program Outcomes (POs):
{po_list}
PSO Count: {c.pso_count}

---

## 9. ASSIGNMENTS & ACTIVITIES

### 9.1 Assignments (Three Levels)

#### Assignment 1 — Beginner Level
- Title:
- CO Mapped:
- Bloom's Level: L1–L2
- Description: (3–4 lines, clear deliverable)
- Expected Output:

#### Assignment 2 — Intermediate Level
- Title:
- CO Mapped:
- Bloom's Level: L3–L4
- Description:
- Expected Output:

#### Assignment 3 — Advanced Level
- Title:
- CO Mapped:
- Bloom's Level: L5–L6
- Description: (project/research-oriented)
- Expected Output:

### 9.2 Experiential / Classroom Activities

#### Activity 1
- Type: (Role Play / Simulation / Group Discussion / Debate / Case Analysis)
- Description:
- CO Mapped:
- Duration:

#### Activity 2
- Type:
- Description:
- CO Mapped:
- Duration:

---

## 10. RUBRICS

### 10.1 Assignment Rubric

| Criteria | Excellent (4) | Good (3) | Satisfactory (2) | Needs Improvement (1) |
|----------|--------------|----------|-------------------|----------------------|

(Generate 5 criteria relevant to this course)

### 10.2 Lab / Practical Rubric (if applicable)

| Criteria | Excellent (4) | Good (3) | Satisfactory (2) | Needs Improvement (1) |
|----------|--------------|----------|-------------------|----------------------|

### 10.3 Presentation / Viva Rubric

| Criteria | Excellent (4) | Good (3) | Satisfactory (2) | Needs Improvement (1) |
|----------|--------------|----------|-------------------|----------------------|

---

## 11. CO–PO–PSO MAPPING

Use correlation levels: 3 = High, 2 = Medium, 1 = Low, — = No correlation

### 11.1 CO–PO Mapping

| CO \\ PO | PO1 | PO2 | PO3 | PO4 | PO5 | PO6 | PO7 | PO8 | PO9 | PO10 | PO11 | PO12 |
|----------|-----|-----|-----|-----|-----|-----|-----|-----|-----|------|------|------|
| CO1      |     |     |     |     |     |     |     |     |     |      |      |      |
| CO2      |     |     |     |     |     |     |     |     |     |      |      |      |
| CO3      |     |     |     |     |     |     |     |     |     |      |      |      |
| CO4      |     |     |     |     |     |     |     |     |     |      |      |      |
| CO5      |     |     |     |     |     |     |     |     |     |      |      |      |

### 11.2 CO–PSO Mapping

| CO \\ PSO | PSO1 | PSO2 | PSO3 |
|-----------|------|------|------|
| CO1       |      |      |      |
| CO2       |      |      |      |
| CO3       |      |      |      |
| CO4       |      |      |      |
| CO5       |      |      |      |
"""


# ─────────────────────────────────────────────
# PROMPT 5 — Question Bank + Resources + Learner Support + Cross-cutting (Sections 12–15)
# ─────────────────────────────────────────────
def resources_support_prompt(c: CourseInput, co_unit_context: str) -> str:
    lab_qb = ""
    if c.has_lab:
        lab_qb = """
### 12.2 Lab / Viva Question Bank

| Q# | Question | CO | Bloom's | Difficulty |
|----|----------|----|---------|------------|

(Generate 10 lab/viva questions)
"""
    return f"""
Course: {c.course_title} | Units: {c.num_units} | Credits: {c.total_credits}
{co_unit_context}

---

## 12. QUESTION BANK

### 12.1 Theory Question Bank

Generate at least **20 questions** covering all units and COs.

| Q# | Question | Unit | CO | Bloom's Level | Difficulty | Marks |
|----|----------|------|----|---------------|------------|-------|

Include:
- 6 Beginner questions (L1–L2): Recall and comprehension
- 8 Intermediate questions (L3–L4): Application and Analysis
- 6 Advanced questions (L5–L6): Evaluation and Creation
{lab_qb}

---

## 13. LEARNING RESOURCES

### 13.1 Textbooks
List 2–3 textbooks with: Author, Title, Edition, Publisher, Year.

### 13.2 Reference Books
List 3–5 reference books with full citation.

### 13.3 Online Resources (MOOCs / NPTEL / Documentation)

| Platform | Course / Resource Name | URL | Relevance to Units |
|----------|------------------------|-----|--------------------|

### 13.4 Knowledge Base (Research Papers / GitHub / Datasets)

| Type | Title / Name | Source / Link | Applicable COs |
|------|--------------|---------------|----------------|

---

## 14. LEARNER DIFFERENTIATION

### 14.1 Slow Learners — Remedial & Scaffolding Strategies
- (4–5 specific strategies with examples)

### 14.2 Average Learners — Guided Practice Strategies
- (4–5 strategies)

### 14.3 Advanced Learners — Challenge & Research Exposure
- (4–5 strategies: research tasks, competitive challenges, open-source contributions)

---

## 15. CROSS-CUTTING INTEGRATION

### 15.1 Industry Relevance & Emerging Trends
- Current industry applications of this course content
- Emerging tools, frameworks, or research directions (2–3)

### 15.2 Ethical Considerations
- Relevant ethical issues specific to this domain
- How ethics is integrated in course activities or assessments

### 15.3 Sustainability Integration (SDG Linkage)
- Specific sustainability themes addressed in the course
- How SDGs are operationalized in assignments or projects
"""
