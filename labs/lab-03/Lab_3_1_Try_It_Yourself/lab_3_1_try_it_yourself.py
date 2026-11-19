"""Lab 3.1 (Try It Yourself) - Course Prerequisites: Reference vs. Embed

Models prerequisite relationships between university courses using references
(prerequisite_codes array) rather than embedding full course documents, and
uses $lookup to resolve prerequisite details.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.connection import get_db, reset_collection, banner
from rich.console import Console
from rich.table import Table

console = Console()

COURSES_WITH_PREREQS = [
    {
        "course_code": "AIML101",
        "course_name": "Introduction to Machine Learning",
        "instructor": "Dr. Priya Sharma",
        "credits": 4,
        "prerequisite_codes": [],
        "schedule": {"days": ["Monday", "Wednesday"], "time": "10:00-11:30", "room": "LH-201"},
    },
    {
        "course_code": "AIML201",
        "course_name": "Natural Language Processing",
        "instructor": "Dr. Meera Joshi",
        "credits": 3,
        "prerequisite_codes": ["AIML101"],
        "schedule": {"days": ["Monday", "Wednesday", "Friday"], "time": "09:00-10:00", "room": "LH-102"},
    },
    {
        "course_code": "AIML301",
        "course_name": "Deep Learning with PyTorch",
        "instructor": "Dr. Anil Gupta",
        "credits": 3,
        "prerequisite_codes": ["AIML101", "AIML201"],
        "schedule": {"days": ["Tuesday", "Thursday"], "time": "14:00-15:30", "room": "LH-305"},
    },
]


def main():
    banner("Lab 3.1 (Try It Yourself): Course Prerequisites Design")

    col = reset_collection("lab_3", "courses_prerequisites")
    col.insert_many(COURSES_WITH_PREREQS)
    print(f"[OK] Inserted {len(COURSES_WITH_PREREQS)} courses with prerequisite references.\n")

    # Resolve prerequisites using $lookup
    pipeline = [
        {
            "$lookup": {
                "from": "courses_prerequisites",
                "localField": "prerequisite_codes",
                "foreignField": "course_code",
                "as": "prerequisite_details",
            }
        }
    ]
    resolved = list(col.aggregate(pipeline))

    table = Table(title="Course Prerequisite Graph (Referenced Design)", show_lines=True)
    table.add_column("Code", style="cyan", width=10)
    table.add_column("Course Name", width=32)
    table.add_column("Instructor", width=18)
    table.add_column("Prerequisite Codes", style="magenta", width=20)
    table.add_column("Resolved Prerequisites", style="green", width=36)

    for c in resolved:
        prereq_codes = ", ".join(c["prerequisite_codes"]) or "None"
        prereq_names = ", ".join(p["course_name"] for p in c["prerequisite_details"]) or "None (Entry-level)"
        table.add_row(c["course_code"], c["course_name"], c["instructor"], prereq_codes, prereq_names)

    console.print(table)

    print("\n--- Design Justification: Why REFERENCING is Best for Prerequisites ---")
    print("  1. Independent Entities: Courses have their own lifecycles, rosters, and schedules.")
    print("  2. Avoids Recursive Nesting: Embedding full prerequisite courses creates deep")
    print("     duplication (e.g., AIML301 -> AIML201 -> AIML101) and wastes storage.")
    print("  3. Single Source of Truth: If AIML101's title or schedule changes, only 1 document")
    print("     needs updating; all referencing courses automatically see the updated data via $lookup.")

    banner("Lab 3.1 (Try It Yourself) Complete")


if __name__ == "__main__":
    main()
