-- 종합실습 4 : E-Commerce 매출 분석 및 성능 튜닝
-- 스키마: ecom (01_schema.sql + 02_seed.sql 실행 후 사용)
--
-- 문항마다 4블록 구조:
--   1) 튜닝 전 - 결과 확인 (답 캡처용, EXPLAIN 없음)
--   2) 튜닝 전 - 성능 측정 (EXPLAIN ANALYZE, BUFFERS 캡처용)
--   3) 튜닝 후 - 결과 확인 (답이 튜닝 전과 같아야 정상)
--   4) 튜닝 후 - 성능 측정 (플랜/시간 비교용)
SET search_path = ecom, public;

-- ============================================================
-- Q1) 지난 한 달간 실제 팔린 총 금액 (paid+shipped+delivered)
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 최근 1개월간 상태가 paid/shipped/delivered인 주문의 매출(line_total) 합계.
-- 컬럼 선택: 합계 하나만 필요하므로 SUM(oi.line_total) 외 컬럼은 선택하지 않음.
SELECT SUM(oi.line_total) AS total_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND (o.order_ts + INTERVAL '0 seconds') >= now() - INTERVAL '1 month';

-- [2] 튜닝 전 - 성능 측정 (order_ts에 연산이 걸려 인덱스 못 탐)
-- 문제: WHERE 절에서 order_ts 컬럼에 (+ INTERVAL '0 seconds') 연산을 적용해 비교함.
--       인덱스 컬럼에 함수/연산이 걸리면 옵티마이저가 Index Cond로 활용하지 못하고
--       Seq Scan 후 Filter로 걸러내야 해서 전체 테이블을 다 훑게 된다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT SUM(oi.line_total) AS total_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND (o.order_ts + INTERVAL '0 seconds') >= now() - INTERVAL '1 month';

-- 튜닝: 복합 인덱스 추가
-- (order_status, order_ts) 순서로 생성해 등치 조건(status)을 선두 컬럼에 두고
-- 뒤이어 범위 조건(ts)을 결합 -> 등치+범위 인덱스의 일반적인 컬럼 순서 원칙을 따름.
CREATE INDEX IF NOT EXISTS idx_orders_status_ts ON orders (order_status, order_ts);

-- [3] 튜닝 후 - 결과 확인 (위 [1]과 값이 같아야 정상)
-- order_ts에 걸었던 연산을 제거하고 컬럼을 원본 그대로 비교하도록 되돌림.
SELECT SUM(oi.line_total) AS total_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND o.order_ts >= now() - INTERVAL '1 month';

-- [4] 튜닝 후 - 성능 측정 (컬럼 원본 그대로 range 비교 -> Index Cond 사용 가능)
-- 효과: idx_orders_status_ts가 Index Cond로 활용되어 Seq Scan -> Index/Bitmap Scan 전환,
--       스캔 대상 행 수가 크게 감소.
EXPLAIN (ANALYZE, BUFFERS)
SELECT SUM(oi.line_total) AS total_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND o.order_ts >= now() - INTERVAL '1 month';


-- ============================================================
-- Q2) 월별 주문수 / 매출 / 평균주문금액
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 월별 주문 건수(order_cnt), 매출(revenue), 주문당 평균 금액(aov)을 함께 조회.
-- 컬럼 선택: 월(month) 기준 그룹핑 결과와 3개 지표만 선택.
SELECT date_trunc('month', o.order_ts) AS month,
       COUNT(DISTINCT o.order_id) AS order_cnt,
       SUM(oi.line_total) AS revenue,
       SUM(oi.line_total) / COUNT(DISTINCT o.order_id) AS aov
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
GROUP BY 1
ORDER BY 1;

-- [2] 튜닝 전 - 성능 측정 (매번 원본 orders x order_items 전체 조인)
-- 문제: 리포트성 조회인데 조회할 때마다 orders/order_items 전체를 조인·집계하므로
--       테이블이 커질수록 매번 무거운 조인 비용을 반복해서 지불하게 된다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT date_trunc('month', o.order_ts) AS month,
       COUNT(DISTINCT o.order_id) AS order_cnt,
       SUM(oi.line_total) AS revenue,
       SUM(oi.line_total) / COUNT(DISTINCT o.order_id) AS aov
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
GROUP BY 1
ORDER BY 1;

