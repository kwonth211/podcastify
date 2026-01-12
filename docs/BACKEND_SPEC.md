# Daily News Podcast - Backend API 명세서

## 목차

1. [개요](#개요)
2. [인증](#인증)
3. [공통 응답 형식](#공통-응답-형식)
4. [API 엔드포인트](#api-엔드포인트)
   - [인증 API](#1-인증-api)
   - [사용자 API](#2-사용자-api)
   - [구독 API](#3-구독-api)
   - [크레딧 API](#4-크레딧-api)
   - [스케줄 API](#5-스케줄-api)
   - [팟캐스트 API](#6-팟캐스트-api)
   - [결제 API](#7-결제-api)
5. [플랜 및 기능](#플랜-및-기능)
6. [에러 코드](#에러-코드)
7. [TypeScript 타입 정의](#typescript-타입-정의)
8. [Webhook](#webhook)

---

## 개요

### Base URL

```
Production: https://api.dailynewspod.com/api/v2
Development: http://localhost:8000/api/v2
```

### API 버전

- **v2** (현재): Supabase 기반 새 백엔드
- **v1** (레거시): 기존 API (호환성 유지)

---

## 인증

### 인증 방식

1. **Bearer Token (JWT)** - 사용자 인증용
2. **API Key** - 서비스 간 통신용

### Bearer Token 사용

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### API Key 사용

```http
X-API-Key: your-api-key
```

### Supabase Auth 연동

프론트엔드에서는 Supabase Auth UI를 사용하여 Google OAuth를 처리합니다:

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// Google OAuth 로그인
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${window.location.origin}/auth/callback`
  }
})

// 세션에서 토큰 가져오기
const { data: { session } } = await supabase.auth.getSession()
const token = session?.access_token
```

---

## 공통 응답 형식

### 성공 응답

```json
{
  "success": true,
  "data": { ... }
}
```

### 에러 응답

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  }
}
```

### 페이지네이션 응답

```json
{
  "success": true,
  "data": {
    "items": [...],
    "total": 100,
    "limit": 20,
    "offset": 0
  }
}
```

---

## API 엔드포인트

### 1. 인증 API

#### `GET /auth/me`

현재 로그인된 사용자 정보를 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "홍길동",
    "picture": "https://lh3.googleusercontent.com/..."
  }
}
```

**Error Responses:**
- `401 UNAUTHORIZED` - 토큰이 없거나 유효하지 않음

---

#### `POST /auth/refresh`

Refresh 토큰으로 새 Access 토큰을 발급받습니다.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600
  }
}
```

---

#### `POST /auth/logout`

현재 세션을 종료합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

### 2. 사용자 API

#### `GET /users/me`

현재 사용자 프로필을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "홍길동",
    "picture": "https://lh3.googleusercontent.com/...",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

#### `GET /users/me/stats`

사용자 통계 정보를 반환합니다 (구독, 크레딧, 스케줄 등).

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "홍길동",
    "picture": "https://lh3.googleusercontent.com/...",
    "created_at": "2024-01-15T10:00:00Z",
    "plan_id": "basic",
    "subscription_status": "active",
    "generations_used": 2,
    "generations_limit": 3,
    "batch_tokens_remaining": 25,
    "active_schedules": 2,
    "total_podcasts": 15
  }
}
```

---

#### `PATCH /users/me`

사용자 프로필을 업데이트합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "name": "새 이름",
  "picture": "https://new-picture-url.com/..."
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "새 이름",
    "picture": "https://new-picture-url.com/...",
    "created_at": "2024-01-15T10:00:00Z"
  }
}
```

---

#### `DELETE /users/me`

계정을 삭제합니다 (모든 관련 데이터 삭제).

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Account deleted successfully"
}
```

---

### 3. 구독 API

#### `GET /subscriptions/plans`

사용 가능한 모든 플랜 목록을 반환합니다.

**Response:**
```json
{
  "success": true,
  "data": {
    "plans": {
      "free": {
        "plan_id": "free",
        "name": "Free",
        "price_usd": 0,
        "price_krw": 0,
        "generations_per_month": 1,
        "scheduler_enabled": true,
        "max_schedules": -1,
        "premium_voices": false,
        "priority_crawling": false,
        "rss_feed": false,
        "batch_tokens": 7,
        "batch_token_validity_days": 7
      },
      "basic": {
        "plan_id": "basic",
        "name": "Basic",
        "price_usd": 100,
        "price_krw": 1500,
        "generations_per_month": 3,
        "scheduler_enabled": true,
        "max_schedules": -1,
        "premium_voices": false,
        "priority_crawling": false,
        "rss_feed": false,
        "batch_tokens": 30,
        "batch_token_validity_days": 30
      },
      "pro": {
        "plan_id": "pro",
        "name": "Pro",
        "price_usd": 1000,
        "price_krw": 15000,
        "generations_per_month": -1,
        "scheduler_enabled": true,
        "max_schedules": -1,
        "premium_voices": true,
        "priority_crawling": true,
        "rss_feed": true,
        "batch_tokens": -1,
        "batch_token_validity_days": -1
      }
    }
  }
}
```

> **참고**: `-1`은 무제한을 의미합니다.

---

#### `GET /subscriptions/me`

현재 사용자의 구독 정보를 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "plan_id": "basic",
    "status": "active",
    "current_period_start": "2024-01-01T00:00:00Z",
    "current_period_end": "2024-02-01T00:00:00Z",
    "cancel_at_period_end": false,
    "features": {
      "plan_id": "basic",
      "name": "Basic",
      "price_usd": 100,
      "price_krw": 1500,
      "generations_per_month": 3,
      "scheduler_enabled": true,
      "max_schedules": -1,
      "premium_voices": false,
      "priority_crawling": false,
      "rss_feed": false,
      "batch_tokens": 30,
      "batch_token_validity_days": 30
    },
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T00:00:00Z"
  }
}
```

---

#### `POST /subscriptions/me/cancel`

구독을 취소합니다 (현재 기간 종료 시 적용).

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "cancel_at_period_end": true,
    "current_period_end": "2024-02-01T00:00:00Z"
  }
}
```

---

#### `POST /subscriptions/me/reactivate`

취소된 구독을 다시 활성화합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "plan_id": "basic",
    "status": "active",
    "cancel_at_period_end": false,
    ...
  }
}
```

---

### 4. 크레딧 API

#### `GET /credits/me`

현재 사용자의 크레딧 잔액을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "generations_used": 2,
    "generations_limit": 3,
    "remaining": 1,
    "reset_date": "2024-02-01T00:00:00Z"
  }
}
```

> **참고**: `generations_limit: -1`은 무제한 (Pro 플랜)

---

#### `GET /credits/batch-tokens/me`

현재 사용자의 배치 토큰 잔액을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "tokens_remaining": 25,
    "tokens_total": 30,
    "tokens_used": 5,
    "valid_until": "2024-02-01T00:00:00Z",
    "is_expired": false,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-15T00:00:00Z"
  }
}
```

> **참고**: 
> - `tokens_total: -1`은 무제한 (Pro 플랜)
> - 배치 토큰은 스케줄 실행 시 사용됩니다
> - 온디맨드 크레딧은 직접 생성 시 사용됩니다

---

### 5. 스케줄 API

#### `GET /schedules/me`

현재 사용자의 모든 스케줄을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| active_only | boolean | false | 활성 스케줄만 반환 |

**Response:**
```json
{
  "success": true,
  "data": {
    "schedules": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "아침 뉴스",
        "prompt": "AI 산업 최신 뉴스와 빅테크 기업 동향",
        "days": ["monday", "wednesday", "friday"],
        "time": "08:00",
        "timezone": "Asia/Seoul",
        "email": "user@example.com",
        "language": "ko",
        "tts_model": "gemini",
        "is_active": true,
        "last_run": "2024-01-15T08:00:00Z",
        "next_run": "2024-01-17T08:00:00Z",
        "run_count": 10,
        "failure_count": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-15T08:00:00Z"
      }
    ],
    "total": 1
  }
}
```

---

#### `POST /schedules`

새 스케줄을 생성합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "name": "아침 뉴스",
  "prompt": "AI 산업 최신 뉴스와 빅테크 기업 동향",
  "days": ["monday", "wednesday", "friday"],
  "time": "08:00",
  "timezone": "Asia/Seoul",
  "email": "user@example.com",
  "language": "ko",
  "tts_model": "gemini",
  "is_active": true
}
```

**Request Body 상세:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| name | string | No | "My Schedule" | 스케줄 이름 |
| prompt | string | **Yes** | - | 뉴스 검색 프롬프트 |
| days | string[] | **Yes** | - | 실행 요일 (monday~sunday) |
| time | string | **Yes** | - | 실행 시간 (HH:MM 형식) |
| timezone | string | No | "Asia/Seoul" | IANA 타임존 |
| email | string (email) | **Yes** | - | 결과 전송 이메일 |
| language | string | No | "ko" | 출력 언어 (ko, en, ja, zh) |
| tts_model | string | No | "gemini" | TTS 모델 |
| is_active | boolean | No | true | 활성화 여부 |

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "아침 뉴스",
    "prompt": "AI 산업 최신 뉴스와 빅테크 기업 동향",
    "days": ["monday", "wednesday", "friday"],
    "time": "08:00",
    "timezone": "Asia/Seoul",
    "email": "user@example.com",
    "language": "ko",
    "tts_model": "gemini",
    "is_active": true,
    "last_run": null,
    "next_run": "2024-01-17T08:00:00Z",
    "run_count": 0,
    "failure_count": 0,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
  }
}
```

**Error Responses:**
- `402 INSUFFICIENT_BATCH_TOKENS` - 배치 토큰이 없거나 만료됨
- `402 SCHEDULE_LIMIT_EXCEEDED` - 스케줄 한도 초과 (플랜 제한)

---

#### `GET /schedules/{schedule_id}`

특정 스케줄 정보를 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "아침 뉴스",
    ...
  }
}
```

