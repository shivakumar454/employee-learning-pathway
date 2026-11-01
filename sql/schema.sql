
-- ============================================================
-- EMPLOYEE SKILL GAP & LEARNING PATHWAY SYSTEM
-- Database: DuckDB
-- ============================================================

-- 1. ROLE
CREATE TABLE IF NOT EXISTS roles (
    role_id VARCHAR PRIMARY KEY,
    role_name VARCHAR NOT NULL UNIQUE,
    role_level INTEGER NOT NULL CHECK (role_level BETWEEN 1 AND 10),
    career_track VARCHAR NOT NULL,
    description VARCHAR
);

-- 2. SKILL
CREATE TABLE IF NOT EXISTS skills (
    skill_id VARCHAR PRIMARY KEY,
    skill_name VARCHAR NOT NULL UNIQUE,
    skill_category VARCHAR NOT NULL
        CHECK (skill_category IN ('TECHNICAL', 'PROFESSIONAL', 'DOMAIN')),
    description VARCHAR
);

-- 3. EMPLOYEE
CREATE TABLE IF NOT EXISTS employees (
    employee_id VARCHAR PRIMARY KEY,
    employee_name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    department VARCHAR NOT NULL,
    role_id VARCHAR NOT NULL REFERENCES roles(role_id),
    manager_id VARCHAR REFERENCES employees(employee_id),
    hire_date DATE NOT NULL,
    employment_status VARCHAR NOT NULL
        CHECK (employment_status IN ('ACTIVE', 'INACTIVE', 'ON_LEAVE'))
);

-- 4. ROLE SKILL TARGET
CREATE TABLE IF NOT EXISTS role_skill_targets (
    target_id VARCHAR PRIMARY KEY,
    role_id VARCHAR NOT NULL REFERENCES roles(role_id),
    skill_id VARCHAR NOT NULL REFERENCES skills(skill_id),
    target_proficiency INTEGER NOT NULL
        CHECK (target_proficiency BETWEEN 1 AND 5),
    effective_from DATE NOT NULL,
    effective_to DATE,
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    UNIQUE (role_id, skill_id, effective_from)
);

-- 5. EMPLOYEE SKILL ASSESSMENT HISTORY
CREATE TABLE IF NOT EXISTS employee_skills (
    employee_skill_id VARCHAR PRIMARY KEY,
    employee_id VARCHAR NOT NULL REFERENCES employees(employee_id),
    skill_id VARCHAR NOT NULL REFERENCES skills(skill_id),
    proficiency INTEGER NOT NULL CHECK (proficiency BETWEEN 1 AND 5),
    assessed_at TIMESTAMP NOT NULL,
    assessment_source VARCHAR NOT NULL
        CHECK (assessment_source IN (
            'SELF', 'MANAGER', 'TEST', 'COURSE_REASSESSMENT'
        ))
);

-- 6. COURSE
CREATE TABLE IF NOT EXISTS courses (
    course_id VARCHAR PRIMARY KEY,
    course_name VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    duration_hours DECIMAL(8,2) NOT NULL CHECK (duration_hours > 0),
    cost_inr DECIMAL(12,2) NOT NULL CHECK (cost_inr >= 0),
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    available_from DATE NOT NULL,
    available_to DATE NOT NULL,
    course_level INTEGER NOT NULL CHECK (course_level BETWEEN 1 AND 5),
    course_status VARCHAR NOT NULL
        CHECK (course_status IN ('ACTIVE', 'INACTIVE', 'CANCELLED')),
    CHECK (available_to > available_from)
);

-- 7. COURSE SKILL BRIDGE
CREATE TABLE IF NOT EXISTS course_skills (
    course_skill_id VARCHAR PRIMARY KEY,
    course_id VARCHAR NOT NULL REFERENCES courses(course_id),
    skill_id VARCHAR NOT NULL REFERENCES skills(skill_id),
    proficiency_gain INTEGER NOT NULL
        CHECK (proficiency_gain BETWEEN 1 AND 4),
    UNIQUE (course_id, skill_id)
);

-- 8. COURSE PREREQUISITES
CREATE TABLE IF NOT EXISTS prerequisites (
    prerequisite_id VARCHAR PRIMARY KEY,
    course_id VARCHAR NOT NULL REFERENCES courses(course_id),
    prerequisite_course_id VARCHAR NOT NULL REFERENCES courses(course_id),
    minimum_proficiency INTEGER
        CHECK (minimum_proficiency BETWEEN 1 AND 5),
    CHECK (course_id <> prerequisite_course_id),
    UNIQUE (course_id, prerequisite_course_id)
);

