# Employee Skill Gap and Learning Pathway — Data Dictionary

## 1. Conventions

- Primary keys use immutable string identifiers.
- IDs are zero-padded where specified.
- Foreign keys must reference existing parent records.
- Proficiency uses an integer scale from 1 to 5.
- Monetary values use decimal precision with currency INR.
- Dates use ISO 8601 format.
- All synthetic data uses seed `20261022`.
- Validity periods use inclusive start dates and exclusive end dates.
- Historical records are retained; previous events are not overwritten.

## 2. Entity Definitions

### 2.1 Employee

Purpose: Stores employee master information.

| Field | Type | Required | Validation |
|---|---|---|---|
| employee_id | VARCHAR | Yes | PK; format EMP-000001 |
| employee_name | VARCHAR | Yes | Non-empty |
| email | VARCHAR | Yes | Unique, valid email |
| department | VARCHAR | Yes | Non-empty |
| role_id | VARCHAR | Yes | FK to Role |
| manager_id | VARCHAR | No | FK to Employee |
| hire_date | DATE | Yes | Cannot be in the future |
| employment_status | VARCHAR | Yes | ACTIVE, INACTIVE, ON_LEAVE |

### 2.2 Role

Purpose: Defines job roles and career pathways.

| Field | Type | Required | Validation |
|---|---|---|---|
| role_id | VARCHAR | Yes | PK; unique |
| role_name | VARCHAR | Yes | Non-empty |
| role_level | INTEGER | Yes | 1–10 |
| career_track | VARCHAR | Yes | Non-empty |
| description | VARCHAR | No | Optional |

### 2.3 Skill

Purpose: Master list of technical and professional skills.

| Field | Type | Required | Validation |
|---|---|---|---|
| skill_id | VARCHAR | Yes | PK; format SKL-000001 |
| skill_name | VARCHAR | Yes | Unique, non-empty |
| skill_category | VARCHAR | Yes | Technical, Professional, Domain |
| description | VARCHAR | No | Optional |

### 2.4 RoleSkillTarget

Purpose: Defines the required proficiency of a skill for a particular role.

| Field | Type | Required | Validation |
|---|---|---|---|
| target_id | VARCHAR | Yes | PK |
| role_id | VARCHAR | Yes | FK to Role |
| skill_id | VARCHAR | Yes | FK to Skill |
| target_proficiency | INTEGER | Yes | 1–5 |
| effective_from | DATE | Yes | Required |
| effective_to | DATE | No | Must be after effective_from |

Unique active relationship: role_id + skill_id for overlapping effective periods is not allowed.

### 2.5 EmployeeSkill

Purpose: Stores employee skill assessments as historical records.

| Field | Type | Required | Validation |
|---|---|---|---|
| employee_skill_id | VARCHAR | Yes | PK |
| employee_id | VARCHAR | Yes | FK to Employee |
| skill_id | VARCHAR | Yes | FK to Skill |
| proficiency | INTEGER | Yes | 1–5 |
| assessed_at | TIMESTAMP | Yes | Valid timestamp |
| assessment_source | VARCHAR | Yes | SELF, MANAGER, TEST, COURSE_REASSESSMENT |

Each assessment is retained. Current proficiency is calculated from the latest valid assessment, not by overwriting an earlier record.

### 2.6 Course

Purpose: Stores learning course information.

| Field | Type | Required | Validation |
|---|---|---|---|
| course_id | VARCHAR | Yes | PK; format CRS-000001 |
| course_name | VARCHAR | Yes | Non-empty |
| provider | VARCHAR | Yes | Non-empty |
| duration_hours | DECIMAL | Yes | Greater than zero |
| cost_inr | DECIMAL | Yes | Zero or greater |
| capacity | INTEGER | Yes | Greater than zero |
| available_from | DATE | Yes | Required |
| available_to | DATE | Yes | After available_from |
| course_level | INTEGER | Yes | 1–5 |
| course_status | VARCHAR | Yes | ACTIVE, INACTIVE, CANCELLED |

### 2.7 CourseSkill

Purpose: Many-to-many bridge between courses and skills.

| Field | Type | Required | Validation |
|---|---|---|---|
| course_skill_id | VARCHAR | Yes | PK |
| course_id | VARCHAR | Yes | FK to Course |
| skill_id | VARCHAR | Yes | FK to Skill |
| proficiency_gain | INTEGER | Yes | Greater than zero, at most 4 |

Unique combination: course_id + skill_id.

Proficiency gain is a documented expected planning value, not proof of actual employee improvement.

### 2.8 Prerequisite

Purpose: Defines course dependencies.

| Field | Type | Required | Validation |
|---|---|---|---|
| prerequisite_id | VARCHAR | Yes | PK |
| course_id | VARCHAR | Yes | FK to Course |
| prerequisite_course_id | VARCHAR | Yes | FK to Course |
| minimum_proficiency | INTEGER | No | 1–5 |

A course cannot be its own prerequisite. Cyclic prerequisite chains are invalid.

### 2.9 Enrollment

Purpose: Tracks employee registration and learning status.

| Field | Type | Required | Validation |
|---|---|---|---|
| enrollment_id | VARCHAR | Yes | PK; ENR-{employee_id}-{course_id} |
| employee_id | VARCHAR | Yes | FK to Employee |
| course_id | VARCHAR | Yes | FK to Course |
| enrolled_at | TIMESTAMP | Yes | Required |
| status | VARCHAR | Yes | RECOMMENDED, ENROLLED, IN_PROGRESS, COMPLETED, CANCELLED, REJECTED |