-- 튜닝: mv_daily_gmv를 주문수(order_cnt)까지 포함하도록 재정의
--       (원래 스키마의 mv_daily_gmv는 day/gmv뿐이라 Q2의 3개 지표를 못 채움 -> 확장)
-- 무거운 조인·집계 비용을 refresh 시점에 미리 지불해두고, 조회는 사전집계 결과만 스캔하게 함.
-- 트레이드오프: refresh 전까지는 최신 데이터가 반영되지 않으므로 갱신 주기 설계가 필요.
DROP MATERIALIZED VIEW IF EXISTS mv_daily_gmv;
CREATE MATERIALIZED VIEW mv_daily_gmv as

SELECT date_trunc('day', o.order_ts) AS day,
       COUNT(DISTINCT o.order_id) AS order_cnt,
       SUM(oi.line_total) AS gmv
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
GROUP BY 1;
CREATE INDEX IF NOT EXISTS idx_mv_daily_gmv_day ON mv_daily_gmv (day);

-- [3] 튜닝 후 - 결과 확인 (주문수/매출/AOV 3개 지표 모두 mv_daily_gmv만으로 계산)
-- 원본 orders/order_items 조인 없이, 일별로 이미 집계된 mv_daily_gmv를 월 단위로 재집계.
SELECT date_trunc('month', day) AS month,
       SUM(order_cnt) AS order_cnt,
       SUM(gmv) AS revenue,
       SUM(gmv) / SUM(order_cnt) AS aov
FROM mv_daily_gmv
GROUP BY 1
ORDER BY 1;

-- [4] 튜닝 후 - 성능 측정 (원본 orders/order_items 조인 없이 사전집계된 MV만 스캔)
-- 효과: 훨씬 작은 사전집계 테이블만 스캔하면 되므로 응답 속도가 크게 개선.
EXPLAIN (ANALYZE, BUFFERS)
SELECT date_trunc('month', day) AS month,
       SUM(order_cnt) AS order_cnt,
       SUM(gmv) AS revenue,
       SUM(gmv) / SUM(order_cnt) AS aov
FROM mv_daily_gmv
GROUP BY 1
ORDER BY 1;


-- ============================================================
-- Q3) 최근 90일 카테고리 Top10
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 최근 90일간 카테고리별 매출을 집계해 상위 10개 카테고리를 조회.
-- 컬럼 선택: 카테고리명과 매출 합계만 선택.
SELECT c.category_name,
       SUM(oi.line_total) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN v_category_path c ON c.category_id = p.category_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND (o.order_ts + INTERVAL '0 seconds') >= now() - INTERVAL '90 days'
GROUP BY c.category_name
ORDER BY revenue DESC
LIMIT 10;

-- [2] 튜닝 전 - 성능 측정
-- 문제: Q1과 동일하게 order_ts에 연산(+ INTERVAL '0 seconds')이 걸려 인덱스를 못 탄다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.category_name,
       SUM(oi.line_total) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN v_category_path c ON c.category_id = p.category_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND (o.order_ts + INTERVAL '0 seconds') >= now() - INTERVAL '90 days'
GROUP BY c.category_name
ORDER BY revenue DESC
LIMIT 10;

-- [3] 튜닝 후 - 결과 확인 (Q1의 idx_orders_status_ts 재사용, 별도 인덱스 불필요)
-- 튜닝: order_ts 비교를 연산 없이 원본 컬럼 그대로 되돌림.
--       Q1에서 만든 idx_orders_status_ts가 동일한 필터 패턴(status+ts 범위)을 커버하므로
--       새 인덱스를 만들 필요 없이 재사용 -> 인덱스 설계 시 재사용성 고려 사례.
SELECT c.category_name,
       SUM(oi.line_total) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN v_category_path c ON c.category_id = p.category_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND o.order_ts >= now() - INTERVAL '90 days'
GROUP BY c.category_name
ORDER BY revenue DESC
LIMIT 10;

-- [4] 튜닝 후 - 성능 측정
-- 효과: idx_orders_status_ts를 Index Cond로 활용해 Seq Scan -> Index/Bitmap Scan 전환.
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.category_name,
       SUM(oi.line_total) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p ON p.product_id = oi.product_id
JOIN v_category_path c ON c.category_id = p.category_id
WHERE o.order_status IN ('paid','shipped','delivered')
  AND o.order_ts >= now() - INTERVAL '90 days'
