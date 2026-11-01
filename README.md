# Employee Learning Pathway

A data-driven employee learning recommendation system that identifies skill gaps, evaluates course eligibility, recommends learning paths, and allocates department learning budgets.

## 1. Business Problem

Organizations need to identify employee skill gaps and recommend suitable learning opportunities while considering role requirements, course prerequisites, availability, capacity, and department budgets.

This project builds a reproducible data pipeline to support that process using synthetic employee, skill, course, enrollment, and completion data.

## 2. Key Features

- Generate employee, role, skill, and course master data.
- Generate enrollment, completion, and lifecycle event records.
- Calculate employee skill gaps using role-specific proficiency targets.
- Recommend courses that address known skill gaps.
- Evaluate prerequisites, availability, capacity, and budget feasibility.
- Allocate learning opportunities within department budgets.
- Generate five labelled anomaly scenarios with separate ground-truth records.
- Validate relationships, transaction integrity, recommendation feasibility, and anomaly construction.
- Export a reproducible SQL database seed.

## 3. Technology Stack

- Python 3.11
- DuckDB
- Pandas
- SQL
- Pytest

## 4. Dataset Overview

| Dataset | Records |
|---|---:|
| Roles | 25 |
| Skills | 500 |
| Employees | 5,000 |
| Role skill targets | 750 |
| Employee skill assessments | 111,913 |
| Courses | 1,000 |
| Course-skill mappings | 5,948 |
| Prerequisites | 296 |
| Budgets | 10 |
| Enrollments | 10,000 |
| Completions | 5,024 |
| Enrollment events | 18,499 |
| Recommendation decisions | 9,770 |
| Ground-truth scenarios | 5 |

The complete database contains **168,740 records across 16 tables**.

All generated records are synthetic.

## 5. Project Structure