---

#### `PATCH /schedules/{schedule_id}`

스케줄을 수정합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "name": "수정된 이름",
  "prompt": "수정된 프롬프트",
  "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
  "time": "07:30",
  "is_active": true
}
```

> 모든 필드는 선택사항입니다.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    ...
  }
}
```

---

#### `DELETE /schedules/{schedule_id}`

스케줄을 삭제합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Schedule deleted successfully"
}
```

---

#### `POST /schedules/{schedule_id}/toggle`

스케줄 활성화 상태를 토글합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "is_active": false,
    "next_run": null,
    ...
  }
}
```

---

#### `POST /schedules/{schedule_id}/test`

스케줄을 즉시 테스트 실행합니다 (배치 토큰 1개 소모).

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "podcast_id": "550e8400-e29b-41d4-a716-446655440003",
    "status": "generating"
  }
}
```

**Error Responses:**
- `402 INSUFFICIENT_BATCH_TOKENS` - 배치 토큰 부족

---

### 6. 팟캐스트 API

#### `GET /podcasts/me`

현재 사용자의 팟캐스트 목록을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | string | - | 필터링할 상태 (pending, generating, completed, failed) |
| limit | integer | 20 | 페이지당 항목 수 (1-100) |
| offset | integer | 0 | 시작 위치 |

**Response:**
```json
{
  "success": true,
  "data": {
    "podcasts": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "schedule_id": "550e8400-e29b-41d4-a716-446655440002",
        "prompt": "AI 뉴스 요약",
        "title": "AI 뉴스 요약 - 2024년 1월 15일",
        "audio_url": "/api/v2/podcasts/audio/podcast_20240115_080000.mp3",
        "transcript_url": "/api/v2/podcasts/transcripts/transcript_20240115_080000.txt",
        "duration": 300,
        "status": "completed",
        "play_count": 5,
        "created_at": "2024-01-15T08:00:00Z"
      }
    ],
    "total": 50,
    "limit": 20,
    "offset": 0
  }
}
```

---

#### `POST /podcasts/generate`

새 팟캐스트를 생성합니다 (온디맨드 크레딧 1개 소모).

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "prompt": "오늘 AI 산업 뉴스 요약해줘",
  "language": "ko",
  "tts_model": "gemini",
  "longform": false
}
```

