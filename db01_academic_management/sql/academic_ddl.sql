-- 종합실습 1 : 학사관리시스템 DDL
-- 실행 전: CREATE DATABASE academic_administration_db; \c academic_administration_db; CREATE SCHEMA app; SET search_path = app, public;

-- 1. majors (학과) - 강한 엔티티
CREATE TABLE majors (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code       VARCHAR(20)  NOT NULL UNIQUE,
    name       VARCHAR(100) NOT NULL
);

-- 2. professors (교수) - 강한 엔티티, majors 참조
CREATE TABLE professors (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    professor_no  VARCHAR(20)  NOT NULL UNIQUE,
    name          VARCHAR(100) NOT NULL,
    major_id      BIGINT REFERENCES majors(id),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3. students (학생) - 강한 엔티티, majors 참조
CREATE TABLE students (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_no  VARCHAR(20)  NOT NULL UNIQUE,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(200) NOT NULL UNIQUE,
    major_id    BIGINT REFERENCES majors(id),
    grade       SMALLINT NOT NULL CHECK (grade BETWEEN 1 AND 4),
    phone       VARCHAR(20),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. courses (강좌) - 강한 엔티티, professors 참조
CREATE TABLE courses (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          VARCHAR(20)  NOT NULL UNIQUE,
    title         VARCHAR(200) NOT NULL,
    credits       SMALLINT NOT NULL CHECK (credits > 0),
    professor_id  BIGINT REFERENCES professors(id)
);

-- 5. enrollments (수강신청) - 약한 엔티티, students/courses N:M 교차 테이블
CREATE TABLE enrollments (
    student_id   BIGINT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id    BIGINT NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
    enrolled_at  DATE NOT NULL DEFAULT CURRENT_DATE,
    score        NUMERIC(5,2),
    PRIMARY KEY (student_id, course_id)
);

-- 역방향 조회 최적화 (course_id 기준 검색)
CREATE INDEX idx_enrollments_course_student ON enrollments (course_id, student_id);
