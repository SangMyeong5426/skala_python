  # 종합실습 2 — CampusHub 복합 쿼리 실습 (JOIN + 서브쿼리 + 윈도우함수)

  DB: `skala_db` / Schema: `lab` / 테이블: `student`, `enroll`, `customers`, `orders`, `emp`

  ---

  ### 문항 1 — INNER JOIN: 수강 존재 학생의 과목/성적
  수강 기록이 있는 학생만 학생-과목-성적을 이어붙여 조회했습니다.
  ```sql
  SELECT s.student_id, s.name, e.course, e.grade
  FROM lab.student s
  JOIN lab.enroll e ON e.student_id = s.student_id
  ORDER BY s.student_id;
  ```

  ### 문항 2 — LEFT JOIN: 모든 학생 기준, 과목 없으면 NULL
  전체 학생을 기준으로 두고, 수강 기록이 없는 학생은 과목/성적이 NULL로 나오게 했습니다.
  ```sql
  SELECT s.student_id, s.name, e.course, e.grade
  FROM lab.student s
  LEFT JOIN lab.enroll e ON e.student_id = s.student_id
  ORDER BY s.student_id;
  ```

  ### 문항 3 — RIGHT JOIN: 수강 기준, 학생 없으면 학생정보 NULL
  수강 기록을 기준으로 두고, 학생 테이블에 없는 고아 데이터(1001, 1010)는 학생정보가 NULL로 나오게 했습니다.
  ```sql
  SELECT s.student_id, s.name, e.student_id AS enroll_student_id, e.course, e.grade
  FROM lab.student s
  RIGHT JOIN lab.enroll e ON e.student_id = s.student_id
  ORDER BY e.student_id;
  ```

  ### 문항 4 — FULL JOIN: 학생/수강 모두 포함
  학생과 수강 양쪽 모두 빠짐없이 포함해서 조회했습니다.
  ```sql
  SELECT s.student_id, s.name, e.student_id AS enroll_student_id, e.course, e.grade
  FROM lab.student s
  FULL JOIN lab.enroll e ON e.student_id = s.student_id
  ORDER BY COALESCE(s.student_id, e.student_id);
  ```

  ### 문항 5 — 한 번도 수강하지 않은 학생 목록
  `NOT IN` 대신 `NOT EXISTS`를 사용해 NULL 함정을 피했습니다.
  ```sql
  SELECT s.student_id, s.name
  FROM lab.student s
  WHERE NOT EXISTS (
    SELECT 1 FROM lab.enroll e WHERE e.student_id = s.student_id
  )
  ORDER BY s.student_id;
  ```

  ### 문항 6 — 한 과목 이상 수강한 학생 목록(중복 제거)
  JOIN 후 `DISTINCT`로 중복을 지우는 대신, `EXISTS`로 애초에 중복이 생기지 않게 짰습니다.
  ```sql
  SELECT s.student_id, s.name
  FROM lab.student s
  WHERE EXISTS (
    SELECT 1 FROM lab.enroll e WHERE e.student_id = s.student_id
  )
  ORDER BY s.student_id;
  ```

  ### 문항 7 — 고객별 주문건수/총액
  ```sql
  SELECT c.customer_id, c.customer_name,
        COUNT(o.order_id) AS order_count,
        SUM(o.amount)     AS total_amount
  FROM lab.customers c
  JOIN lab.orders o ON o.customer_id = c.customer_id
  GROUP BY c.customer_id, c.customer_name
  ORDER BY c.customer_id;
  ```

  ### 문항 8 — 총액 상위 10명과 금액
  ```sql
  SELECT c.customer_id, c.customer_name, SUM(o.amount) AS total_amount
  FROM lab.customers c
  JOIN lab.orders o ON o.customer_id = c.customer_id
  GROUP BY c.customer_id, c.customer_name
  ORDER BY total_amount DESC
  LIMIT 10;
  ```

  ### 문항 9 — 모든 직원과 그 매니저 이름 (Self join)
  CEO는 매니저가 없으므로 LEFT JOIN으로 처리했습니다.
  ```sql
  SELECT e.emp_id, e.name AS employee_name, m.name AS manager_name
  FROM lab.emp e
  LEFT JOIN lab.emp m ON m.emp_id = e.manager_id
  ORDER BY e.emp_id;
  ```

  ### 문항 10 — 모든 학생 기준 과목 분포 (LEFT JOIN + 집계)
  ```sql
  SELECT COALESCE(e.course, '미수강') AS course, COUNT(DISTINCT s.student_id) AS student_count
  FROM lab.student s
  LEFT JOIN lab.enroll e ON e.student_id = s.student_id
  GROUP BY e.course
  ORDER BY student_count DESC;
  ```

  ### 문항 11 — DB 과목을 듣지 않은 모든 학생 (Anti join)
  ```sql
  SELECT s.student_id, s.name
  FROM lab.student s
  WHERE NOT EXISTS (
    SELECT 1 FROM lab.enroll e WHERE e.student_id = s.student_id AND e.course = 'DB'
  )
  ORDER BY s.student_id;
  ```

  ### 문항 12 — course_owner 매핑 테이블 생성 + 과목별 수강인원/책임매니저 리포트
  과목별로 매니저가 운영 책임을 갖는다고 가정하고, 매핑 테이블을 만든 뒤 리포트를 작성했습니다.
  ```sql
  DROP TABLE IF EXISTS lab.course_owner;

  CREATE TABLE lab.course_owner (
    course     VARCHAR(50) PRIMARY KEY,
    manager_id INT REFERENCES lab.emp(emp_id)
  );

  INSERT INTO lab.course_owner (course, manager_id)
  SELECT course, 2 + ((ROW_NUMBER() OVER (ORDER BY course) - 1) % 10)  -- 매니저 emp_id 2~11
  FROM (SELECT DISTINCT course FROM lab.enroll) c;

  SELECT co.course,
        COUNT(e.student_id) AS enroll_count,
        m.name               AS manager_name
  FROM lab.course_owner co
  LEFT JOIN lab.enroll e ON e.course = co.course
  JOIN lab.emp m ON m.emp_id = co.manager_id
  GROUP BY co.course, m.name
  ORDER BY co.course;
  ```

  ### 문항 13 — 학생×과목 전체조합(Cross join) 샘플 100건
  학생별 과목 추천 후보를 만들되, 샘플 100건만 확인했습니다.
  ```sql
  SELECT s.student_id, s.name, c.course AS candidate_course
  FROM lab.student s
  CROSS JOIN (SELECT DISTINCT course FROM lab.enroll) c
  ORDER BY s.student_id, c.course
  LIMIT 100;
  ```

  ### 문항 14 — 스칼라 서브쿼리로 학생 + 학과명 붙이기
  이 스키마는 `major`가 `student` 테이블에 이미 내장돼 있어, 별도 학과 테이블 대신 스칼라 서브쿼리 문법을 연습하는 형태로 작성했습니다.
  ```sql
  SELECT s.student_id, s.name,
        (SELECT s2.major FROM lab.student s2 WHERE s2.student_id = s.student_id) AS major
  FROM lab.student s
  ORDER BY s.student_id;
  ```

  ### 문항 15 — 평균 GPA보다 높은 학생 (WHERE 서브쿼리)
  ```sql
  SELECT student_id, name, major, gpa
  FROM lab.student
  WHERE gpa > (SELECT AVG(gpa) FROM lab.student)
  ORDER BY gpa DESC;
  ```

  ### 문항 16 — 자신의 학과 평균 GPA보다 높은 학생 (Correlated subquery)
  ```sql
  SELECT s.student_id, s.name, s.major, s.gpa
  FROM lab.student s
  WHERE s.gpa > (
    SELECT AVG(s2.gpa) FROM lab.student s2 WHERE s2.major = s.major
  )
  ORDER BY s.major, s.gpa DESC;
  ```

  ### 문항 17 — 수강(enroll) 기록이 있는 학생만 (Semi join)
  `IN` 서브쿼리 대신 `EXISTS`로 작성했습니다.
  ```sql
  SELECT s.student_id, s.name
  FROM lab.student s
  WHERE EXISTS (SELECT 1 FROM lab.enroll e WHERE e.student_id = s.student_id)
  ORDER BY s.student_id;
  ```

  ### 문항 18 — 한 번도 수강하지 않은 학생 (서브쿼리 버전)
  ```sql
  SELECT s.student_id, s.name
  FROM lab.student s
  WHERE NOT EXISTS (SELECT 1 FROM lab.enroll e WHERE e.student_id = s.student_id)
  ORDER BY s.student_id;
  ```

  ### 문항 19 — HR 학과 학생 일부와의 비교 데모
  HR 학과 학생들의 GPA를 전체 평균과 비교했습니다.
  ```sql
  SELECT s.student_id, s.name, s.gpa,
        ROUND((SELECT AVG(gpa) FROM lab.student), 2) AS overall_avg_gpa,
        ROUND(s.gpa - (SELECT AVG(gpa) FROM lab.student), 2) AS diff_from_avg
  FROM lab.student s
  WHERE s.major = 'HR'
  ORDER BY s.gpa DESC
  LIMIT 10;
  ```

  ### 문항 20 — CS 학과 학생 또는 DB 과목을 수강한 학생 목록 (UNION)
  ```sql
  SELECT student_id, name, major FROM lab.student WHERE major = 'CS'
  UNION
  SELECT s.student_id, s.name, s.major
  FROM lab.student s
  JOIN lab.enroll e ON e.student_id = s.student_id
  WHERE e.course = 'DB'
  ORDER BY student_id;
  ```

  ### 문항 21 — 학과별·GPA구간별 집계 (ROLLUP + GROUPING, 소계/총계)
  GPA를 3구간(3.0 미만/3.0~3.5/3.5 초과)으로 나누고, `ROLLUP`으로 학과별 소계와 전체 총계를 한 쿼리로 뽑았습니다. `GROUPING()`으로 소계 행에 '전체' 라벨을 붙였습니다.
  ```sql
  SELECT
    CASE WHEN GROUPING(major) = 1 THEN '전체' ELSE major END AS major,
    CASE WHEN GROUPING(gpa_tier) = 1 THEN NULL ELSE gpa_tier END AS gpa_tier,
    COUNT(*) AS cnt
  FROM (
    SELECT major,
      CASE WHEN gpa < 3.0 THEN '3.0 미만'
          WHEN gpa <= 3.5 THEN '3.0~3.5'
          ELSE '3.5 초과' END AS gpa_tier
    FROM lab.student
  ) t
  GROUP BY ROLLUP(major, gpa_tier)
  ORDER BY major NULLS LAST, gpa_tier NULLS LAST;
  ```

  ### 문항 22 — WITH RECURSIVE: 조직 계층 경로/깊이 + 매니저별 직속부하 수
  CEO(depth=0)에서 시작해 전 직원의 계층 경로를 재귀적으로 탐색하고, 매니저별 직속 부하 직원 수를 별도로 집계했습니다.
  ```sql
  WITH RECURSIVE org AS (
    SELECT emp_id, name, manager_id, 0 AS depth, name::text AS path
    FROM lab.emp WHERE manager_id IS NULL
    UNION ALL
    SELECT e.emp_id, e.name, e.manager_id, o.depth + 1, o.path || ' > ' || e.name
    FROM lab.emp e
    JOIN org o ON e.manager_id = o.emp_id
  )
  SELECT emp_id, name, depth, path
  FROM org
  ORDER BY path;

  SELECT manager_id, COUNT(*) AS direct_reports
  FROM lab.emp
  WHERE manager_id IS NOT NULL
  GROUP BY manager_id
  ORDER BY manager_id;
  ```

  ### 문항 23 — 학과별 GPA Top3 (서브쿼리 방식 + CTE 방식)
  `ROW_NUMBER()`로 학과 내 순위를 매기고, GPA 동점 시 `student_id` 오름차순을 2차 기준으로 사용했습니다. `RANK()`/`DENSE_RANK()`로 동점 처리 방식 차이를 비교하고, `COUNT() OVER(PARTITION BY major)`로 학과별 전체 학생 수(`total_in_major`)도 추가했습니다.
  ```sql
  -- (a) 서브쿼리 방식
  SELECT * FROM (
    SELECT student_id, name, major, gpa,
          ROW_NUMBER() OVER (PARTITION BY major ORDER BY gpa DESC, student_id ASC) AS rn,
          RANK()       OVER (PARTITION BY major ORDER BY gpa DESC) AS rnk,
          DENSE_RANK() OVER (PARTITION BY major ORDER BY gpa DESC) AS drnk,
          COUNT(*)     OVER (PARTITION BY major) AS total_in_major
    FROM lab.student
  ) ranked
  WHERE rn <= 3
  ORDER BY major, rn;

  -- (b) CTE 방식
  WITH ranked AS (
    SELECT student_id, name, major, gpa,
          ROW_NUMBER() OVER (PARTITION BY major ORDER BY gpa DESC, student_id ASC) AS rn,
          RANK()       OVER (PARTITION BY major ORDER BY gpa DESC) AS rnk,
          DENSE_RANK() OVER (PARTITION BY major ORDER BY gpa DESC) AS drnk,
          COUNT(*)     OVER (PARTITION BY major) AS total_in_major
    FROM lab.student
  )
  SELECT * FROM ranked WHERE rn <= 3 ORDER BY major, rn;
  ```

  ### 문항 24 — LAG()로 이전 수강 대비 성적 변화 + 최고/최저 점수차
  성적(A~D)을 4~1점으로 변환한 뒤, `LAG()`로 직전 과목 대비 점수 변화(`diff`)와 상승/유지/하락 여부를 계산했습니다. 학생별 최고점-최저점 차이(`score_range`)도 함께 구했습니다.
  ```sql
  WITH scored AS (
    SELECT student_id, course, grade,
          CASE grade WHEN 'A' THEN 4 WHEN 'B' THEN 3 WHEN 'C' THEN 2 WHEN 'D' THEN 1 END AS score
    FROM lab.enroll
  )
  SELECT
    student_id, course, grade, score,
    LAG(score) OVER (PARTITION BY student_id ORDER BY course) AS prev_score,
    score - LAG(score) OVER (PARTITION BY student_id ORDER BY course) AS diff,
    CASE
      WHEN LAG(score) OVER (PARTITION BY student_id ORDER BY course) IS NULL THEN '첫 과목'
      WHEN score - LAG(score) OVER (PARTITION BY student_id ORDER BY course) > 0 THEN '상승'
      WHEN score - LAG(score) OVER (PARTITION BY student_id ORDER BY course) = 0 THEN '유지'
      ELSE '하락'
    END AS trend,
    MAX(score) OVER (PARTITION BY student_id) - MIN(score) OVER (PARTITION BY student_id) AS score_range
  FROM scored
  ORDER BY student_id, course;
  ```

  ### 문항 25 — 누적 주문금액 + 3개 주문 이동평균 (ROWS BETWEEN)
  주문을 `order_id` 순으로 정렬해서 누적 주문금액과 3개 주문 이동평균을 계산하고, `customer_id`별 누적 구매금액, 그리고 누적합이 전체 합의 50%를 넘는 첫 시점도 함께 확인했습니다.
  ```sql
  -- (a) order_id 순 누적합 + 3개 이동평균
  SELECT order_id, customer_id, amount,
        SUM(amount) OVER (ORDER BY order_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
        ROUND(AVG(amount) OVER (ORDER BY order_id ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3
  FROM lab.orders
  ORDER BY order_id;

  -- (b) 고객별 누적 구매금액 (PARTITION BY customer_id)
  SELECT order_id, customer_id, amount,
        SUM(amount) OVER (
          PARTITION BY customer_id ORDER BY order_id
          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS customer_running_total
  FROM lab.orders
  ORDER BY customer_id, order_id;

  -- (c) 누적합이 전체 합의 50%를 초과하는 첫 번째 order_id
  WITH running AS (
    SELECT order_id, amount,
          SUM(amount) OVER (ORDER BY order_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
          SUM(amount) OVER () AS grand_total
    FROM lab.orders
  )
  SELECT order_id, running_total, grand_total
  FROM running
  WHERE running_total > grand_total * 0.5
  ORDER BY order_id
  LIMIT 1;
  ```
