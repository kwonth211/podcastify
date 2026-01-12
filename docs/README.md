# 📚 Daily News Podcast - 개발 문서

이 폴더에는 Daily News Podcast 프로젝트의 모든 개발 문서가 포함되어 있습니다.

---

## 문서 목록

| 문서 | 설명 | 대상 |
|------|------|------|
| [BACKEND_SPEC.md](./BACKEND_SPEC.md) | API 명세서 | 프론트엔드/백엔드 개발자 |
| [FRONTEND_GUIDE.md](./FRONTEND_GUIDE.md) | 프론트엔드 개발 가이드 | 프론트엔드 개발자 |
| [SCHEDULER_FLOW.md](./SCHEDULER_FLOW.md) | 스케줄러 시스템 상세 | 백엔드 개발자 |
| [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) | 데이터베이스 스키마 | 백엔드 개발자 |

---

## 문서 상세

### 📖 BACKEND_SPEC.md

**API 명세서** - 모든 REST API 엔드포인트 문서

- 인증 방식 (Supabase Auth, JWT)
- 전체 엔드포인트 목록 및 상세
- 요청/응답 JSON 예시
- TypeScript 타입 정의
- 에러 코드 목록
- 플랜별 기능 비교

### 📖 FRONTEND_GUIDE.md

**프론트엔드 개발 가이드** - React/Next.js 구현 예시

- Supabase 클라이언트 설정
- API 클라이언트 설정
- Google OAuth 구현
- 주요 컴포넌트 구현 예시
- 결제 연동 (Stripe, 토스)

### 📖 SCHEDULER_FLOW.md

**스케줄러 시스템 상세** - 자동 팟캐스트 생성 시스템

- 스케줄 생성/실행 플로우
- Cron Job 로직
- 팟캐스트 생성 Worker
- Redis 키 구조
- 에러 처리 및 재시도

### 📖 DATABASE_SCHEMA.md

**데이터베이스 스키마** - Supabase/PostgreSQL 테이블 구조

- ERD 다이어그램
- 테이블 상세 스키마
- RLS 정책
- 인덱스 설정

---

## 빠른 링크

### 프론트엔드 개발자

1. [BACKEND_SPEC.md](./BACKEND_SPEC.md) 읽기
2. [FRONTEND_GUIDE.md](./FRONTEND_GUIDE.md)의 코드 복사
3. TypeScript 타입 정의 복사 ([BACKEND_SPEC.md#typescript-타입-정의](./BACKEND_SPEC.md#typescript-타입-정의))

### 백엔드 개발자

1. [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)로 Supabase 설정
2. [SCHEDULER_FLOW.md](./SCHEDULER_FLOW.md)로 스케줄러 이해
3. [BACKEND_SPEC.md](./BACKEND_SPEC.md)로 API 확인

---

## 문서 업데이트

문서 수정 시 다음 규칙을 따라주세요:

1. **API 변경 시**: BACKEND_SPEC.md 동기화
2. **DB 스키마 변경 시**: DATABASE_SCHEMA.md 및 migrations 파일 동기화
3. **새 기능 추가 시**: 관련 문서에 예시 추가

---

_마지막 업데이트: 2026-01-12_
