
import argparse
import csv
import random
from pathlib import Path
from datetime import date, timedelta

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261022

DEPARTMENTS = [
    "Engineering", "Data", "Product", "Design", "Finance",
    "HR", "Operations", "Marketing", "Sales", "Security"
]

ROLE_NAMES = [
    "Junior Software Engineer", "Software Engineer",
    "Senior Software Engineer", "Backend Developer",
    "Frontend Developer", "Full Stack Developer",
    "Data Analyst", "Senior Data Analyst",
    "Data Engineer", "Senior Data Engineer",
    "Machine Learning Engineer", "AI Engineer",
    "DevOps Engineer", "Cloud Engineer",
    "QA Engineer", "Product Manager",
    "Business Analyst", "UX Designer",
    "UI Designer", "Security Engineer",
    "HR Specialist", "Finance Analyst",
    "Operations Analyst", "Sales Executive",
    "Technical Lead"
]

SKILL_CATEGORIES = ["TECHNICAL", "PROFESSIONAL", "DOMAIN"]

START_DATE = date(2026, 1, 1)
END_DATE = date(2027, 12, 31)


def write_csv(output_dir, filename, rows):
    if not rows:
        return

    path = output_dir / filename

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def random_date(rng, start=START_DATE, end=END_DATE):
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, days))