**Request Body 상세:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| prompt | string | **Yes** | - | 뉴스 검색 프롬프트 |
| language | string | No | "ko" | 출력 언어 (ko, en, ja, zh) |
| tts_model | string | No | "gemini" | TTS 모델 (gemini, openai, edge, elevenlabs) |
| longform | boolean | No | false | 긴 형식 생성 여부 |

**Response:**
```json
{
  "success": true,
  "data": {
    "podcast_id": "550e8400-e29b-41d4-a716-446655440003",
    "status": "generating",
    "estimated_time": 120
  }
}
```

**Error Responses:**
- `402 INSUFFICIENT_CREDITS` - 크레딧 부족

---

#### `GET /podcasts/{podcast_id}`

팟캐스트 상세 정보를 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "schedule_id": null,
    "prompt": "AI 뉴스 요약",
    "title": "AI 뉴스 요약 - 2024년 1월 15일",
    "script": "안녕하세요, 오늘의 AI 뉴스를 요약해드리겠습니다...",
    "audio_url": "/api/v2/podcasts/audio/podcast_20240115_080000.mp3",
    "transcript_url": "/api/v2/podcasts/transcripts/transcript_20240115_080000.txt",
    "sources_url": "/api/v2/podcasts/sources/sources_20240115_080000.json",
    "duration": 300,
    "file_size": 4800000,
    "status": "completed",
    "error_message": null,
    "play_count": 5,
    "metadata": {
      "language": "ko",
      "tts_model": "gemini"
    },
    "created_at": "2024-01-15T08:00:00Z",
    "updated_at": "2024-01-15T08:05:00Z"
  }
}
```

---

#### `GET /podcasts/{podcast_id}/status`

팟캐스트 생성 상태를 반환합니다 (Polling 용).

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "status": "generating",
    "progress": 65,
    "current_step": "summarizing",
    "steps": [
      { "id": "prompting", "status": "completed", "message": null },
      { "id": "crawling", "status": "completed", "message": null },
      { "id": "summarizing", "status": "in_progress", "message": null },
      { "id": "generating", "status": "pending", "message": null }
    ],
    "error_message": null
  }
}
```

