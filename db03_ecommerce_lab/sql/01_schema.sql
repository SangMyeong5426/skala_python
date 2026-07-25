-- ecom_schema_postgres_student.sql
-- E-Commerce DB: Postgres-centric schema (PostgreSQL 14+)

-- 0) Schema & Extensions (중요: 타입/제약에 필요한 확장 먼저!)
CREATE SCHEMA IF NOT EXISTS ecom;
SET search_path = ecom, public;

-- CITEXT(대소문자 무시 이메일) / EXCLUDE 제약용 btree_gist
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 1) Reference/Dimension tables
CREATE TABLE IF NOT EXISTS country (
  country_code CHAR(2) PRIMARY KEY,
  country_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGSERIAL PRIMARY KEY,
  email CITEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  phone TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  marketing_opt_in BOOLEAN NOT NULL DEFAULT false,
  country_code CHAR(2) REFERENCES country(country_code)
);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);
CREATE INDEX IF NOT EXISTS idx_customers_country ON customers(country_code);

CREATE TABLE IF NOT EXISTS addresses (
  address_id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
  line1 TEXT NOT NULL,
  line2 TEXT,
  city TEXT NOT NULL,
  state TEXT,
  postal_code TEXT,
  country_code CHAR(2) NOT NULL REFERENCES country(country_code),
  is_default BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_addresses_customer ON addresses(customer_id);

CREATE TABLE IF NOT EXISTS categories (
  category_id BIGSERIAL PRIMARY KEY,
  parent_id BIGINT REFERENCES categories(category_id) ON DELETE SET NULL,
  category_name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);

CREATE TABLE IF NOT EXISTS products (
  product_id BIGSERIAL PRIMARY KEY,
  sku TEXT UNIQUE NOT NULL,
  product_name TEXT NOT NULL,
  category_id BIGINT REFERENCES categories(category_id),
  unit TEXT NOT NULL DEFAULT 'each',
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);

-- SCD2-like price history (valid_from/valid_to windows)
CREATE TABLE IF NOT EXISTS product_prices (
  price_id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
  price NUMERIC(12,2) NOT NULL CHECK (price >= 0),
  currency CHAR(3) NOT NULL DEFAULT 'USD',
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to   TIMESTAMPTZ NOT NULL,
  is_current BOOLEAN NOT NULL DEFAULT true,
  -- 기간 뒤집힘 방지
  CHECK (valid_from < valid_to),
  -- (중요) 동일 product_id에 대해 기간 겹침 방지
  EXCLUDE USING gist (product_id WITH =, tstzrange(valid_from, valid_to, '[]') WITH &&)
);

-- "현재 가격"은 상품당 1개만 허용
CREATE UNIQUE INDEX IF NOT EXISTS ux_product_prices_current
ON product_prices(product_id)
WHERE is_current;

CREATE TABLE IF NOT EXISTS suppliers (
  supplier_id BIGSERIAL PRIMARY KEY,
  supplier_name TEXT NOT NULL,
  phone TEXT
);

CREATE TABLE IF NOT EXISTS product_suppliers (
  product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
  supplier_id BIGINT NOT NULL REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
  primary_supplier BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (product_id, supplier_id)
);

CREATE TABLE IF NOT EXISTS inventory (
  product_id BIGINT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
  qty_on_hand INT NOT NULL DEFAULT 0 CHECK (qty_on_hand >= 0),
  reorder_point INT NOT NULL DEFAULT 10 CHECK (reorder_point >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2) Fact tables
CREATE TABLE IF NOT EXISTS orders (
  order_id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id),
  order_status TEXT NOT NULL CHECK (order_status IN ('created','paid','shipped','delivered','cancelled','refunded')),
  order_ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  shipping_address_id BIGINT REFERENCES addresses(address_id),
  coupon_code TEXT,
  channel TEXT NOT NULL DEFAULT 'web' -- web, mobile, marketplace
);
CREATE INDEX IF NOT EXISTS idx_orders_customer_ts ON orders(customer_id, order_ts DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(order_status);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  qty INT NOT NULL CHECK (qty > 0),
  unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
  discount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (discount >= 0),
  -- (선택: 원치 않으면 주석처리) 할인 과다로 line_total 음수 방지
  CHECK (discount <= unit_price * qty),
  line_total NUMERIC(12,2) GENERATED ALWAYS AS ((unit_price * qty) - discount) STORED
);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);

CREATE TABLE IF NOT EXISTS payments (
  payment_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  method TEXT NOT NULL CHECK (method IN ('card','bank','paypal','cod')),
  amount NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
  paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);

CREATE TABLE IF NOT EXISTS shipments (
  shipment_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  carrier TEXT NOT NULL,
  tracking_no TEXT,
  shipped_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_shipments_order ON shipments(order_id);

CREATE TABLE IF NOT EXISTS reviews (
  review_id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
  rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(product_id, customer_id)
);

-- Helpful materialized view example (daily GMV)
-- NOTE: Materialized View는 자동 갱신되지 않습니다.
-- 실습 후 갱신이 필요하면:
--   REFRESH MATERIALIZED VIEW mv_daily_gmv;
-- (고급) 동시 갱신을 쓰려면:
--   CREATE UNIQUE INDEX ... 후
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_gmv;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_gmv AS
SELECT date_trunc('day', o.order_ts) AS day,
       sum(oi.line_total) AS gmv
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.order_status IN ('paid','shipped','delivered')
GROUP BY 1;

-- (고급 옵션) CONCURRENTLY를 쓰고 싶으면 UNIQUE 인덱스 권장
-- CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_daily_gmv_day ON mv_daily_gmv(day);
CREATE INDEX IF NOT EXISTS idx_mv_daily_gmv_day ON mv_daily_gmv(day);

-- UDF example: safe division for AOV
CREATE OR REPLACE FUNCTION f_safe_div(numer numeric, denom numeric)
RETURNS numeric LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
  IF denom = 0 THEN
    RETURN 0;
  END IF;
  RETURN numer/denom;
END $$;

-- View example: current price per product
CREATE OR REPLACE VIEW v_product_current_price AS
SELECT p.product_id, p.product_name, pp.price, pp.currency
FROM products p
JOIN product_prices pp
  ON pp.product_id = p.product_id AND pp.is_current;

-- Recursion example: category path
CREATE OR REPLACE VIEW v_category_path AS
WITH RECURSIVE r AS (
  SELECT category_id, parent_id, category_name, category_name::text AS path
  FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.category_id, c.parent_id, c.category_name, r.path || ' > ' || c.category_name
  FROM categories c JOIN r ON c.parent_id = r.category_id
)
SELECT * FROM r;

-- (선택) 수강생 확인용: 최소 시드 데이터(원하면 주석 해제)
-- INSERT INTO country(country_code, country_name) VALUES
-- ('KR','Korea'),('US','United States')
-- ON CONFLICT DO NOTHING;
