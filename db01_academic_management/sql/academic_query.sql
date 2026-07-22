-- VS Code PostgreSQL 확장(GUI)에서 실행할 때는 SET search_path가 세션에 유지되지 않을 수 있어
-- 모든 테이블명에 app. 스키마를 직접 명시했습니다. (psql 터미널에서 실행할 땐 이 SET 문도 그대로 유효)
SET search_path = app, public;

-- Q1. WHERE + ORDER BY : 컴퓨터공학과(major_id=1) 학생 중 2학년 이상, 학년 내림차순 조회
\echo '--- Q1. WHERE + ORDER BY ---'
SELECT student_no, name, grade, phone
FROM app.students
WHERE major_id = 1 AND grade >= 2
ORDER BY grade DESC, name ASC;

-- Q2. WHERE(BETWEEN) + ORDER BY : 학점(credits) 3학점 강좌만, 강좌코드 순
\echo '--- Q2. WHERE(BETWEEN) + ORDER BY ---'
SELECT code, title, credits
FROM app.courses
WHERE credits BETWEEN 3 AND 4
ORDER BY code;

-- Q3. COALESCE : 전화번호 미등록 학생을 '미등록'으로 표시
\echo '--- Q3. COALESCE ---'
SELECT student_no, name, COALESCE(phone, '미등록') AS phone_display
FROM app.students
ORDER BY student_no;

-- Q4. CASE WHEN : 학년을 신입생/2학년/3학년/졸업반으로 라벨링
\echo '--- Q4. CASE WHEN ---'
SELECT student_no, name,
       CASE grade
           WHEN 1 THEN '신입생'
           WHEN 4 THEN '졸업반'
           ELSE grade || '학년'
       END AS grade_label
FROM app.students
ORDER BY grade;

-- Q5. 날짜 함수 : 학생 등록연도, 등록일로부터 경과일(오늘 기준)
\echo '--- Q5. 날짜 함수 ---'
SELECT student_no, name,
       EXTRACT(YEAR FROM created_at)      AS joined_year,
       TO_CHAR(created_at, 'YYYY-MM-DD')  AS joined_date,
       (CURRENT_DATE - created_at::date)  AS days_since_joined
FROM app.students
ORDER BY created_at;

-- Q6. 5개 테이블 JOIN : 학생-수강신청-강좌-교수-학과, 성적 미입력은 COALESCE로 표시
\echo '--- Q6. 5개 테이블 JOIN ---'
SELECT s.student_no                       AS 학번,
       s.name                             AS 학생,
       COALESCE(m.name, '미배정')         AS 학과,
       c.title                            AS 강좌명,
       p.name                             AS 담당교수,
       COALESCE(e.score::text, '미입력')  AS 성적
FROM app.enrollments e
JOIN app.students s   ON s.id = e.student_id
JOIN app.courses c    ON c.id = e.course_id
JOIN app.professors p ON p.id = c.professor_id
LEFT JOIN app.majors m ON m.id = s.major_id
ORDER BY s.student_no, c.code;

-- Q7. CASE WHEN 심화 : 성적을 A/B/C/D/F 등급으로 변환 (JOIN 결과에 적용)
\echo '--- Q7. 성적 등급 매기기 (CASE WHEN 심화) ---'
SELECT s.student_no                AS 학번,
       s.name                      AS 학생,
       c.title                     AS 강좌명,
       e.score                     AS 점수,
       CASE
           WHEN e.score IS NULL   THEN '미입력'
           WHEN e.score >= 90     THEN 'A'
           WHEN e.score >= 80     THEN 'B'
           WHEN e.score >= 70     THEN 'C'
           WHEN e.score >= 60     THEN 'D'
           ELSE 'F'
       END                         AS 등급
FROM app.enrollments e
JOIN app.students s ON s.id = e.student_id
JOIN app.courses c  ON c.id = e.course_id
ORDER BY s.student_no, c.code;