**Status 값:**
| Status | Progress | Description |
|--------|----------|-------------|
| pending | 0 | 대기 중 |
| generating | 10-90 | 생성 중 |
| completed | 100 | 완료 |
| failed | - | 실패 |

**Step 값:**
| Step | Progress | Description |
|------|----------|-------------|
| prompting | 10% | 프롬프트 분석 |
| crawling | 40% | 뉴스 크롤링 |
| summarizing | 70% | 요약 및 스크립트 생성 |
| generating | 90% | 오디오 생성 |
| completed | 100% | 완료 |

---

#### `POST /podcasts/{podcast_id}/play`

재생 카운트를 증가시킵니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Play recorded"
}
```

---

#### `DELETE /podcasts/{podcast_id}`

팟캐스트를 삭제합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Response:**
```json
{
  "success": true,
  "message": "Podcast deleted successfully"
}
```

---

#### `GET /podcasts/audio/{filename}`

오디오 파일을 스트리밍합니다.

**Response:** `audio/mpeg` 파일

---

#### `GET /podcasts/transcripts/{filename}`

트랜스크립트 파일을 반환합니다.

**Response:** `text/plain` 파일

---

#### `GET /podcasts/sources/{filename}`

뉴스 소스 JSON을 반환합니다.

**Response:**
```json
{
  "timestamp": "2024-01-15T08:00:00Z",
  "prompt": "AI 뉴스 요약",
  "language": "ko",
  "sources": [
    {
      "method": "gemini",
      "query": "AI",
      "referenced_urls": [
        "https://news.example.com/ai-article-1",
        "https://news.example.com/ai-article-2"
      ]
    }
  ]
}
```

---

### 7. 결제 API

#### `POST /payments/stripe/checkout`

Stripe 결제 세션을 생성합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "plan_id": "basic",
  "success_url": "https://yourapp.com/payment/success?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://yourapp.com/payment/cancel"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "session_id": "cs_test_a1b2c3d4...",
    "url": "https://checkout.stripe.com/pay/cs_test_a1b2c3d4..."
  }
}
```