-- 9. DEPARTMENT BUDGET
CREATE TABLE IF NOT EXISTS budgets (
    budget_id VARCHAR PRIMARY KEY,
    department VARCHAR NOT NULL,
    fiscal_year INTEGER NOT NULL,
    allocated_amount DECIMAL(14,2) NOT NULL
        CHECK (allocated_amount >= 0),
    currency VARCHAR NOT NULL CHECK (currency = 'INR'),
    effective_from DATE NOT NULL,
    effective_to DATE NOT NULL,
    CHECK (effective_to > effective_from),
    UNIQUE (department, fiscal_year)
);

-- 10. ENROLLMENT
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id VARCHAR PRIMARY KEY,
    employee_id VARCHAR NOT NULL REFERENCES employees(employee_id),
    course_id VARCHAR NOT NULL REFERENCES courses(course_id),
    enrolled_at TIMESTAMP NOT NULL,
    status VARCHAR NOT NULL
        CHECK (status IN (
            'RECOMMENDED', 'ENROLLED', 'IN_PROGRESS',
            'COMPLETED', 'CANCELLED', 'REJECTED'
        )),
    UNIQUE (employee_id, course_id)
);

-- 11. COMPLETION EVENTS
-- Multiple events can be retained so duplicate attempts can be detected.
CREATE TABLE IF NOT EXISTS completions (
    completion_id VARCHAR PRIMARY KEY,
    enrollment_id VARCHAR NOT NULL REFERENCES enrollments(enrollment_id),
    completed_at TIMESTAMP NOT NULL,
    completion_score DECIMAL(5,2)
        CHECK (completion_score BETWEEN 0 AND 100),
    outcome VARCHAR NOT NULL CHECK (outcome IN ('PASSED', 'FAILED')),
    recorded_at TIMESTAMP NOT NULL
);

-- 12. ENROLLMENT STATUS HISTORY
CREATE TABLE IF NOT EXISTS enrollment_events (
    event_id VARCHAR PRIMARY KEY,
    enrollment_id VARCHAR NOT NULL REFERENCES enrollments(enrollment_id),
    previous_status VARCHAR,
    new_status VARCHAR NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    reason VARCHAR
);

-- 13. RECOMMENDATION DECISIONS
CREATE TABLE IF NOT EXISTS recommendation_decisions (
    decision_id VARCHAR PRIMARY KEY,
    employee_id VARCHAR NOT NULL REFERENCES employees(employee_id),
    course_id VARCHAR NOT NULL REFERENCES courses(course_id),
    decision_status VARCHAR NOT NULL
        CHECK (decision_status IN ('RECOMMENDED', 'BLOCKED', 'REJECTED')),
    decision_reason VARCHAR NOT NULL,
    decision_score DECIMAL(5,2)
        CHECK (decision_score BETWEEN 0 AND 100),
    evaluated_at TIMESTAMP NOT NULL
);

-- 14. PIPELINE RUN HISTORY
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    status VARCHAR NOT NULL
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    seed INTEGER NOT NULL,
    input_rows BIGINT DEFAULT 0,
    accepted_rows BIGINT DEFAULT 0,
    rejected_rows BIGINT DEFAULT 0,
    error_message VARCHAR
);

-- 15. DATA QUALITY ISSUES / QUARANTINE
CREATE TABLE IF NOT EXISTS data_quality_issues (
    issue_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL REFERENCES pipeline_runs(run_id),
    entity_name VARCHAR NOT NULL,
    record_id VARCHAR,
    issue_type VARCHAR NOT NULL,
    severity VARCHAR NOT NULL
        CHECK (severity IN ('INFO', 'WARNING', 'ERROR')),
    description VARCHAR NOT NULL,
    detected_at TIMESTAMP NOT NULL
);

-- 16. RECOMMENDATION GROUND TRUTH
-- Expected labels are kept separately from recommendation inputs.
CREATE TABLE IF NOT EXISTS ground_truth (
    ground_truth_id VARCHAR PRIMARY KEY,
    scenario_id VARCHAR NOT NULL,
    employee_id VARCHAR REFERENCES employees(employee_id),
    course_id VARCHAR REFERENCES courses(course_id),
    expected_label VARCHAR NOT NULL,
    expected_reason VARCHAR NOT NULL,
    UNIQUE (scenario_id, employee_id, course_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_employee_role
    ON employees(role_id);

CREATE INDEX IF NOT EXISTS idx_employee_skill_lookup
    ON employee_skills(employee_id, skill_id, assessed_at);

CREATE INDEX IF NOT EXISTS idx_role_skill_lookup
    ON role_skill_targets(role_id, skill_id);

CREATE INDEX IF NOT EXISTS idx_course_skill_lookup
    ON course_skills(skill_id, course_id);

CREATE INDEX IF NOT EXISTS idx_enrollment_employee
    ON enrollments(employee_id);

CREATE INDEX IF NOT EXISTS idx_completion_enrollment
    ON completions(enrollment_id);

CREATE INDEX IF NOT EXISTS idx_recommendation_employee
    ON recommendation_decisions(employee_id);
