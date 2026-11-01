from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated"


def load_csv(filename):
    path = DATA / filename
    assert path.exists(), f"Missing file: {path}"
    return pd.read_csv(path)


def assert_unique_non_null(df, column, filename):
    assert df[column].notna().all(), f"{filename}.{column} has null values"
    assert df[column].is_unique, f"{filename}.{column} has duplicates"


def test_primary_keys_are_unique():
    keys = {
        "roles.csv": "role_id",
        "skills.csv": "skill_id",
        "employees.csv": "employee_id",
        "courses.csv": "course_id",
        "enrollments.csv": "enrollment_id",
        "completions.csv": "completion_id",
    }

    for filename, column in keys.items():
        assert_unique_non_null(load_csv(filename), column, filename)


def test_employee_foreign_keys():
    employees = load_csv("employees.csv")
    roles = load_csv("roles.csv")

    assert set(employees["role_id"]).issubset(set(roles["role_id"]))

    employee_ids = set(employees["employee_id"])
    manager_ids = set(employees["manager_id"].dropna())

    assert manager_ids.issubset(employee_ids)


def test_skill_relationships():
    employees = load_csv("employees.csv")
    roles = load_csv("roles.csv")
    skills = load_csv("skills.csv")
    employee_skills = load_csv("employee_skills.csv")
    targets = load_csv("role_skill_targets.csv")

    assert set(employee_skills["employee_id"]).issubset(set(employees["employee_id"]))
    assert set(employee_skills["skill_id"]).issubset(set(skills["skill_id"]))
    assert set(targets["role_id"]).issubset(set(roles["role_id"]))
    assert set(targets["skill_id"]).issubset(set(skills["skill_id"]))

    assert employee_skills["proficiency"].between(1, 5).all()
    assert targets["target_proficiency"].between(1, 5).all()


def test_course_relationships():
    courses = load_csv("courses.csv")
    skills = load_csv("skills.csv")
    course_skills = load_csv("course_skills.csv")
    prerequisites = load_csv("prerequisites.csv")

    course_ids = set(courses["course_id"])
    skill_ids = set(skills["skill_id"])

    assert set(course_skills["course_id"]).issubset(course_ids)
    assert set(course_skills["skill_id"]).issubset(skill_ids)
    assert set(prerequisites["course_id"]).issubset(course_ids)
    assert set(prerequisites["prerequisite_course_id"]).issubset(course_ids)


def test_course_values():
    courses = load_csv("courses.csv")

    assert (courses["duration_hours"] > 0).all()
    assert (courses["cost_inr"] >= 0).all()
    assert (courses["capacity"] > 0).all()


def test_enrollment_relationships():
    employees = load_csv("employees.csv")
    courses = load_csv("courses.csv")
    enrollments = load_csv("enrollments.csv")

    assert set(enrollments["employee_id"]).issubset(set(employees["employee_id"]))
    assert set(enrollments["course_id"]).issubset(set(courses["course_id"]))

    assert not enrollments.duplicated(
        subset=["employee_id", "course_id"]
    ).any()


def test_completion_relationships():
    enrollments = load_csv("enrollments.csv")
    completions = load_csv("completions.csv")

    assert set(completions["enrollment_id"]).issubset(
        set(enrollments["enrollment_id"])
    )

    assert pd.to_datetime(
        completions["completed_at"], errors="coerce"
    ).notna().all()


def test_anomaly_ground_truth():
    scenarios = load_csv("anomaly_scenarios.csv")
    ground_truth = load_csv("ground_truth.csv")

    assert len(scenarios) == 5
    assert len(ground_truth) == 5

    assert scenarios["scenario_id"].is_unique
    assert ground_truth["scenario_id"].is_unique

    assert set(scenarios["scenario_id"]) == set(ground_truth["scenario_id"])