**Frontend 처리:**
```typescript
const response = await fetch('/api/v2/payments/stripe/checkout', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    plan_id: 'basic',
    success_url: `${window.location.origin}/payment/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${window.location.origin}/payment/cancel`
  })
})

const { data } = await response.json()

// Stripe 결제 페이지로 리다이렉트
window.location.href = data.url
```

---

#### `POST /payments/toss/confirm`

토스페이먼츠 결제를 승인합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Request Body:**
```json
{
  "payment_key": "tossPaymentKey123...",
  "order_id": "basic_550e8400_1705312800",
  "amount": 1500
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "payment_key": "tossPaymentKey123...",
    "order_id": "basic_550e8400_1705312800",
    "status": "DONE",
    "total_amount": 1500,
    "method": "카드",
    "approved_at": "2024-01-15T10:00:00Z"
  }
}
```

**토스 결제 플로우:**
```typescript
// 1. 토스페이먼츠 SDK로 결제 요청
const tossPayments = await loadTossPayments(TOSS_CLIENT_KEY)

await tossPayments.requestPayment('카드', {
  amount: 1500,
  orderId: `basic_${userId}_${Date.now()}`,
  orderName: 'Daily News Podcast - Basic Plan',
  successUrl: `${window.location.origin}/payment/toss/success`,
  failUrl: `${window.location.origin}/payment/toss/fail`,
})

// 2. 성공 리다이렉트 후 승인 요청
// successUrl에서 paymentKey, orderId, amount 파라미터로 전달됨
const params = new URLSearchParams(window.location.search)
const response = await fetch('/api/v2/payments/toss/confirm', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    payment_key: params.get('paymentKey'),
    order_id: params.get('orderId'),
    amount: parseInt(params.get('amount'))
  })
})
```

---

#### `GET /payments/history`

결제 내역을 반환합니다.

**Headers:**
```http
Authorization: Bearer {token}
```

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer | 20 | 페이지당 항목 수 |
| offset | integer | 0 | 시작 위치 |

**Response:**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "plan_id": "basic",
        "amount": 1500,
        "currency": "KRW",
        "provider": "toss",
        "status": "completed",
        "paid_at": "2024-01-15T10:00:00Z",
        "created_at": "2024-01-15T09:55:00Z"
      }
    ],
    "total": 5
  }
}
```

---

## 플랜 및 기능

### 플랜 비교

| 기능 | Free | Basic | Pro |
|------|------|-------|-----|
| **가격 (월)** | 무료 | ₩1,500 / $1 | ₩15,000 / $10 |
| **온디맨드 생성** | 1회/월 | 3회/월 | 무제한 |
| **배치 토큰** | 7개/7일 | 30개/30일 | 무제한 |
| **스케줄 개수** | 무제한 | 무제한 | 무제한 |
| **프리미엄 음성** | ❌ | ❌ | ✅ |
| **우선 크롤링** | ❌ | ❌ | ✅ |
| **RSS 피드** | ❌ | ❌ | ✅ |

### 크레딧 시스템

#### 온디맨드 크레딧
- 직접 팟캐스트 생성 시 사용
- 매월 1일에 리셋
- 플랜별 한도 적용

#### 배치 토큰
- 스케줄 실행 시 사용
- 구독 시점부터 유효기간 적용
- 스케줄 1회 실행 = 토큰 1개 소모

---

## 에러 코드

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `UNAUTHORIZED` | 401 | 인증 필요 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `VALIDATION_ERROR` | 400 | 입력값 검증 실패 |
| `INSUFFICIENT_CREDITS` | 402 | 온디맨드 크레딧 부족 |
| `INSUFFICIENT_BATCH_TOKENS` | 402 | 배치 토큰 부족/만료 |
| `SCHEDULE_LIMIT_EXCEEDED` | 402 | 스케줄 한도 초과 |
| `PLAN_FEATURE_DISABLED` | 402 | 플랜에서 미지원 기능 |
| `PAYMENT_FAILED` | 400 | 결제 실패 |
| `RATE_LIMIT_EXCEEDED` | 429 | 요청 한도 초과 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |

---

## TypeScript 타입 정의

```typescript
// ============================================
// Common Types
// ============================================

interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    [key: string]: any;
  };
}

interface PaginatedResponse<T> {
  success: boolean;
  data: {
    items: T[];
    total: number;
    limit: number;
    offset: number;
  };
}

// ============================================
// User Types
// ============================================

interface User {
  id: string;
  email: string;
  name: string;
  picture: string | null;
  created_at: string;
}

interface UserStats extends User {
  plan_id: PlanType;
  subscription_status: SubscriptionStatus;
  generations_used: number;
  generations_limit: number;
  batch_tokens_remaining: number;
  active_schedules: number;
  total_podcasts: number;
}

// ============================================
// Subscription Types
// ============================================

type PlanType = 'free' | 'basic' | 'pro';
type SubscriptionStatus = 'active' | 'canceled' | 'past_due' | 'trialing' | 'unpaid';

interface PlanFeatures {
  plan_id: PlanType;
  name: string;
  price_usd: number;
  price_krw: number;
  generations_per_month: number; // -1 = unlimited
  scheduler_enabled: boolean;
  max_schedules: number; // -1 = unlimited
  premium_voices: boolean;
  priority_crawling: boolean;
  rss_feed: boolean;
  batch_tokens: number; // -1 = unlimited
  batch_token_validity_days: number; // -1 = no expiry
}

interface Subscription {
  id: string;
  user_id: string;
  plan_id: PlanType;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  features?: PlanFeatures;
  created_at: string;
  updated_at: string;
}

// ============================================
// Credits Types
// ============================================

interface Credits {
  user_id: string;
  generations_used: number;
  generations_limit: number; // -1 = unlimited
  remaining: number;
  reset_date: string;
}

interface BatchTokens {
  user_id: string;
  tokens_remaining: number; // -1 = unlimited
  tokens_total: number; // -1 = unlimited
  tokens_used: number;
  valid_until: string;
  is_expired: boolean;
  created_at: string;
  updated_at: string;
}

// ============================================
// Schedule Types
// ============================================

type DayOfWeek = 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday';
type Language = 'ko' | 'en' | 'ja' | 'zh';
type TTSModel = 'gemini' | 'openai' | 'edge' | 'elevenlabs';

interface Schedule {
  id: string;
  user_id: string;
  name: string;
  prompt: string;
  days: DayOfWeek[];
  time: string; // HH:MM format
  timezone: string; // IANA timezone
  email: string;
  language: Language;
  tts_model: TTSModel;
  is_active: boolean;
  last_run: string | null;
  next_run: string | null;
  run_count: number;
  failure_count: number;
  created_at: string;
  updated_at: string;
}

interface ScheduleCreate {
  name?: string;
  prompt: string;
  days: DayOfWeek[];
  time: string;
  timezone?: string;
  email: string;
  language?: Language;
  tts_model?: TTSModel;
  is_active?: boolean;
}

interface ScheduleUpdate {
  name?: string;
  prompt?: string;
  days?: DayOfWeek[];
  time?: string;
  timezone?: string;
  email?: string;
  language?: Language;
  tts_model?: TTSModel;
  is_active?: boolean;
}

// ============================================
// Podcast Types
// ============================================

type PodcastStatus = 'pending' | 'generating' | 'completed' | 'failed';
type StepStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

interface Podcast {
  id: string;
  user_id: string;
  schedule_id: string | null;
  prompt: string;
  title: string | null;
  audio_url: string | null;
  transcript_url: string | null;
  duration: number | null; // seconds
  status: PodcastStatus;
  play_count: number;
  created_at: string;
}

interface PodcastDetail extends Podcast {
  script: string | null;
  sources_url: string | null;
  file_size: number | null; // bytes
  error_message: string | null;
  metadata: Record<string, any>;
  updated_at: string;
}

interface PodcastGenerateRequest {
  prompt: string;
  language?: Language;
  tts_model?: TTSModel;
  longform?: boolean;
}

interface PodcastGenerateResponse {
  podcast_id: string;
  status: PodcastStatus;
  estimated_time: number; // seconds
}

interface GenerationStep {
  id: 'prompting' | 'crawling' | 'summarizing' | 'generating';
  status: StepStatus;
  message: string | null;
}

