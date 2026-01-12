# Daily News Podcast - 데이터베이스 스키마

## 개요

이 문서는 Supabase (PostgreSQL) 데이터베이스 스키마를 설명합니다.

**SQL 파일 위치**: `podcastify/api/db/migrations/001_initial_schema.sql`

---

## ERD (Entity Relationship Diagram)

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    users     │       │subscriptions │       │   credits    │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK)      │       │ id (PK)      │
│ google_id    │  │    │ user_id (FK) │──┐    │ user_id (FK) │──┐
│ email        │  └───▶│ plan_id      │  │    │ used         │  │
│ name         │       │ status       │  │    │ limit        │  │
│ picture      │       │ period_start │  │    │ reset_date   │  │
│ supabase_id  │       │ period_end   │  │    └──────────────┘  │
│ created_at   │       │ cancel_at    │  │                      │
│ updated_at   │       │ created_at   │  │    ┌──────────────┐  │
└──────────────┘       └──────────────┘  │    │ batch_tokens │  │
        │                                │    ├──────────────┤  │
        │                                │    │ id (PK)      │  │
        ▼                                │    │ user_id (FK) │──┤
┌──────────────┐       ┌──────────────┐  │    │ remaining    │  │
│  schedules   │       │   podcasts   │  │    │ total        │  │
├──────────────┤       ├──────────────┤  │    │ valid_until  │  │
│ id (PK)      │       │ id (PK)      │  │    └──────────────┘  │
│ user_id (FK) │       │ user_id (FK) │◀─┤                      │
│ prompt       │       │ schedule_id  │──┤    ┌──────────────┐  │
│ days         │       │ prompt       │  │    │   payments   │  │
│ time         │       │ title        │  │    ├──────────────┤  │
│ timezone     │       │ script       │  │    │ id (PK)      │  │
│ email        │       │ audio_url    │  │    │ user_id (FK) │◀─┘
│ is_active    │       │ status       │  │    │ plan_id      │
│ last_run     │       │ play_count   │  │    │ amount       │
│ next_run     │       │ created_at   │  │    │ provider     │
│ created_at   │       └──────────────┘  │    │ status       │
│ updated_at   │                         │    │ created_at   │
└──────────────┘                         │    └──────────────┘
                                         │
                       ┌──────────────┐  │
                       │scheduler_jobs│  │
                       ├──────────────┤  │
                       │ id (PK)      │  │
                       │ schedule_id  │◀─┘
                       │ podcast_id   │
                       │ status       │
                       │ attempts     │
                       │ error_msg    │
                       │ created_at   │
                       └──────────────┘
```

---

## 테이블 상세

### 1. users (사용자)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    google_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    picture TEXT,
    auth_provider VARCHAR(50) DEFAULT 'google',
    supabase_auth_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | 기본 키 |
| google_id | VARCHAR | Google OAuth ID |
| email | VARCHAR | 이메일 (unique) |
| name | VARCHAR | 사용자 이름 |
| picture | TEXT | 프로필 이미지 URL |
| supabase_auth_id | UUID | Supabase Auth 연결 (FK) |

---

### 2. subscriptions (구독)

```sql
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id plan_type NOT NULL DEFAULT 'free',
    status subscription_status NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMPTZ NOT NULL,
    current_period_end TIMESTAMPTZ NOT NULL,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    toss_subscription_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_subscription UNIQUE (user_id)
);

-- ENUM Types
CREATE TYPE subscription_status AS ENUM ('active', 'canceled', 'past_due', 'trialing', 'unpaid');
CREATE TYPE plan_type AS ENUM ('free', 'basic', 'pro');
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | UUID | 사용자 (FK, unique) |
| plan_id | ENUM | free / basic / pro |
| status | ENUM | 구독 상태 |
| current_period_start | TIMESTAMPTZ | 현재 기간 시작 |
| current_period_end | TIMESTAMPTZ | 현재 기간 종료 |
| cancel_at_period_end | BOOLEAN | 기간 종료 시 취소 여부 |
| stripe_subscription_id | VARCHAR | Stripe 구독 ID |
| toss_subscription_id | VARCHAR | 토스 구독 ID |

---

### 3. credits (온디맨드 크레딧)

```sql
CREATE TABLE credits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generations_used INTEGER NOT NULL DEFAULT 0,
    generations_limit INTEGER NOT NULL DEFAULT 1,
    reset_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_credits UNIQUE (user_id)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| generations_used | INTEGER | 사용한 크레딧 |
| generations_limit | INTEGER | 한도 (-1 = 무제한) |
| reset_date | TIMESTAMPTZ | 다음 리셋 날짜 |

---

### 4. batch_tokens (배치 토큰)

```sql
CREATE TABLE batch_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tokens_remaining INTEGER NOT NULL DEFAULT 0,
    tokens_total INTEGER NOT NULL DEFAULT 0,
    valid_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_batch_tokens UNIQUE (user_id)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| tokens_remaining | INTEGER | 남은 토큰 (-1 = 무제한) |
| tokens_total | INTEGER | 총 토큰 |
| valid_until | TIMESTAMPTZ | 만료 시간 |

---

### 5. schedules (스케줄)