GROUP BY c.category_name
ORDER BY revenue DESC
LIMIT 10;
-- 참고: 현재 카테고리 트리는 리프 10개뿐이라 Top10=전체와 같을 수 있음 (정상)


-- ============================================================
-- Q4) 제품별 누적매출 RANK() Top20
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 제품별 누적 매출로 RANK()를 매겨 상위 20개 제품을 조회.
-- 컬럼 선택: product_id, revenue, 순위(rnk)만 선택.
SELECT t1.product_id,
       t1.revenue,
       (SELECT COUNT(*) + 1
        FROM (SELECT product_id, SUM(line_total) AS revenue
              FROM order_items GROUP BY product_id) t2
        WHERE t2.revenue > t1.revenue) AS rnk
FROM (SELECT product_id, SUM(line_total) AS revenue
      FROM order_items GROUP BY product_id) t1
ORDER BY t1.revenue DESC
LIMIT 20;

-- [2] 튜닝 전 - 성능 측정 (상관 서브쿼리로 순위 흉내 -> 제품 수만큼 반복 스캔, O(n^2))
-- 문제: "나보다 매출 큰 제품 수 + 1"을 구하는 상관 서브쿼리를 제품마다 반복 실행.
--       제품 수가 N개면 매번 전체 제품 집계 결과를 다시 스캔해 사실상 O(N^2)에 가깝다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT t1.product_id,
       t1.revenue,
       (SELECT COUNT(*) + 1
        FROM (SELECT product_id, SUM(line_total) AS revenue
              FROM order_items GROUP BY product_id) t2
        WHERE t2.revenue > t1.revenue) AS rnk
FROM (SELECT product_id, SUM(line_total) AS revenue
      FROM order_items GROUP BY product_id) t1
ORDER BY t1.revenue DESC
LIMIT 20;

-- 튜닝: 커버링 인덱스로 Heap Fetch 제거
-- (product_id) INCLUDE (line_total) 구성으로 product_id별 집계에 필요한 값을
-- 인덱스만으로 해결 -> Index Only Scan 유도.
CREATE INDEX IF NOT EXISTS idx_order_items_product_cover
  ON order_items (product_id) INCLUDE (line_total);

-- [3] 튜닝 후 - 결과 확인 (RANK() 사용, 요구사항 명시대로, Before와 같은 정렬)
-- 상관 서브쿼리 대신 RANK() OVER (ORDER BY SUM(line_total) DESC) 윈도우 함수로 대체.
SELECT product_id, revenue, rnk
FROM (
  SELECT product_id,
         SUM(line_total) AS revenue,
         RANK() OVER (ORDER BY SUM(line_total) DESC) AS rnk
  FROM order_items
  GROUP BY product_id
) ranked
WHERE rnk <= 20
ORDER BY rnk;

-- [4] 튜닝 후 - 성능 측정 (윈도우함수로 한 번의 스캔+정렬)
-- 효과: O(N^2) 상관 서브쿼리 -> 단일 스캔+정렬(O(N log N))로 전환, 커버링 인덱스 덕분에
--       Index Only Scan이 가능해져 힙 접근(Heap Fetch)도 제거됨.
EXPLAIN (ANALYZE, BUFFERS)
SELECT product_id, revenue, rnk
FROM (
  SELECT product_id,
         SUM(line_total) AS revenue,
         RANK() OVER (ORDER BY SUM(line_total) DESC) AS rnk
  FROM order_items
  GROUP BY product_id
) ranked
WHERE rnk <= 20
ORDER BY rnk;


-- ============================================================
-- Q5) RFM (최근성 / 빈도 / 금액)
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 고객별 최근 구매 시점(recency), 구매 빈도(frequency), 총 구매 금액(monetary).
-- 컬럼 선택: customer_id와 RFM 3개 지표만 선택.
SELECT o.customer_id,
       MAX(o.order_ts) AS recency,
       COUNT(DISTINCT o.order_id) AS frequency,
       SUM(oi.line_total) AS monetary
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.customer_id
ORDER BY o.customer_id;

-- [2] 튜닝 전 - 성능 측정 (하나의 큰 JOIN으로 fan-out된 뒤 집계)
-- 문제: order_items가 orders에 대해 1:N이라 조인 결과가 fan-out되고,
--       recency/frequency(주문 단위 지표)까지 부풀려진 행 위에서 계산되어
--       COUNT(DISTINCT o.order_id)로 억지로 중복을 제거해야 한다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.customer_id,
       MAX(o.order_ts) AS recency,
       COUNT(DISTINCT o.order_id) AS frequency,
       SUM(oi.line_total) AS monetary
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.customer_id
ORDER BY o.customer_id;

