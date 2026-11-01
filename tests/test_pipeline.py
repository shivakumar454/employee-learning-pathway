from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"
REPORTS = ROOT / "reports"


def test_required_project_files_exist():
    required_files = [
        ROOT / "README.md",
        ROOT / "requirements.txt",
        ROOT / "sql" / "schema.sql",
        ROOT / "docs" / "data_dictionary.md",
        ROOT / "docs" / "design_decisions.md",
    ]

    for file_path in required_files:
        assert file_path.exists(), f"Missing file: {file_path}"


def test_generated_datasets_exist():
    required_files = [
        "roles.csv",
        "skills.csv",
        "employees.csv",
        "role_skill_targets.csv",
        "employee_skills.csv",
        "courses.csv",
        "course_skills.csv",
        "prerequisites.csv",
        "budgets.csv",
        "enrollments.csv",
        "completions.csv",
        "enrollment_events.csv",
        "anomaly_scenarios.csv",
        "ground_truth.csv",
    ]

    for filename in required_files:
        assert (GENERATED / filename).exists(), f"Missing dataset: {filename}"


def test_expected_dataset_sizes():
    expected_counts = {
        "roles.csv": 25,
        "skills.csv": 500,
        "employees.csv": 5000,
        "role_skill_targets.csv": 750,
        "courses.csv": 1000,
        "enrollments.csv": 10000,
        "completions.csv": 5024,
        "enrollment_events.csv": 18499,
        "anomaly_scenarios.csv": 5,
        "ground_truth.csv": 5,
    }

    for filename, expected_count in expected_counts.items():
        dataframe = pd.read_csv(GENERATED / filename)
        assert len(dataframe) == expected_count, (
            f"{filename}: expected {expected_count} rows, got {len(dataframe)}"
        )


def test_analysis_reports_exist():
    required_reports = [
        "employee_skill_gaps.csv",
        "recommendations.csv",
        "budget_allocation.csv",
        "department_budget_summary.csv",
    ]

    for filename in required_reports:
        assert (REPORTS / filename).exists(), f"Missing report: {filename}"