```sql
CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) DEFAULT 'My Schedule',
    prompt TEXT NOT NULL,
    days day_of_week[] NOT NULL,
    time TIME NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Seoul',
    email VARCHAR(255) NOT NULL,
    language VARCHAR(10) DEFAULT 'ko',
    tts_model VARCHAR(50) DEFAULT 'gemini',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_run TIMESTAMPTZ,
    next_run TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ENUM Type
CREATE TYPE day_of_week AS ENUM (
    'monday', 'tuesday', 'wednesday', 'thursday', 
    'friday', 'saturday', 'sunday'
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| prompt | TEXT | 뉴스 검색 프롬프트 |
| days | day_of_week[] | 실행 요일 배열 |
| time | TIME | 실행 시간 |
| timezone | VARCHAR | IANA 타임존 |
| email | VARCHAR | 결과 전송 이메일 |
| is_active | BOOLEAN | 활성화 여부 |
| next_run | TIMESTAMPTZ | 다음 실행 시간 |

---

### 6. podcasts (팟캐스트)

```sql
CREATE TABLE podcasts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    schedule_id UUID REFERENCES schedules(id) ON DELETE SET NULL,
    prompt TEXT NOT NULL,
    title VARCHAR(500),
    script TEXT,
    audio_url TEXT,
    transcript_url TEXT,
    sources_url TEXT,
    duration INTEGER,
    file_size INTEGER,
    status podcast_status NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    current_step VARCHAR(50),
    play_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ENUM Type
CREATE TYPE podcast_status AS ENUM ('pending', 'generating', 'completed', 'failed');
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| schedule_id | UUID | 스케줄 (FK, nullable) |
| status | ENUM | pending / generating / completed / failed |
| progress | INTEGER | 진행률 (0-100) |
| current_step | VARCHAR | prompting / crawling / summarizing / generating |
| metadata | JSONB | 추가 메타데이터 |

---

### 7. payments (결제)

```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id plan_type NOT NULL,
    amount INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'KRW',
    provider payment_provider NOT NULL,
    provider_payment_id VARCHAR(255),
    provider_order_id VARCHAR(255),
    status payment_status NOT NULL DEFAULT 'pending',
    description TEXT,
    metadata JSONB DEFAULT '{}',
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ENUM Types
CREATE TYPE payment_status AS ENUM (
    'pending', 'processing', 'completed', 
    'failed', 'canceled', 'refunded'
);
CREATE TYPE payment_provider AS ENUM ('stripe', 'toss');
```

---

### 8. scheduler_jobs (스케줄러 작업)

```sql
CREATE TABLE scheduler_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    podcast_id UUID REFERENCES podcasts(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

---

## 인덱스

```sql
-- Users
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_supabase_auth_id ON users(supabase_auth_id);

-- Subscriptions
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);

-- Credits
CREATE INDEX idx_credits_user_id ON credits(user_id);
CREATE INDEX idx_credits_reset_date ON credits(reset_date);

-- Batch Tokens
CREATE INDEX idx_batch_tokens_user_id ON batch_tokens(user_id);
CREATE INDEX idx_batch_tokens_valid_until ON batch_tokens(valid_until);

-- Schedules
CREATE INDEX idx_schedules_user_id ON schedules(user_id);
CREATE INDEX idx_schedules_next_run ON schedules(next_run) WHERE is_active = TRUE;
CREATE INDEX idx_schedules_is_active ON schedules(is_active);

-- Podcasts
CREATE INDEX idx_podcasts_user_id ON podcasts(user_id);
CREATE INDEX idx_podcasts_schedule_id ON podcasts(schedule_id);
CREATE INDEX idx_podcasts_status ON podcasts(status);
CREATE INDEX idx_podcasts_created_at ON podcasts(created_at DESC);

-- Payments
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_provider_payment_id ON payments(provider_payment_id);
```

---

## Row Level Security (RLS)

모든 테이블에 RLS가 활성화되어 있습니다:

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
-- ... (모든 테이블)
```

### 주요 정책

```sql
-- 사용자는 자신의 데이터만 조회 가능
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid() = supabase_auth_id);

-- 서비스 롤은 모든 접근 가능
CREATE POLICY "Service role full access" ON users
    FOR ALL USING (auth.role() = 'service_role');
```

---

## 트리거

### updated_at 자동 업데이트

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 모든 관련 테이블에 적용
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

### 신규 사용자 초기화

```sql
CREATE OR REPLACE FUNCTION create_user_defaults()
RETURNS TRIGGER AS $$
BEGIN
    -- Free 구독 생성
    INSERT INTO subscriptions (user_id, plan_id, status) VALUES (...);
    -- 기본 크레딧 생성
    INSERT INTO credits (user_id, generations_limit) VALUES (...);
    -- 배치 토큰 생성
    INSERT INTO batch_tokens (user_id, tokens_remaining, tokens_total) VALUES (...);
    RETURN NEW;
END;
$$ language 'plpgsql';
```

---

## 뷰

### user_stats (사용자 통계)

```sql
CREATE OR REPLACE VIEW user_stats AS
SELECT 
    u.id,
    u.email,
    u.name,
    s.plan_id,
    s.status as subscription_status,
    c.generations_used,
    c.generations_limit,
    bt.tokens_remaining as batch_tokens_remaining,
    (SELECT COUNT(*) FROM schedules WHERE user_id = u.id AND is_active = TRUE) as active_schedules,
    (SELECT COUNT(*) FROM podcasts WHERE user_id = u.id) as total_podcasts,
    u.created_at
FROM users u
LEFT JOIN subscriptions s ON u.id = s.user_id
LEFT JOIN credits c ON u.id = c.user_id
LEFT JOIN batch_tokens bt ON u.id = bt.user_id;
```

---

## Supabase 설정 방법

1. Supabase 대시보드 → SQL Editor 열기
2. `podcastify/api/db/migrations/001_initial_schema.sql` 내용 복사
3. SQL Editor에서 실행
4. Authentication → Providers → Google 활성화

---

_마지막 업데이트: 2026-01-12_