-- [3] 튜닝 후 - 결과 확인 (최근성/빈도는 orders만으로 먼저 집계, 금액은 별도 집계 후 합침)
-- 튜닝: recency/frequency는 orders 테이블만으로 먼저 집계(rf CTE),
--       monetary는 order_items와 조인해 별도로 집계(monetary CTE) 후 병합
--       -> fan-out된 결과 위에서 집계하지 않아 DISTINCT가 불필요해짐.
WITH rf AS (
  SELECT customer_id,
         MAX(order_ts) AS recency,
         COUNT(*) AS frequency
  FROM orders
  GROUP BY customer_id
),
monetary AS (
  SELECT o.customer_id, SUM(oi.line_total) AS monetary
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY o.customer_id
)
SELECT rf.customer_id, rf.recency, rf.frequency, m.monetary
FROM rf
JOIN monetary m ON m.customer_id = rf.customer_id
ORDER BY rf.customer_id;

-- [4] 튜닝 후 - 성능 측정 (fan-out 없이 선(先)집계)
-- 효과: 중간 결과 행 수 감소, DISTINCT로 중복을 걷어내는 우회가 필요 없어짐.
EXPLAIN (ANALYZE, BUFFERS)
WITH rf AS (
  SELECT customer_id,
         MAX(order_ts) AS recency,
         COUNT(*) AS frequency
  FROM orders
  GROUP BY customer_id
),
monetary AS (
  SELECT o.customer_id, SUM(oi.line_total) AS monetary
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY o.customer_id
)
SELECT rf.customer_id, rf.recency, rf.frequency, m.monetary
FROM rf
JOIN monetary m ON m.customer_id = rf.customer_id
ORDER BY rf.customer_id;


-- ============================================================
-- Q6) 첫 구매 후 30일 내 재구매율
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 고객의 첫 주문 이후 30일 이내에 두 번째 주문이 발생한 비율.
-- 컬럼 선택: 최종 지표(repurchase_rate) 하나만 선택.
SELECT
  COUNT(*) FILTER (
    WHERE second_ts IS NOT NULL AND second_ts <= first_ts + INTERVAL '30 days'
  )::numeric / COUNT(*) AS repurchase_rate
FROM (
  SELECT DISTINCT customer_id, first_ts_sub AS first_ts,
         (SELECT MIN(o2.order_ts) FROM orders o2
          WHERE o2.customer_id = o1.customer_id
            AND o2.order_ts > o1.first_ts_sub) AS second_ts
  FROM (SELECT customer_id, order_ts,
               MIN(order_ts) OVER (PARTITION BY customer_id) AS first_ts_sub
        FROM orders) o1
) t;

-- [2] 튜닝 전 - 성능 측정 (고객마다 상관 서브쿼리로 다음 주문 반복 탐색, N+1 성향)
-- 문제: 고객마다 "첫 주문 이후 최소 주문 시각(다음 주문)"을 구하는 상관 서브쿼리를 반복 실행,
--       고객 수만큼 orders를 반복 스캔하는 N+1 패턴.
EXPLAIN (ANALYZE, BUFFERS)
SELECT
  COUNT(*) FILTER (
    WHERE second_ts IS NOT NULL AND second_ts <= first_ts + INTERVAL '30 days'
  )::numeric / COUNT(*) AS repurchase_rate
FROM (
  SELECT DISTINCT customer_id, first_ts_sub AS first_ts,
         (SELECT MIN(o2.order_ts) FROM orders o2
          WHERE o2.customer_id = o1.customer_id
            AND o2.order_ts > o1.first_ts_sub) AS second_ts
  FROM (SELECT customer_id, order_ts,
               MIN(order_ts) OVER (PARTITION BY customer_id) AS first_ts_sub
        FROM orders) o1
) t;

-- [3] 튜닝 후 - 결과 확인 (LEAD() 윈도우함수로 대체)
-- 튜닝: LEAD(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts)로
--       고객별 다음 주문 시각을 한 번의 스캔으로 계산, ROW_NUMBER()=1(첫 주문)만 남김.
WITH ordered AS (
  SELECT customer_id, order_ts,
         LEAD(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) AS next_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts) AS rn
  FROM orders
)
SELECT
  COUNT(*) FILTER (
    WHERE next_ts IS NOT NULL AND next_ts <= order_ts + INTERVAL '30 days'
  )::numeric / COUNT(*) AS repurchase_rate
