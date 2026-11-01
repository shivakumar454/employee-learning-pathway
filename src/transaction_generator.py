 
import csv
import random
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "generated"

SEED = 20261022
TARGET_ENROLLMENTS = 10_000
COMPLETION_THRESHOLD = 70


def read_csv(filename):
    path = DATA_DIR / filename

    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def write_csv(filename, rows):
    if not rows:
        raise ValueError(f"No records generated for {filename}")

    path = DATA_DIR / filename

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{filename}: {len(rows):,} records")


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def generate_transactions():
    rng = random.Random(SEED)

    employees = read_csv("employees.csv")
    courses = read_csv("courses.csv")
    prerequisites = read_csv("prerequisites.csv")

    employee_ids = [e["employee_id"] for e in employees]

    # Build prerequisite relationships.
    prerequisite_map = defaultdict(set)

    for row in prerequisites:
        prerequisite_map[row["course_id"]].add(
            row["prerequisite_course_id"]
        )

    # Track enrollment capacity and completed courses.
    capacity_used = defaultdict(int)
    completed_courses = defaultdict(set)
    enrolled_pairs = set()

    enrollments = []
    completions = []
    enrollment_events = []

    # Only active courses are eligible.
    eligible_courses = [
        course for course in courses
        if course["course_status"] == "ACTIVE"
        and int(course["capacity"]) > 0
    ]

    if not eligible_courses:
        raise ValueError("No active courses available.")

    attempts = 0
    max_attempts = TARGET_ENROLLMENTS * 100

    while len(enrollments) < TARGET_ENROLLMENTS:

        attempts += 1

        if attempts > max_attempts:
            raise RuntimeError(
                f"Generated only {len(enrollments)} enrollments. "
                "Could not find enough valid combinations."
            )

        employee_id = rng.choice(employee_ids)
        course = rng.choice(eligible_courses)

        course_id = course["course_id"]
        pair = (employee_id, course_id)

        # Prevent duplicate employee-course enrollment.
        if pair in enrolled_pairs:
            continue

        # Check course capacity.
        if capacity_used[course_id] >= int(course["capacity"]):
            continue

        # Check prerequisites.
        required_courses = prerequisite_map[course_id]

        if not required_courses.issubset(
            completed_courses[employee_id]
        ):
            continue

        # Calculate valid enrollment and completion dates.
        available_from = parse_date(course["available_from"])
        available_to = parse_date(course["available_to"])

        if available_to < available_from:
            continue

        duration_hours = int(course["duration_hours"])
        duration_days = max(1, (duration_hours + 7) // 8)

        # A completed course must finish within availability.
        latest_start_date = available_to - timedelta(
            days=duration_days
        )

        if latest_start_date < available_from:
            continue

        date_range = (latest_start_date - available_from).days

        enrolled_date = available_from + timedelta(
            days=rng.randint(0, date_range)
        )

        # Generate lifecycle status.
        status_roll = rng.random()

        if status_roll < 0.50:
            status = "COMPLETED"
        elif status_roll < 0.75:
            status = "IN_PROGRESS"
        elif status_roll < 0.90:
            status = "ENROLLED"
        else:
            status = "CANCELLED"

        enrollment_id = f"ENR-{employee_id}-{course_id}"

        enrollments.append({
            "enrollment_id": enrollment_id,
            "employee_id": employee_id,
            "course_id": course_id,
            "enrolled_at": enrolled_date.isoformat(),
            "status": status,
        })

        enrolled_pairs.add(pair)
        capacity_used[course_id] += 1

        # Every enrollment has an ENROLLED event.
        enrollment_events.append({
            "event_id": f"EVT-{len(enrollment_events) + 1:07d}",
            "enrollment_id": enrollment_id,
            "event_type": "ENROLLED",
            "event_at": enrolled_date.isoformat(),
        })

        if status == "IN_PROGRESS":

            event_date = enrolled_date + timedelta(days=1)

            enrollment_events.append({
                "event_id": f"EVT-{len(enrollment_events) + 1:07d}",
                "enrollment_id": enrollment_id,
                "event_type": "STARTED",
                "event_at": event_date.isoformat(),
            })

        elif status == "COMPLETED":

            completion_date = enrolled_date + timedelta(
                days=duration_days
            )

            score = rng.randint(40, 100)

            outcome = (
                "PASSED"
                if score >= COMPLETION_THRESHOLD
                else "FAILED"
            )

            completion_id = (
                f"CMP-2026-{len(completions) + 1:06d}"
            )

            completions.append({
                "completion_id": completion_id,
                "enrollment_id": enrollment_id,
                "employee_id": employee_id,
                "course_id": course_id,
                "completed_at": completion_date.isoformat(),
                "score": score,
                "outcome": outcome,
            })

            enrollment_events.append({
                "event_id": f"EVT-{len(enrollment_events) + 1:07d}",
                "enrollment_id": enrollment_id,
                "event_type": "COMPLETED",
                "event_at": completion_date.isoformat(),
            })

            # Only passed courses satisfy prerequisites.
            if outcome == "PASSED":
                completed_courses[employee_id].add(course_id)

        elif status == "CANCELLED":

            cancellation_date = enrolled_date + timedelta(days=1)

            enrollment_events.append({
                "event_id": f"EVT-{len(enrollment_events) + 1:07d}",
                "enrollment_id": enrollment_id,
                "event_type": "CANCELLED",
                "event_at": cancellation_date.isoformat(),
            })

    # Write generated datasets.
    write_csv("enrollments.csv", enrollments)
    write_csv("completions.csv", completions)
    write_csv("enrollment_events.csv", enrollment_events)

    print("\nTRANSACTION GENERATION COMPLETE")
    print("=" * 40)
    print(f"Seed: {SEED}")
    print(f"Enrollments: {len(enrollments):,}")
    print(f"Completions: {len(completions):,}")
    print(f"Enrollment events: {len(enrollment_events):,}")


if __name__ == "__main__":
    generate_transactions()