```text
Employee_Learning_Pathway/
│
├── data/
│   └── generated/
│       ├── roles.csv
│       ├── skills.csv
│       ├── employees.csv
│       ├── role_skill_targets.csv
│       ├── employee_skills.csv
│       ├── courses.csv
│       ├── course_skills.csv
│       ├── prerequisites.csv
│       ├── budgets.csv
│       ├── enrollments.csv
│       ├── completions.csv
│       ├── enrollment_events.csv
│       ├── anomaly_scenarios.csv
│       └── ground_truth.csv
│
├── docs/
│   ├── data_dictionary.md
│   ├── design_decisions.md
│   └── source_manifest.json
│
├── reports/
│   ├── employee_skill_gaps.csv
│   ├── recommendations.csv
│   ├── budget_allocation.csv
│   ├── department_budget_summary.csv
│   └── validation_summary.json
│
├── sql/
│   ├── schema.sql
│   └── seed.sql
│
├── src/
│   ├── generator.py
│   ├── transaction_generator.py
│   ├── initialize_db.py
│   ├── load_data.py
│   ├── skill_gap_analysis.py
│   ├── recommendation_engine.py
│   ├── allocate_learning_budget.py
│   ├── reconcile_budgets.py
│   ├── inject_anomalies.py
│   ├── validate_transactions.py
│   ├── validate_recommendations.py
│   ├── validate_anomalies.py
│   ├── verify_database.py
│   ├── export_sql_seed.py
│   ├── verify_sql_seed.py
│   ├── build_validation_summary.py
│   └── build_manifest.py
│
├── tests/
│   ├── test_pipeline.py
│   └── test_validation.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

## 6. Setup

Python 3.11 is recommended.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Dependencies:

- duckdb
- pandas
- pytest

## 7. Generate the Dataset

Run scripts from the project root directory.

```bash
python src/generator.py
python src/transaction_generator.py
```

The generator uses the fixed random seed `20261022` to support reproducibility.

## 8. Database Initialization and Loading

For a fresh database, run:

```bash
python src/initialize_db.py
python src/load_data.py
```

The loader expects an empty database and prevents accidental loading into populated tables.

## 9. Analytical Pipeline

Run skill-gap analysis:

```bash
python src/skill_gap_analysis.py
```

Generate course recommendations:

```bash
python src/recommendation_engine.py
```

Reconcile synthetic department budgets:

```bash
python src/reconcile_budgets.py
```

Allocate learning budgets:

```bash
python src/allocate_learning_budget.py
```

Generate labelled anomaly scenarios:

```bash
python src/inject_anomalies.py
```

## 10. SQL Database Restoration

The project includes:

- `sql/schema.sql` — database table definitions, keys, constraints, and indexes.
- `sql/seed.sql` — exported SQL insert statements for all 168,740 records.

To restore the database:

1. Create a fresh DuckDB database.
2. Execute `sql/schema.sql`.
3. Execute `sql/seed.sql`.

The seed file includes all 16 tables, including recommendation decisions and ground-truth records. Employee manager relationships are restored after employee records are inserted.

To verify the SQL restoration process:

```bash
python src/verify_sql_seed.py
```

This script creates a separate temporary database, applies the schema and seed, and compares row counts across all 16 tables against the original database. It does not modify the original database.

## 11. Validation

Run transaction validation:

```bash
python src/validate_transactions.py
```

Run recommendation validation:

```bash
python src/validate_recommendations.py
```

Run anomaly validation:

```bash
python src/validate_anomalies.py
```

Verify database record counts:

```bash
python src/verify_database.py
```

Run automated tests:

```bash
python -m pytest -v
```

Generate the validation summary:

```bash
python src/build_validation_summary.py
```

The summary is written to `reports/validation_summary.json`.

## 12. Anomaly Scenarios

Five labelled scenarios are generated separately from the baseline operational data:

1. Recommendation violates a course prerequisite.
2. Department budget is exceeded.
3. Completion is counted twice.
4. Skill gap remains after course completion without reassessment.
5. Course is unavailable during the planning period.

The `ground_truth.csv` file contains expected labels and reasons. It is reference/evaluation data and must not be used as ordinary analytical input features.

The anomaly validation checks scenario construction and labels; it does not demonstrate an independent production anomaly-detection engine.

## 13. Business Rules and Assumptions

- Skill proficiency is represented on a scale of 1 to 5.
- Skill gap = max(0, target proficiency - current proficiency).
- Missing skill assessments are treated as `UNKNOWN`, not zero.
- The latest valid assessment is used for current proficiency.
- Course completion does not automatically increase employee proficiency.
- A new skill assessment is required to record a proficiency change.
- Recommendations do not automatically create enrollments.
- Budget allocation is handled separately from recommendation generation.
- Generated department budgets and the 10% reserve are synthetic planning assumptions, not approved company budgets.

Additional design decisions are documented in `docs/design_decisions.md`.

## 14. Reproducibility and Integrity

- Fixed generation seed: `20261022`.
- Generated datasets are stored in `data/generated/`.
- SQL schema and seed are stored in `sql/`.
- File hashes and metadata are recorded in `docs/source_manifest.json`.
- Validation results are recorded in `reports/validation_summary.json`.

Regenerate the source manifest after changing project files:

```bash
python src/build_manifest.py
```

## 15. Limitations

- All employees, roles, skills, courses, costs, and assessments are synthetic.
- Budget amounts are generated planning assumptions.
- Recommendation decisions represent system evaluations, not confirmed employee enrollments.
- Course completion does not establish skill improvement without reassessment.
- The anomaly scenarios validate labelled edge-case construction, not a deployed anomaly detection model.

## 16. Project Outcome

The project delivers a reproducible employee learning pathway data pipeline with relational data modelling, synthetic data generation, skill-gap analysis, course recommendation, budget allocation, labelled anomaly scenarios, SQL restoration, and automated validation.


## AI Usage and Transparency

This project was developed with assistance from ChatGPT (OpenAI).

The `ai_usage/` directory contains:

- `prompt_history.md` — AI prompts used during development.
- `ai_usage_disclosure.md` — Explanation of AI assistance.
- `human_validation.md` — Personal review and validation activities.

AI-generated code and suggestions were reviewed and tested as part of the development process.