FROM ordered
WHERE rn = 1;

-- [4] 튜닝 후 - 성능 측정 (idx_orders_customer_ts로 정렬된 스캔 한 번)
-- 효과: 반복되는 상관 서브쿼리 스캔이 제거되고, (customer_id, order_ts) 인덱스가 있으면
--       정렬된 스캔 한 번으로 처리 가능.
EXPLAIN (ANALYZE, BUFFERS)
WITH ordered AS (
  SELECT customer_id, order_ts,
         LEAD(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) AS next_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts) AS rn
  FROM orders
)
SELECT
  COUNT(*) FILTER (
    WHERE next_ts IS NOT NULL AND next_ts <= order_ts + INTERVAL '30 days'
  )::numeric / COUNT(*) AS repurchase_rate
FROM ordered
WHERE rn = 1;


-- ============================================================
-- Q7) 재고 임계치 미달 상품
-- ============================================================

-- [1] 튜닝 전 - 결과 확인 (After와 같은 컬럼만 명시 + 같은 정렬로 맞춤)
-- 요구사항: 현재 재고(qty_on_hand)가 재주문 임계치(reorder_point)보다 낮은 상품 조회.
-- 컬럼 선택: product_id, qty_on_hand, reorder_point만 선택.
SELECT product_id, qty_on_hand, reorder_point
FROM inventory
WHERE product_id IN (
  SELECT product_id FROM inventory WHERE qty_on_hand < reorder_point
)
ORDER BY product_id;

-- [2] 튜닝 전 - 성능 측정 (불필요한 자기 서브쿼리)
-- 문제: 같은 테이블(inventory)을 자기 자신에 대한 서브쿼리로 감싸 불필요하게 두 번 스캔.
EXPLAIN (ANALYZE, BUFFERS)
SELECT product_id, qty_on_hand, reorder_point
FROM inventory
WHERE product_id IN (
  SELECT product_id FROM inventory WHERE qty_on_hand < reorder_point
)
ORDER BY product_id;

-- [3] 튜닝 후 - 결과 확인 (서브쿼리 제거, Before와 같은 컬럼/정렬)
-- 튜닝: IN 서브쿼리를 제거하고 WHERE 조건을 직접 적용 -> 테이블 스캔 1회로 감소.
SELECT product_id, qty_on_hand, reorder_point
FROM inventory
WHERE qty_on_hand < reorder_point
ORDER BY product_id;

-- [4] 튜닝 후 - 성능 측정
-- 참고: inventory가 600행뿐이라 인덱스를 걸어도 Seq Scan을 유지할 수 있음(정상, 소규모 테이블 특성)
EXPLAIN (ANALYZE, BUFFERS)
SELECT product_id, qty_on_hand, reorder_point
FROM inventory
WHERE qty_on_hand < reorder_point
ORDER BY product_id;


-- ============================================================
-- Q8) 리뷰 4.5 이상 & 50개 이상 효자상품
-- ============================================================

-- [1] 튜닝 전 - 결과 확인 (After와 같은 컬럼 구성 + 같은 정렬로 맞춤)
-- 요구사항: 평균 평점 4.5 이상 & 리뷰 수 50개 이상인 "효자상품" 조회.
-- 컬럼 선택: product_id, avg_rating, review_cnt만 선택.
SELECT p.product_id,
       (SELECT AVG(r.rating) FROM reviews r WHERE r.product_id = p.product_id) AS avg_rating,
       (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.product_id) AS review_cnt
FROM products p
WHERE (SELECT AVG(r.rating) FROM reviews r WHERE r.product_id = p.product_id) >= 4.5
  AND (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.product_id) >= 50
ORDER BY p.product_id;

-- [2] 튜닝 전 - 성능 측정 (상품마다 AVG/COUNT 서브쿼리 반복, reviews를 상품 수만큼 반복 스캔)
-- 문제: 상품마다 AVG(rating)/COUNT(*) 상관 서브쿼리를 SELECT/WHERE 절에서 각각 반복 호출,
--       상품 수만큼 reviews 테이블을 반복 스캔하는 N+1 패턴.
EXPLAIN (ANALYZE, BUFFERS)
SELECT p.product_id,
       (SELECT AVG(r.rating) FROM reviews r WHERE r.product_id = p.product_id) AS avg_rating,
       (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.product_id) AS review_cnt
