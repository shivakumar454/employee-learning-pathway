
import csv
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "generated"


def read_csv(filename):
    with (DATA_DIR / filename).open(
        "r", newline="", encoding="utf-8"
    ) as file:
        return list(csv.DictReader(file))


def to_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def validate():
    employees = read_csv("employees.csv")
    courses = read_csv("courses.csv")
    enrollments = read_csv("enrollments.csv")
    completions = read_csv("completions.csv")
    events = read_csv("enrollment_events.csv")
    prerequisites = read_csv("prerequisites.csv")

    employee_ids = {r["employee_id"] for r in employees}
    course_map = {r["course_id"]: r for r in courses}
    enrollment_map = {r["enrollment_id"]: r for r in enrollments}

    errors = []
    warnings = []

    # 1. Enrollment primary keys and foreign keys.
    enrollment_ids = [r["enrollment_id"] for r in enrollments]
    if len(enrollment_ids) != len(set(enrollment_ids)):
        errors.append("Duplicate enrollment IDs found.")

    pairs = [
        (r["employee_id"], r["course_id"])
        for r in enrollments
    ]
    if len(pairs) != len(set(pairs)):
        errors.append("Duplicate employee-course enrollments found.")

    for row in enrollments:
        if row["employee_id"] not in employee_ids:
            errors.append(
                f"Invalid employee ID in {row['enrollment_id']}"
            )

        if row["course_id"] not in course_map:
            errors.append(
                f"Invalid course ID in {row['enrollment_id']}"
            )
            continue

        course = course_map[row["course_id"]]
        enrolled_date = to_date(row["enrolled_at"])

        if row["status"] not in {
            "ENROLLED", "IN_PROGRESS", "COMPLETED", "CANCELLED"
        }:
            errors.append(
                f"Invalid enrollment status: {row['status']}"
            )

        if not (
            to_date(course["available_from"])
            <= enrolled_date
            <= to_date(course["available_to"])
        ):
            errors.append(
                f"Enrollment outside course availability: "
                f"{row['enrollment_id']}"
            )

    # 2. Course capacity.
    course_counts = Counter(r["course_id"] for r in enrollments)

    for course_id, count in course_counts.items():
        if course_id in course_map:
            capacity = int(course_map[course_id]["capacity"])
            if count > capacity:
                errors.append(
                    f"Capacity exceeded for {course_id}: "
                    f"{count}/{capacity}"
                )

    # 3. Completion integrity.
    completion_ids = [r["completion_id"] for r in completions]
    if len(completion_ids) != len(set(completion_ids)):
        errors.append("Duplicate completion IDs found.")

    completions_by_enrollment = defaultdict(list)

    for row in completions:
        enrollment_id = row["enrollment_id"]
        completions_by_enrollment[enrollment_id].append(row)

        enrollment = enrollment_map.get(enrollment_id)

        if enrollment is None:
            errors.append(
                f"Completion references unknown enrollment: "
                f"{enrollment_id}"
            )
            continue

        if row["employee_id"] != enrollment["employee_id"]:
            errors.append(
                f"Completion employee mismatch: {enrollment_id}"
            )

        if row["course_id"] != enrollment["course_id"]:
            errors.append(
                f"Completion course mismatch: {enrollment_id}"
            )

        if enrollment["status"] != "COMPLETED":
            errors.append(
                f"Completion exists for non-completed enrollment: "
                f"{enrollment_id}"
            )

        if int(row["score"]) < 0 or int(row["score"]) > 100:
            errors.append(f"Invalid score: {row['completion_id']}")

        expected_outcome = (
            "PASSED" if int(row["score"]) >= 70 else "FAILED"
        )

        if row["outcome"] != expected_outcome:
            errors.append(
                f"Score/outcome mismatch: {row['completion_id']}"
            )

        if to_date(row["completed_at"]) < to_date(
            enrollment["enrolled_at"]
        ):
            errors.append(
                f"Completion before enrollment: {enrollment_id}"
            )

    for row in enrollments:
        count = len(completions_by_enrollment[row["enrollment_id"]])

        if row["status"] == "COMPLETED" and count != 1:
            errors.append(
                f"Completed enrollment must have one completion: "
                f"{row['enrollment_id']}"
            )

        if row["status"] != "COMPLETED" and count != 0:
            errors.append(
                f"Non-completed enrollment has completion: "
                f"{row['enrollment_id']}"
            )

    # 4. Enrollment event integrity.
    event_ids = [r["event_id"] for r in events]

    if len(event_ids) != len(set(event_ids)):
        errors.append("Duplicate event IDs found.")

    events_by_enrollment = defaultdict(list)

    for row in events:
        enrollment_id = row["enrollment_id"]
        events_by_enrollment[enrollment_id].append(row)

        if enrollment_id not in enrollment_map:
            errors.append(
                f"Event references unknown enrollment: {enrollment_id}"
            )

        if row["event_type"] not in {
            "ENROLLED", "STARTED", "COMPLETED", "CANCELLED"
        }:
            errors.append(
                f"Invalid event type: {row['event_type']}"
            )

    for enrollment_id, rows in events_by_enrollment.items():
        dates = [to_date(r["event_at"]) for r in rows]

        if dates != sorted(dates):
            errors.append(
                f"Events are not chronologically ordered: {enrollment_id}"
            )

    # 5. Prerequisite validation.
    prerequisite_map = defaultdict(set)

    for row in prerequisites:
        prerequisite_map[row["course_id"]].add(
            row["prerequisite_course_id"]
        )

    passed_courses = defaultdict(list)

    for row in completions:
        if row["outcome"] == "PASSED":
            passed_courses[row["employee_id"]].append({
                "course_id": row["course_id"],
                "completed_at": to_date(row["completed_at"]),
            })

    for row in enrollments:
        required = prerequisite_map[row["course_id"]]

        for prerequisite_course in required:
            valid_completion = any(
                item["course_id"] == prerequisite_course
                and item["completed_at"] < to_date(row["enrolled_at"])
                for item in passed_courses[row["employee_id"]]
            )

            if not valid_completion:
                errors.append(
                    f"Prerequisite not completed before enrollment: "
                    f"{row['enrollment_id']} requires "
                    f"{prerequisite_course}"
                )

    # 6. Course completion availability check.
    for row in completions:
        course = course_map.get(row["course_id"])

        if course and to_date(row["completed_at"]) > to_date(
            course["available_to"]
        ):
            warnings.append(
                f"Completion after course availability window: "
                f"{row['enrollment_id']}"
            )

    print("\nTRANSACTION VALIDATION REPORT")
    print("=" * 45)
    print(f"Employees: {len(employees):,}")
    print(f"Courses: {len(courses):,}")
    print(f"Enrollments: {len(enrollments):,}")
    print(f"Completions: {len(completions):,}")
    print(f"Events: {len(events):,}")
    print(f"Errors: {len(errors):,}")
    print(f"Warnings: {len(warnings):,}")

    if errors:
        print("\nERRORS (first 20)")
        for error in errors[:20]:
            print("-", error)

    if warnings:
        print("\nWARNINGS (first 20)")
        for warning in warnings[:20]:
            print("-", warning)

    if not errors:
        print("\nNo validation errors found.")
    else:
        print("\nValidation FAILED. Fix errors before proceeding.")

    return len(errors) == 0


if __name__ == "__main__":
    validate()
