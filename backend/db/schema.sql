-- 이음러닝 행사 후속 관리 SQLite 설계도
-- 열 이름은 docs/data-schema.md 와 backend/data/build_profile.py 결과 CSV(data/processed/*.csv)와 같습니다.
--
-- - 여러 번 실행해도 됩니다 (CREATE ... IF NOT EXISTS).
-- - 외래 키는 SQLite 연결마다 켜야 합니다:  PRAGMA foreign_keys = ON;
-- - 데이터 넣는 순서: events → companies → customers → participation → surveys → interactions, contents
-- - 날짜는 TEXT 'YYYY-MM-DD', Y/N 값은 TEXT 'Y' / 'N' (빈 값은 NULL)

-- 행사 (00_행사목록)
CREATE TABLE IF NOT EXISTS events (
    event_id         TEXT PRIMARY KEY CHECK (event_id GLOB 'E[0-9][0-9]*'),  -- E01~
    event_name       TEXT NOT NULL,
    event_date       TEXT,
    event_type       TEXT,
    applied_count    INTEGER,
    attended_count   INTEGER,
    thanks_mail_date TEXT,                                                  -- 발송 못 했으면 NULL
    thanks_mail_sent TEXT CHECK (thanks_mail_sent IN ('Y', 'N')),
    survey_count     INTEGER,
    note             TEXT
);

-- 회사 (customers 에서 생성, 1개 회사 1행). industry_* 는 내부용 (고객 메일 문장에 쓰지 않음)
CREATE TABLE IF NOT EXISTS companies (
    company_key     TEXT PRIMARY KEY,                                       -- 정규화된 회사명
    company_name    TEXT,
    domain          TEXT,
    industry_major  TEXT,                                                   -- KSIC 대분류 (예: 'C 제조업')
    industry_mid    TEXT,                                                   -- KSIC 중분류
    industry_source TEXT CHECK (industry_source IN ('manual', 'llm'))      -- NULL = 미분류
);

-- 사람 (1명 1행, 이메일이 고객 ID)
CREATE TABLE IF NOT EXISTS customers (
    email          TEXT PRIMARY KEY,                                        -- 소문자·공백 제거
    name           TEXT,
    company        TEXT,
    company_key    TEXT REFERENCES companies (company_key),
    title          TEXT,
    consent        TEXT CHECK (consent IN ('Y', 'N')),
    first_event_id TEXT REFERENCES events (event_id),
    last_event_id  TEXT REFERENCES events (event_id)
);

-- 신청 1건 1행 (01_참가자명단_E0X)
CREATE TABLE IF NOT EXISTS participation (
    event_id     TEXT NOT NULL REFERENCES events (event_id),
    email        TEXT NOT NULL REFERENCES customers (email),
    name         TEXT NOT NULL,
    company      TEXT,                                                      -- 정규화
    company_raw  TEXT,                                                      -- 원본
    title        TEXT,
    pre_question TEXT,
    attended     TEXT NOT NULL CHECK (attended IN ('Y', 'N')),
    consent      TEXT CHECK (consent IN ('Y', 'N')),
    note         TEXT,
    source_file  TEXT,
    source_row   INTEGER,
    is_test      INTEGER NOT NULL DEFAULT 0 CHECK (is_test IN (0, 1)),
    PRIMARY KEY (event_id, email)
);

-- 만족도 설문 응답 (02_만족도설문, 응답 시트)
CREATE TABLE IF NOT EXISTS surveys (
    survey_id          TEXT PRIMARY KEY,                                    -- S001~
    event_id           TEXT REFERENCES events (event_id),
    response_date      TEXT,
    q1_satisfaction    INTEGER CHECK (q1_satisfaction BETWEEN 1 AND 5),
    q2_helpfulness     INTEGER CHECK (q2_helpfulness BETWEEN 1 AND 5),
    q3_recommend       INTEGER CHECK (q3_recommend BETWEEN 0 AND 10),
    q4_helpful_content TEXT,
    q5_wanted_topic    TEXT,
    q6_adoption        TEXT CHECK (q6_adoption IN ('Y', 'REVIEW', 'N')),
    q7_contact_wish    TEXT CHECK (q7_contact_wish IN ('Y', 'N')),
    email              TEXT REFERENCES customers (email),                   -- NULL = 익명 응답
    matched            TEXT CHECK (matched IN ('Y', 'N'))
);

-- 후속 연락 기록 (04_후속연락기록)
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,                                        -- I001~
    event_id       TEXT REFERENCES events (event_id),
    name           TEXT,
    company        TEXT,                                                    -- 정규화
    contact_date   TEXT,
    method         TEXT,
    memo           TEXT,
    result         TEXT,
    email          TEXT REFERENCES customers (email)                        -- 행사+이름+회사로 찾음, 못 찾으면 NULL
);

-- 발행 글 (03_발행글목록)
CREATE TABLE IF NOT EXISTS contents (
    content_id     TEXT PRIMARY KEY,                                        -- C001~
    published_date TEXT,
    channel        TEXT,
    title          TEXT,
    topic          TEXT,
    audience       TEXT,
    url            TEXT
);

-- 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_customers_company_key ON customers (company_key);
CREATE INDEX IF NOT EXISTS idx_participation_email   ON participation (email);
CREATE INDEX IF NOT EXISTS idx_surveys_event_id      ON surveys (event_id);
CREATE INDEX IF NOT EXISTS idx_surveys_email         ON surveys (email);
CREATE INDEX IF NOT EXISTS idx_interactions_event_id ON interactions (event_id);
CREATE INDEX IF NOT EXISTS idx_interactions_email    ON interactions (email);