FROM products p
WHERE (SELECT AVG(r.rating) FROM reviews r WHERE r.product_id = p.product_id) >= 4.5
  AND (SELECT COUNT(*) FROM reviews r WHERE r.product_id = p.product_id) >= 50
ORDER BY p.product_id;

-- 튜닝: rating을 포함한 커버링 인덱스로 Index Only Scan 유도
CREATE INDEX IF NOT EXISTS idx_reviews_product_cover ON reviews (product_id) INCLUDE (rating);

SELECT product_id, AVG(rating) AS avg_rating, COUNT(*) AS review_cnt
FROM reviews
GROUP BY product_id
HAVING AVG(rating) >= 4.5 AND COUNT(*) >= 50
ORDER BY product_id;

-- [4] 튜닝 후 - 성능 측정 (단일 GROUP BY/HAVING으로 한 번의 스캔)
-- 효과: 커버링 인덱스 덕분에 힙 접근 없이 인덱스만으로 집계(Index Only Scan) 가능.
EXPLAIN (ANALYZE, BUFFERS)
SELECT product_id, AVG(rating) AS avg_rating, COUNT(*) AS review_cnt
FROM reviews
GROUP BY product_id
HAVING AVG(rating) >= 4.5 AND COUNT(*) >= 50
ORDER BY product_id;


-- ============================================================
-- Q9) 쿠폰 사용 영향 (쿠폰 사용 주문 vs 미사용 주문 평균금액)
-- ============================================================

-- [1] 튜닝 전 - 결과 확인 (After와 같은 정렬로 맞춤)
-- 요구사항: 쿠폰을 사용한 주문과 사용하지 않은 주문의 평균 주문 금액 비교.
-- 컬럼 선택: used_coupon 라벨과 avg_order_amount만 명시적으로 선택
--            (기존 SELECT * FROM (...) x는 불필요한 컬럼 선택 위험이 있어 컬럼명을 명시하도록 수정).
SELECT used_coupon, avg_order_amount FROM (
  SELECT 'no_coupon' AS used_coupon, AVG(order_amount) AS avg_order_amount
  FROM (
    SELECT o.order_id, SUM(oi.line_total) AS order_amount
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.coupon_code IS NULL
    GROUP BY o.order_id
  ) t
  UNION ALL
  SELECT 'coupon' AS used_coupon, AVG(order_amount)
  FROM (
    SELECT o.order_id, SUM(oi.line_total) AS order_amount
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.coupon_code IS NOT NULL
    GROUP BY o.order_id
  ) t
) x
ORDER BY used_coupon;

-- [2] 튜닝 전 - 성능 측정 (그룹별로 따로 쿼리 짜서 UNION -> orders/order_items를 두 번 스캔)
-- 문제: 쿠폰 있음/없음 두 그룹을 각각 별도 쿼리로 작성한 뒤 UNION ALL로 합쳐서
--       orders/order_items 조인을 두 번 반복 수행하게 된다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT used_coupon, avg_order_amount FROM (
  SELECT 'no_coupon' AS used_coupon, AVG(order_amount) AS avg_order_amount
  FROM (
    SELECT o.order_id, SUM(oi.line_total) AS order_amount
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.coupon_code IS NULL
    GROUP BY o.order_id
  ) t
  UNION ALL
  SELECT 'coupon' AS used_coupon, AVG(order_amount)
  FROM (
    SELECT o.order_id, SUM(oi.line_total) AS order_amount
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.coupon_code IS NOT NULL
    GROUP BY o.order_id
  ) t
) x
ORDER BY used_coupon;

-- 튜닝: coupon_code 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_orders_coupon ON orders (coupon_code);

SELECT CASE WHEN o.coupon_code IS NOT NULL THEN 'coupon' ELSE 'no_coupon' END AS used_coupon,
       AVG(order_amount) AS avg_order_amount
FROM (
  SELECT o.order_id, o.coupon_code, SUM(oi.line_total) AS order_amount
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY o.order_id, o.coupon_code
) o
GROUP BY used_coupon
ORDER BY used_coupon;