One enrollment per employee-course pair in this initial model. Enrollment status changes are separately recorded in EnrollmentEvent.

### 2.10 Completion

Purpose: Records course completion outcomes.

| Field | Type | Required | Validation |
|---|---|---|---|
| completion_id | VARCHAR | Yes | PK; CMP-2026-000001 |
| enrollment_id | VARCHAR | Yes | FK to Enrollment |
| completed_at | TIMESTAMP | Yes | Cannot precede enrollment |
| completion_score | DECIMAL | No | 0–100 |
| outcome | VARCHAR | Yes | PASSED, FAILED |
| recorded_at | TIMESTAMP | Yes | Required |

Multiple completion records can exist for anomaly detection. Duplicate completion events are flagged and must not be counted as separate successful learning outcomes.

### 2.11 Budget

Purpose: Defines available learning budgets.

| Field | Type | Required | Validation |
|---|---|---|---|
| budget_id | VARCHAR | Yes | PK; BUD-{department}-2026 |
| department | VARCHAR | Yes | Non-empty |
| fiscal_year | INTEGER | Yes | 2026 |
| allocated_amount | DECIMAL | Yes | Zero or greater |
| currency | VARCHAR | Yes | INR |
| effective_from | DATE | Yes | Required |
| effective_to | DATE | Yes | After effective_from |

Budget utilization is derived from valid enrollment and spending records, not randomly assigned.

## 3. Supporting Event Entities

These support the required historical traceability.

### 3.1 EnrollmentEvent

| Field | Type | Required | Validation |
|---|---|---|---|
| event_id | VARCHAR | Yes | PK |
| enrollment_id | VARCHAR | Yes | FK to Enrollment |
| previous_status | VARCHAR | No | Valid enrollment status |
| new_status | VARCHAR | Yes | Valid enrollment status |
| event_timestamp | TIMESTAMP | Yes | Required |
| reason | VARCHAR | No | Optional |

Every enrollment state transition is recorded. Invalid lifecycle transitions are rejected.

### 3.2 RecommendationDecision

| Field | Type | Required | Validation |
|---|---|---|---|
| decision_id | VARCHAR | Yes | PK |
| employee_id | VARCHAR | Yes | FK to Employee |
| course_id | VARCHAR | Yes | FK to Course |
| decision_status | VARCHAR | Yes | RECOMMENDED, BLOCKED, REJECTED |
| decision_reason | VARCHAR | Yes | Non-empty |
| decision_score | DECIMAL | No | 0–100 |
| evaluated_at | TIMESTAMP | Yes | Required |

Every evaluated recommendation is retained, including blocked and rejected decisions.

## 4. Entity Relationships and Cardinality

| Relationship | Cardinality |
|---|---|
| Role → Employee | 1:N |
| Employee → EmployeeSkill | 1:N |
| Skill → EmployeeSkill | 1:N |
| Role → RoleSkillTarget | 1:N |
| Skill → RoleSkillTarget | 1:N |
| Course → CourseSkill | 1:N |
| Skill → CourseSkill | 1:N |
| Course → Prerequisite | 1:N |
| Employee → Enrollment | 1:N |
| Course → Enrollment | 1:N |
| Enrollment → Completion | 1:N |
| Department → Budget | 1:N over fiscal years |
| Enrollment → EnrollmentEvent | 1:N |
| Employee → RecommendationDecision | 1:N |
| Course → RecommendationDecision | 1:N |

Role-to-Skill and Course-to-Skill are many-to-many relationships implemented through bridge tables.

## 5. Business Rules

1. Skill gaps are calculated as:

   `gap = max(0, target_proficiency - current_proficiency)`

2. An employee with no assessment for a target skill has unknown proficiency. The system must not silently assume proficiency zero.

3. A course is relevant when it covers at least one skill with a positive gap.

4. A course is feasible only when:
   - The course is active.
   - The course is available during the planning period.
   - Capacity is available.
   - All prerequisites have been satisfied.
   - The applicable department budget is sufficient.

5. Course completion and skill improvement are different events.

6. Actual proficiency improvement requires a new EmployeeSkill assessment with source COURSE_REASSESSMENT.

7. Recommendations are decision records. They do not automatically create enrollments.

8. A duplicate completion event must be flagged and excluded from valid completion counts.

9. Budget utilization must be reconciled with eligible spending records.

10. Every recommendation decision must include a reason.

## 6. Edge Cases and Ground Truth

The separate ground_truth dataset will label these five scenarios:

| Case | Expected decision |
|---|---|
| Recommendation violates prerequisite | BLOCK |
| Budget exceeded | BLOCK |
| Duplicate completion | FLAG_DUPLICATE |
| Course completed without reassessment | FLAG_REASSESSMENT_REQUIRED |
| Course unavailable during planning period | BLOCK |

Ground-truth labels must be generated from documented scenario rules. They must never be used as recommendation-engine input features.

## 7. Data Generation

- Baseline employees: 5,000
- Skills: 500
- Courses: 1,000
- Enrollments: 10,000
- Random seed: 20261022

Master records are generated before dependent records. Every foreign key must reference a valid parent.

Generate valid baseline records first, then inject labelled anomalies separately.

The generator must produce reproducible outputs with identical seeds and parameters.
