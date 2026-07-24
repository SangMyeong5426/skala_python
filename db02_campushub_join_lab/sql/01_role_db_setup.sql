-- ============================================================
-- 종합실습 2 : STEP A. 롤(skala_user) & 데이터베이스(skala_db) 생성
-- ============================================================
-- DBeaver 사용 안내
--  1) 이 파일은 "postgres" (또는 template1 등 기본 관리용 DB)에 연결된
--     슈퍼유저 계정(예: postgres)으로 실행하세요. skala_db에는 아직
--     아무것도 없으므로 skala_db로 접속해서 실행하면 안 됩니다.
--  2) 전체 실행(Alt+X)하지 말고, 아래 STEP을 순서대로 한 문장씩(Ctrl+Enter,
--     macOS는 ⌘+Return) 실행하세요. CREATE DATABASE는 트랜잭션 안에서
--     실행할 수 없어서 다른 문장과 묶어 한 번에 실행하면 오류가 날 수 있습니다.
--  3) 원본 스크립트의 `\prompt`(대화형 비밀번호 입력)는 DBeaver에서 지원되지
--     않으므로, 아래 STEP A2에서 비밀번호를 직접 입력해서 실행하세요.
-- ============================================================

-- ────────────────────────────────────────────
-- STEP A1: 롤(사용자) 생성
-- ────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'skala_user') THEN
    CREATE ROLE skala_user
      LOGIN
      NOSUPERUSER NOCREATEDB NOCREATEROLE;
    RAISE NOTICE 'Role skala_user created.';
  ELSE
    RAISE NOTICE 'Role skala_user already exists — password will be updated.';
  END IF;
END
$$;

-- ────────────────────────────────────────────
-- STEP A2: 비밀번호 설정
--   ↓↓↓ 'CHANGE_ME_PASSWORD' 를 실제 비밀번호로 바꾼 뒤 실행하세요 ↓↓↓
--   (실제 비밀번호를 파일에 그대로 남기지 않기 위해 자리표시자로 둡니다)
-- ────────────────────────────────────────────
ALTER ROLE skala_user PASSWORD 'CHANGE_ME_PASSWORD';

-- ────────────────────────────────────────────
-- STEP A3: 데이터베이스 존재 여부 확인 (0건이어야 정상)
-- ────────────────────────────────────────────
SELECT datname FROM pg_database WHERE datname = 'skala_db';

-- ────────────────────────────────────────────
-- STEP A4: 데이터베이스 생성 (STEP A3 결과가 0건일 때만 실행)
-- ────────────────────────────────────────────
CREATE DATABASE skala_db
  OWNER    = skala_user
  ENCODING = 'UTF8'
  TEMPLATE = template0;

-- ────────────────────────────────────────────
-- 다음 단계 안내
-- ────────────────────────────────────────────
-- 여기까지 완료되면, DBeaver에서 skala_db로 연결을 새로 열고
-- 02_schema_tables_data.sql 파일을 이어서 실행하세요.