-- [4] 튜닝 후 - 성능 측정 (한 번의 스캔으로 양쪽 그룹 동시 집계)
EXPLAIN (ANALYZE, BUFFERS)
SELECT CASE WHEN o.coupon_code IS NOT NULL THEN 'coupon' ELSE 'no_coupon' END AS used_coupon,
       AVG(order_amount) AS avg_order_amount
FROM (
  SELECT o.order_id, o.coupon_code, SUM(oi.line_total) AS order_amount
  FROM orders o
  JOIN order_items oi ON oi.order_id = o.order_id
  GROUP BY o.order_id, o.coupon_code
) o
GROUP BY used_coupon
ORDER BY used_coupon;


-- ============================================================
-- Q10) 상위 1% 고객의 최근 60일 매출
-- ============================================================

-- [1] 튜닝 전 - 결과 확인
-- 요구사항: 누적 매출 기준 상위 1% 고객을 가려내고, 이들의 최근 60일 매출을 조회.
-- 컬럼 선택: customer_id, recent_60d_revenue만 선택.
SELECT o.customer_id, SUM(oi.line_total) AS recent_60d_revenue
FROM (
  SELECT customer_id, SUM(oi2.line_total) AS total_revenue
  FROM orders o2 JOIN order_items oi2 ON oi2.order_id = o2.order_id
  GROUP BY customer_id
) ct
JOIN orders o ON o.customer_id = ct.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE ct.total_revenue >= (
  SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_revenue)
  FROM (SELECT customer_id, SUM(oi3.line_total) AS total_revenue
        FROM orders o3 JOIN order_items oi3 ON oi3.order_id = o3.order_id
        GROUP BY customer_id) x
)
AND o.order_ts >= now() - INTERVAL '60 days'
GROUP BY o.customer_id
ORDER BY o.customer_id;

-- [2] 튜닝 전 - 성능 측정 (전체고객 매출 계산+백분위+최근매출을 한 쿼리에 뒤섞음, 상위1% 밖 고객도 다 훑음)
-- 문제: 전체 고객 매출 계산, 백분위(PERCENTILE_CONT) 계산, 최근 매출 계산이 한 쿼리에
--       뒤섞여 있어, 최종적으로 상위 1%에 들지 못하는 고객까지 전부 조인·집계한 뒤에야
--       필터링되는 비효율이 있다.
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.customer_id, SUM(oi.line_total) AS recent_60d_revenue
FROM (
  SELECT customer_id, SUM(oi2.line_total) AS total_revenue
  FROM orders o2 JOIN order_items oi2 ON oi2.order_id = o2.order_id
  GROUP BY customer_id
) ct
JOIN orders o ON o.customer_id = ct.customer_id
JOIN order_items oi ON oi.order_id = o.order_id
WHERE ct.total_revenue >= (
  SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_revenue)
  FROM (SELECT customer_id, SUM(oi3.line_total) AS total_revenue
        FROM orders o3 JOIN order_items oi3 ON oi3.order_id = o3.order_id
        GROUP BY customer_id) x
)
AND o.order_ts >= now() - INTERVAL '60 days'
GROUP BY o.customer_id
ORDER BY o.customer_id;

-- [3] 튜닝 후 - 결과 확인 (상위 1% 고객 집합을 먼저 확정한 뒤, 그 소수 집합만 재조회)
-- 튜닝: PERCENT_RANK()로 상위 1% 고객 집합(top_customers)을 CTE로 먼저 확정한 뒤,
--       확정된 소수 고객에 대해서만 최근 60일 매출을 다시 조회
--       -> 처리해야 하는 데이터량이 대폭 감소.
-- 검증: customer_id가 대부분 1~30 사이로 나와야 정상 (seed의 heavy customers)

-- [4] 튜닝 후 - 성능 측정
EXPLAIN (ANALYZE, BUFFERS)
WITH top_customers AS (
  SELECT customer_id
  FROM (
    SELECT o.customer_id,
           PERCENT_RANK() OVER (ORDER BY SUM(oi.line_total) DESC) AS pr
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY o.customer_id
  ) r
  WHERE r.pr <= 0.01
)
SELECT o.customer_id, SUM(oi.line_total) AS recent_60d_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.customer_id IN (SELECT customer_id FROM top_customers)
  AND o.order_ts >= now() - INTERVAL '60 days'
GROUP BY o.customer_id
ORDER BY o.customer_id;