interface PodcastStatusResponse {
  id: string;
  status: PodcastStatus;
  progress: number; // 0-100
  current_step: string | null;
  steps: GenerationStep[];
  error_message: string | null;
}

// ============================================
// Payment Types
// ============================================

type PaymentProvider = 'stripe' | 'toss';
type PaymentStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'canceled' | 'refunded';

interface Payment {
  id: string;
  user_id: string;
  plan_id: PlanType;
  amount: number;
  currency: 'USD' | 'KRW';
  provider: PaymentProvider;
  status: PaymentStatus;
  paid_at: string | null;
  created_at: string;
}

interface StripeCheckoutRequest {
  plan_id: PlanType;
  success_url: string;
  cancel_url: string;
}

interface StripeCheckoutResponse {
  session_id: string;
  url: string;
}

interface TossConfirmRequest {
  payment_key: string;
  order_id: string;
  amount: number;
}

interface TossConfirmResponse {
  payment_key: string;
  order_id: string;
  status: string;
  total_amount: number;
  method: string;
  approved_at: string;
}
```

---

## Webhook

### Stripe Webhook

**Endpoint:** `POST /payments/webhook/stripe`

**Headers:**
```http
stripe-signature: t=1234567890,v1=abc123...
```

**Events 처리:**
- `checkout.session.completed` - 결제 완료
- `customer.subscription.updated` - 구독 업데이트
- `customer.subscription.deleted` - 구독 삭제
- `invoice.payment_failed` - 결제 실패

### Toss Webhook

**Endpoint:** `POST /payments/webhook/toss`

**Events 처리:**
- `PAYMENT_STATUS_CHANGED` - 결제 상태 변경

---

## 프론트엔드 구현 예시

### API 클라이언트 설정

```typescript
// lib/api-client.ts
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.dailynewspod.com/api/v2'

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token 
    ? { Authorization: `Bearer ${session.access_token}` }
    : {}
}

export async function apiGet<T>(endpoint: string): Promise<APIResponse<T>> {
  const headers = await getAuthHeader()
  const response = await fetch(`${API_BASE}${endpoint}`, { headers })
  return response.json()
}

export async function apiPost<T>(endpoint: string, body?: any): Promise<APIResponse<T>> {
  const headers = await getAuthHeader()
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      ...headers,
      'Content-Type': 'application/json'
    },
    body: body ? JSON.stringify(body) : undefined
  })
  return response.json()
}

export async function apiPatch<T>(endpoint: string, body: any): Promise<APIResponse<T>> {
  const headers = await getAuthHeader()
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'PATCH',
    headers: {
      ...headers,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })
  return response.json()
}

export async function apiDelete<T>(endpoint: string): Promise<APIResponse<T>> {
  const headers = await getAuthHeader()
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'DELETE',
    headers
  })
  return response.json()
}
```

### 사용 예시

```typescript
// 사용자 통계 가져오기
const { data: stats } = await apiGet<UserStats>('/users/me/stats')

// 스케줄 생성
const { data: schedule } = await apiPost<Schedule>('/schedules', {
  prompt: 'AI 뉴스 요약',
  days: ['monday', 'wednesday', 'friday'],
  time: '08:00',
  email: 'user@example.com'
})

// 팟캐스트 생성 및 상태 폴링
const { data: { podcast_id } } = await apiPost<PodcastGenerateResponse>('/podcasts/generate', {
  prompt: 'AI 뉴스 요약'
})

// 상태 폴링
const pollStatus = async () => {
  const { data: status } = await apiGet<PodcastStatusResponse>(`/podcasts/${podcast_id}/status`)
  
  if (status.status === 'completed') {
    // 완료됨
    const { data: podcast } = await apiGet<PodcastDetail>(`/podcasts/${podcast_id}`)
    return podcast
  } else if (status.status === 'failed') {
    throw new Error(status.error_message || 'Generation failed')
  } else {
    // 계속 폴링
    await new Promise(resolve => setTimeout(resolve, 3000))
    return pollStatus()
  }
}
```

---

## 문의

추가 질문이나 이슈가 있으시면 연락주세요! 🚀
