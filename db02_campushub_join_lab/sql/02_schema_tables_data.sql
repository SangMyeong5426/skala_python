-- ============================================================
-- 종합실습 2 : STEP B. 스키마(lab) / 테이블 / 인덱스 / 데이터 적재 / 검증
-- ============================================================
-- DBeaver 사용 안내
--  1) 이 파일은 반드시 "skala_db"에 연결된 창에서 실행하세요.
--     (01_role_db_setup.sql은 postgres DB에서, 이 파일은 skala_db에서.
--      DBeaver는 psql의 `\c` 처럼 스크립트 중간에 DB를 바꿀 수 없으므로
--      파일을 분리했습니다.)
--  2) skala_user로 접속하든, 관리자 계정으로 접속하든 상관없습니다.
--  3) 전체 실행(Alt+X / macOS ⌘+⌥+Return) 가능합니다.
-- ============================================================

-- ────────────────────────────────────────────
-- STEP B1: 스키마 생성 및 권한 설정
-- ────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS lab AUTHORIZATION skala_user;

SET search_path TO lab, public;
ALTER DATABASE skala_db SET search_path TO lab, public;
ALTER ROLE     skala_user SET search_path TO lab, public;

GRANT USAGE  ON SCHEMA lab TO skala_user;
GRANT CREATE ON SCHEMA lab TO skala_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA lab
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO skala_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA lab
  GRANT USAGE, SELECT ON SEQUENCES TO skala_user;

-- ────────────────────────────────────────────
-- STEP B2: 테이블 DDL
-- ────────────────────────────────────────────
DROP TABLE IF EXISTS lab.enroll    CASCADE;
DROP TABLE IF EXISTS lab.orders    CASCADE;
DROP TABLE IF EXISTS lab.emp       CASCADE;
DROP TABLE IF EXISTS lab.student   CASCADE;
DROP TABLE IF EXISTS lab.customers CASCADE;

CREATE TABLE lab.student (
  student_id INT PRIMARY KEY,
  name       VARCHAR(50),
  major      VARCHAR(50),
  gpa        NUMERIC(3,2)
);

CREATE TABLE lab.enroll (
  student_id INT,
  course     VARCHAR(50),
  grade      CHAR(1)
);

CREATE TABLE lab.customers (
  customer_id   INT PRIMARY KEY,
  customer_name VARCHAR(50)
);

CREATE TABLE lab.orders (
  order_id    INT PRIMARY KEY,
  customer_id INT REFERENCES lab.customers(customer_id),
  amount      NUMERIC(10,2)
);

CREATE TABLE lab.emp (
  emp_id     INT PRIMARY KEY,
  name       VARCHAR(50),
  manager_id INT NULL REFERENCES lab.emp(emp_id)
);

-- ────────────────────────────────────────────
-- STEP B3: 인덱스
-- ────────────────────────────────────────────
CREATE INDEX ix_enroll_student  ON lab.enroll(student_id);
CREATE INDEX ix_orders_customer ON lab.orders(customer_id);
CREATE INDEX ix_emp_manager     ON lab.emp(manager_id);

-- ────────────────────────────────────────────
-- STEP B4: 데이터 적재
-- ────────────────────────────────────────────

-- 학생 1,000건 (규칙: student_id % 3 = 0 → 수강 0건, =1 → 1건, =2 → 2건 배정될 예정)
INSERT INTO lab.student (student_id, name, major, gpa)
SELECT gs,
       'Student_' || gs,
       CASE gs % 5
         WHEN 0 THEN 'CS'  WHEN 1 THEN 'EE'
         WHEN 2 THEN 'ME'  WHEN 3 THEN 'CE'
         ELSE 'BIO'
       END,
       ROUND(2.0 + (gs % 30) / 10.0, 2)
FROM generate_series(1, 1000) AS gs;

UPDATE lab.student SET major = 'HR'
WHERE student_id BETWEEN 981 AND 1000;

-- 수강 데이터 (student_id 1001, 1010은 enroll에만 있는 고아 데이터로 별도 삽입)
INSERT INTO lab.enroll (student_id, course, grade)
SELECT s.student_id,
       CASE WHEN ((s.student_id + k) % 21) = 0 THEN 'DB'
            ELSE 'Course_' || (((s.student_id + k) % 20) + 1)
       END,
       (ARRAY['A','B','C','D'])[((s.student_id + k) % 4) + 1]
FROM lab.student s
JOIN LATERAL generate_series(
  1,
  CASE WHEN (s.student_id % 10) = 0 THEN 0
       WHEN (s.student_id % 2)  = 0 THEN 2
       ELSE 3 END
) AS g(k) ON TRUE;

INSERT INTO lab.enroll VALUES (1001,'AI','A'), (1010,'ML','B');

-- 고객 500건
INSERT INTO lab.customers (customer_id, customer_name)
SELECT gs, 'Customer_' || gs FROM generate_series(1,500) gs;

-- 주문 3,000건
INSERT INTO lab.orders (order_id, customer_id, amount)
SELECT gs,
       (gs % 500) + 1,
       ROUND(5 + (gs * 13) % 5000 + (gs % 100) / 100.0, 2)
FROM generate_series(1, 3000) gs;

-- 조직도 (CEO 1명 → 매니저 10명 → 직원 300명)
INSERT INTO lab.emp VALUES (1, 'CEO', NULL);
INSERT INTO lab.emp (emp_id, name, manager_id)
  SELECT 1+gs, 'Mgr_'||(1+gs), 1 FROM generate_series(1,10) gs;
INSERT INTO lab.emp (emp_id, name, manager_id)
  SELECT 11+gs, 'Dev_'||(11+gs), 1+((gs-1)%10) FROM generate_series(1,300) gs;

-- ────────────────────────────────────────────
-- STEP B5: 검증 (테이블별 건수)
-- ────────────────────────────────────────────
SELECT tablename AS "테이블",
       (xpath('/row/cnt/text()',
              query_to_xml(
                'SELECT COUNT(*) AS cnt FROM lab.' || tablename,
                false, true, ''))
       )[1]::text::int AS "건수"
FROM pg_tables
WHERE schemaname = 'lab'
ORDER BY tablename;

-- 예상 결과: customers 500 / emp 311 / enroll 약 2,300건 / orders 3,000 / student 1,000

-- ────────────────────────────────────────────
-- 접속 정보 (참고용)
--   Host    : localhost
--   Port    : 5432
--   DB      : skala_db
--   Schema  : lab
--   User    : skala_user
--   Password: 01_role_db_setup.sql STEP A2에서 설정한 값
-- ────────────────────────────────────────────
