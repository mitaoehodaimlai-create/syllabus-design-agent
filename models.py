from dataclasses import dataclass, field
from typing import List


@dataclass
class CourseInput:
    course_title: str
    course_code: str = ""
    class_year: str = "TY"
    department: str = ""
    program: str = "B.Tech"
    discipline: str = ""
    course_type: str = "Theory"          # Theory | Lab | Hybrid
    lectures_per_week: int = 3
    tutorials_per_week: int = 1
    practicals_per_week: int = 0
    total_credits: int = 4
    total_contact_hours: int = 48
    num_units: int = 5
    semester_duration_weeks: int = 16
    prerequisites: str = ""
    num_lab_modules: int = 0
    num_lab_assignments: int = 0
    program_outcomes: List[str] = field(default_factory=list)
    pso_count: int = 3
    university: str = ""

    @property
    def ltp(self) -> str:
        return f"{self.lectures_per_week}-{self.tutorials_per_week}-{self.practicals_per_week}"

    @property
    def has_lab(self) -> bool:
        return self.practicals_per_week > 0 or self.course_type in ("Lab", "Hybrid")

    def summary(self) -> str:
        return (
            f"Course Title: {self.course_title}\n"
            f"Course Code: {self.course_code}\n"
            f"Class: {self.class_year} | Program: {self.program} | Discipline: {self.discipline}\n"
            f"Department: {self.department} | University: {self.university}\n"
            f"Course Type: {self.course_type} | L-T-P: {self.ltp}\n"
            f"Credits: {self.total_credits} | Total Contact Hours: {self.total_contact_hours}\n"
            f"Units: {self.num_units} | Semester Duration: {self.semester_duration_weeks} weeks\n"
            f"Prerequisites: {self.prerequisites or 'None'}\n"
        )