def generate_master_data(
    employee_count=5000,
    skill_count=500,
    course_count=1000,
    seed=SEED,
    output_dir=None
):
    rng = random.Random(seed)

    if output_dir is None:
        output_dir = ROOT / "data" / "generated"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # 1. ROLES
    # -------------------------------------------------
    roles = []

    for i, name in enumerate(ROLE_NAMES, start=1):
        roles.append({
            "role_id": f"ROLE-{i:04d}",
            "role_name": name,
            "role_level": min(10, 1 + (i - 1) % 6),
            "career_track": (
                "ENGINEERING" if i <= 15
                else "BUSINESS" if i <= 24
                else "LEADERSHIP"
            ),
            "description": f"Career role: {name}"
        })

    # -------------------------------------------------
    # 2. SKILLS
    # -------------------------------------------------
    skill_prefixes = [
        "Python", "Java", "SQL", "JavaScript", "React",
        "Node.js", "AWS", "Docker", "Kubernetes", "Git",
        "Communication", "Leadership", "Problem Solving",
        "Project Management", "System Design"
    ]

    skills = []

    for i in range(1, skill_count + 1):
        category = rng.choice(SKILL_CATEGORIES)

        if i <= len(skill_prefixes):
            name = skill_prefixes[i - 1]
        else:
            name = f"{category.title()} Skill {i:04d}"

        skills.append({
            "skill_id": f"SKL-{i:06d}",
            "skill_name": name,
            "skill_category": category,
            "description": f"Skill definition for {name}"
        })

    skill_ids = [s["skill_id"] for s in skills]

    # -------------------------------------------------
    # 3. ROLE SKILL TARGETS
    # -------------------------------------------------
    role_skill_targets = []
    role_skill_lookup = {}

    for role in roles:
        selected_skills = rng.sample(skill_ids, 30)
        role_skill_lookup[role["role_id"]] = selected_skills

        for skill_id in selected_skills:
            role_skill_targets.append({
                "target_id": f"RST-{len(role_skill_targets) + 1:07d}",
                "role_id": role["role_id"],
                "skill_id": skill_id,
                "target_proficiency": rng.randint(3, 5),
                "effective_from": "2026-01-01",
                "effective_to": ""
            })

    # -------------------------------------------------
    # 4. EMPLOYEES
    # -------------------------------------------------
    employees = []

    for i in range(1, employee_count + 1):
        role = rng.choice(roles)
        department = rng.choice(DEPARTMENTS)

        # Managers are selected from an earlier employee range.
        manager_id = ""
        if i > 100:
            manager_id = f"EMP-{rng.randint(1, min(100, employee_count)):06d}"

        employees.append({
            "employee_id": f"EMP-{i:06d}",
            "employee_name": f"Employee {i:06d}",
            "email": f"employee{i:06d}@example.com",
            "department": department,
            "role_id": role["role_id"],
            "manager_id": manager_id,
            "hire_date": random_date(
                rng, date(2018, 1, 1), date(2026, 6, 30)
            ).isoformat(),
            "employment_status": rng.choices(
                ["ACTIVE", "INACTIVE", "ON_LEAVE"],
                weights=[90, 5, 5]
            )[0]
        })

    # -------------------------------------------------
    # 5. EMPLOYEE SKILL ASSESSMENTS
    # -------------------------------------------------
    employee_skills = []

    for employee in employees:
        role_skills = role_skill_lookup[employee["role_id"]]

        # Each employee has 15-30 assessed skills from their role.
        selected = rng.sample(
            role_skills,
            rng.randint(15, len(role_skills))
        )

        for skill_id in selected:
            employee_skills.append({
                "employee_skill_id": (
                    f"ESK-{len(employee_skills) + 1:08d}"
                ),
                "employee_id": employee["employee_id"],
                "skill_id": skill_id,
                "proficiency": rng.randint(1, 5),
                "assessed_at": (
                    random_date(rng, date(2025, 1, 1), date(2026, 10, 1))
                    .isoformat() + "T10:00:00"
                ),
                "assessment_source": rng.choices(
                    ["SELF", "MANAGER", "TEST"],
                    weights=[30, 40, 30]
                )[0]
            })

    # -------------------------------------------------
    # 6. COURSES
    # -------------------------------------------------
    courses = []

    for i in range(1, course_count + 1):
        available_from = random_date(
            rng, date(2026, 1, 1), date(2027, 6, 30)
        )
        available_to = available_from + timedelta(
            days=rng.randint(90, 365)
        )

        courses.append({
            "course_id": f"CRS-{i:06d}",
            "course_name": f"Learning Course {i:04d}",
            "provider": rng.choice([
                "Internal Academy", "Learning Hub",
                "Tech Academy", "External Training Partner"
            ]),
            "duration_hours": rng.choice([4, 8, 12, 16, 24, 40, 60]),
            "cost_inr": f"{rng.choice([500, 1000, 1500, 2500, 5000, 8000, 12000]):.2f}",
            "capacity": rng.randint(10, 100),
            "available_from": available_from.isoformat(),
            "available_to": available_to.isoformat(),
            "course_level": rng.randint(1, 5),
            "course_status": rng.choices(
                ["ACTIVE", "INACTIVE", "CANCELLED"],
                weights=[85, 10, 5]
            )[0]
        })

    # -------------------------------------------------
    # 7. COURSE SKILL MAPPINGS
    # -------------------------------------------------
    course_skills = []

    for course in courses:
        selected_skills = rng.sample(skill_ids, rng.randint(4, 8))

        for skill_id in selected_skills:
            course_skills.append({
                "course_skill_id": (
                    f"CSM-{len(course_skills) + 1:08d}"
                ),
                "course_id": course["course_id"],
                "skill_id": skill_id,
                "proficiency_gain": rng.randint(1, 3)
            })

    # -------------------------------------------------
    # 8. PREREQUISITES
    # -------------------------------------------------
    prerequisites = []

    # Only reference earlier courses, which prevents cycles.
    for i in range(20, course_count + 1):
        if rng.random() < 0.30:
            prerequisite_course_number = rng.randint(1, i - 1)

            prerequisites.append({
                "prerequisite_id": (
                    f"PRE-{len(prerequisites) + 1:06d}"
                ),
                "course_id": f"CRS-{i:06d}",
                "prerequisite_course_id": (
                    f"CRS-{prerequisite_course_number:06d}"
                ),
                "minimum_proficiency": rng.choice(["", 2, 3, 4])
            })

    # -------------------------------------------------
    # 9. DEPARTMENT BUDGETS
    # -------------------------------------------------
    budgets = []

    for department in DEPARTMENTS:
        budgets.append({
            "budget_id": f"BUD-{department}-2026",
            "department": department,
            "fiscal_year": 2026,
            "allocated_amount": f"{rng.randint(500000, 2000000):.2f}",
            "currency": "INR",
            "effective_from": "2026-01-01",
            "effective_to": "2026-12-31"
        })

    # -------------------------------------------------
    # EXPORT
    # -------------------------------------------------
    datasets = {
        "roles.csv": roles,
        "skills.csv": skills,
        "employees.csv": employees,
        "role_skill_targets.csv": role_skill_targets,
        "employee_skills.csv": employee_skills,
        "courses.csv": courses,
        "course_skills.csv": course_skills,
        "prerequisites.csv": prerequisites,
        "budgets.csv": budgets
    }

    for filename, rows in datasets.items():
        write_csv(output_dir, filename, rows)

    print("\nMASTER DATA GENERATION COMPLETE")
    print(f"Seed: {seed}")
    print(f"Output: {output_dir}")

    for filename, rows in datasets.items():
        print(f"{filename}: {len(rows):,} records")

    return datasets


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--employees", type=int, default=5000)
    parser.add_argument("--skills", type=int, default=500)
    parser.add_argument("--courses", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", default="data/generated")

    args = parser.parse_args()

    if min(args.employees, args.skills, args.courses) < 1:
        parser.error("All entity counts must be positive")

    generate_master_data(
        employee_count=args.employees,
        skill_count=args.skills,
        course_count=args.courses,
        seed=args.seed,
        output_dir=ROOT / args.output
    )
