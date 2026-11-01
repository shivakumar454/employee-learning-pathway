# Design Decisions

## 1. Relational data model

The system uses a normalized relational model with separate entities for employees, roles, skills, courses, budgets, enrollments, and completions.

Many-to-many relationships are represented using bridge tables:
- `role_skill_targets`: skills required by roles.
- `employee_skills`: employee skill assessments.
- `course_skills`: skills covered by courses.
- `prerequisites`: prerequisite relationships between courses.

Primary keys and foreign keys maintain referential integrity.

## 2. Employee skill proficiency

Skill proficiency is represented on a scale of 1 to 5.

The skill gap is calculated as:

`skill_gap = max(0, target_proficiency - current_proficiency)`

The latest valid assessment is used when calculating an employee's current proficiency.

A missing assessment is classified as `UNKNOWN`, not proficiency zero. Treating missing data as zero would incorrectly assume that the employee has no knowledge of the skill.

## 3. Recommendation eligibility

A course is considered relevant when it covers at least one known skill gap.

Before recommending a course, the engine checks:
- Course status.
- Course availability during the planning period.
- Prerequisite completion.
- Course capacity.
- Department budget availability.

Recommendations are decision records. They do not automatically enroll employees. This keeps the recommendation decision separate from the employee's actual enrollment.

## 4. Budget allocation

The recommendation engine identifies feasible learning options. A separate allocation process selects courses that fit within the remaining department budget.

This separation avoids treating every recommendation as a financial commitment.

The generated budget values are synthetic planning assumptions. They are not approved or actual company budgets.

A 10% reserve is included when reconciling generated budgets against existing commitments.

## 5. Historical records and lifecycle

Enrollment and completion records are kept separately.

Enrollment status changes are represented through enrollment events, preserving the history of the lifecycle rather than relying only on the current status.

A course completion does not automatically increase an employee's skill proficiency. A new assessment is required to record a proficiency change.

## 6. Reproducibility

All generated data uses the fixed random seed `20261022`.

Master data is generated before dependent transaction data so that transaction records can reference valid parent IDs.

The source manifest records file hashes and metadata to support reproducibility and integrity checks.

## 7. Anomaly handling

Five deliberate scenarios are generated and labelled separately from baseline operational data:

1. Recommendation violates a prerequisite.
2. Department budget is exceeded.
3. Completion is counted twice.
4. Skill gap remains after course completion without reassessment.
5. Course is unavailable during the planning period.

The anomaly scenarios and `ground_truth.csv` are reference/evaluation data. They must not be mixed into ordinary analytical input features.

The baseline operational records are not deliberately corrupted to create these scenarios.

## 8. Limitations and assumptions

- Generated employees, skills, courses, costs, and assessments are synthetic.
- The planning horizon is configured in the recommendation engine.
- Budget allocation is based on generated budget and enrollment records.
- A recommendation is not proof that an employee enrolled in or completed a course.
- A completion is not proof of skill improvement without a subsequent assessment.
- The anomaly validation checks scenario construction and expected labels; it does not by itself prove that an independent production detection system can detect every anomaly.    