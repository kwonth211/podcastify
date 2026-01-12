# 스케줄러 시스템 상세 플로우

## 개요

스케줄러는 사용자가 설정한 시간에 자동으로 팟캐스트를 생성하고 이메일로 전송하는 시스템입니다.

---

## 시퀀스 다이어그램

### 1. 스케줄 생성 플로우

```
┌────────┐          ┌────────┐          ┌────────┐
│Frontend│          │ Backend│          │   DB   │
└───┬────┘          └───┬────┘          └───┬────┘
    │                   │                   │
    │ POST /schedules   │                   │
    │──────────────────▶│                   │
    │                   │                   │
    │                   │ 플랜 확인         │
    │                   │──────────────────▶│
    │                   │◀──────────────────│
    │                   │                   │
    │                   │ 스케줄 개수 확인  │
    │                   │──────────────────▶│
    │                   │◀──────────────────│
    │                   │                   │
    │                   │ 한도 검증         │
    │                   │ (maxSchedules)    │
    │                   │                   │
    │                   │ nextRun 계산      │
    │                   │                   │
    │                   │ INSERT schedule   │
    │                   │──────────────────▶│
    │                   │◀──────────────────│
    │                   │                   │
    │  Schedule 객체    │                   │
    │◀──────────────────│                   │
    │                   │                   │
```

### 2. 스케줄 실행 플로우

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│  Cron  │     │ Backend│     │  Queue │     │ Worker │     │   DB   │
└───┬────┘     └───┬────┘     └───┬────┘     └───┬────┘     └───┬────┘
    │              │              │              │              │
    │ 매 분 트리거 │              │              │              │
    │─────────────▶│              │              │              │
    │              │              │              │              │
    │              │ 실행 대상    │              │              │
    │              │ 스케줄 조회  │              │              │
    │              │─────────────────────────────────────────▶│
    │              │◀─────────────────────────────────────────│
    │              │              │              │              │
    │              │ [각 스케줄]  │              │              │
    │              │              │              │              │
    │              │ Job 추가     │              │              │
    │              │─────────────▶│              │              │
    │              │              │              │              │
    │              │ nextRun 갱신 │              │              │
    │              │─────────────────────────────────────────▶│
    │              │              │              │              │
    │              │              │ Job 처리     │              │
    │              │              │─────────────▶│              │
    │              │              │              │              │
    │              │              │              │ podcast 생성 │
    │              │              │              │─────────────▶│
    │              │              │              │              │
    │              │              │              │ AI 파이프라인│
    │              │              │              │ 실행         │
    │              │              │              │              │
    │              │              │              │ 결과 저장    │
    │              │              │              │─────────────▶│
    │              │              │              │              │
    │              │              │              │ 이메일 발송  │
    │              │              │              │              │
```

### 3. 팟캐스트 생성 파이프라인

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Podcast Generation Pipeline                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ STEP 1   │───▶│ STEP 2   │───▶│ STEP 3   │───▶│ STEP 4   │      │
│  │Prompting │    │ Crawling │    │Summarize │    │Generating│      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │              │
│       ▼               ▼               ▼               ▼              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │프롬프트  │    │웹 크롤링 │    │뉴스 요약 │    │TTS 변환  │      │
│  │분석/키워드│    │뉴스 수집 │    │스크립트  │    │오디오 생성│     │
│  │추출      │    │          │    │작성      │    │          │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│       │               │               │               │              │
│       ▼               ▼               ▼               ▼              │
│  keywords[]      articles[]      script text     audio_url          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 상세 구현 가이드

### 1. Cron Job 설정

```typescript
// 매 분 실행 (* * * * *)
import cron from "node-cron";
import { checkAndExecuteSchedules } from "./scheduler";

cron.schedule("* * * * *", async () => {
  console.log("Checking schedules...");
  await checkAndExecuteSchedules();
});
```

### 2. 스케줄 체크 로직

```typescript
async function checkAndExecuteSchedules() {
  const now = new Date();

  // 현재 시간에 실행되어야 하는 활성 스케줄 조회
  const pendingSchedules = await db.query(
    `
    SELECT s.*, u.email as user_email
    FROM schedules s
    JOIN users u ON s.user_id = u.id
    WHERE s.is_active = TRUE 
      AND s.next_run <= $1
    ORDER BY s.next_run ASC
    LIMIT 100
  `,
    [now]
  );

  for (const schedule of pendingSchedules) {
    try {
      // 배치 토큰 확인 (Pro 플랜은 무제한이므로 체크 생략)
      const userSubscription = await db.query(
        `
        SELECT s.plan_id, bt.tokens_remaining, bt.valid_until
        FROM subscriptions s
        LEFT JOIN batch_tokens bt ON s.user_id = bt.user_id
        WHERE s.user_id = $1 AND s.status = 'active'
      `,
        [schedule.user_id]
      );

      if (userSubscription && userSubscription.plan_id !== "pro") {
        const batchToken = await db.query(
          `
          SELECT tokens_remaining, valid_until 
          FROM batch_tokens 
          WHERE user_id = $1
        `,
          [schedule.user_id]
        );

        if (
          !batchToken ||
          batchToken.tokens_remaining <= 0 ||
          new Date(batchToken.valid_until) < now
        ) {
          console.log(
            `Skipping schedule ${schedule.id}: No batch tokens available`
          );
          // 스케줄 비활성화 (선택사항)
          await db.query(
            `
            UPDATE schedules SET is_active = FALSE WHERE id = $1
          `,
            [schedule.id]
          );
          continue;
        }
      }

      // Job Queue에 추가
      await podcastQueue.add(
        "generate",
        {
          scheduleId: schedule.id,
          userId: schedule.user_id,
          prompt: schedule.prompt,
          email: schedule.email,
        },
        {
          attempts: 3,
          backoff: {
            type: "exponential",
            delay: 5000,
          },
        }
      );

      // 다음 실행 시간 계산 및 업데이트
      const nextRun = calculateNextRun(schedule);
      await db.query(
        `
        UPDATE schedules 
        SET last_run = $1, next_run = $2, updated_at = $1
        WHERE id = $3
      `,
        [now, nextRun, schedule.id]
      );
    } catch (error) {
      console.error(`Failed to queue schedule ${schedule.id}:`, error);
    }
  }
}
```

### 3. 다음 실행 시간 계산

```typescript
function calculateNextRun(schedule: Schedule): Date {
  const { days, time, timezone } = schedule;
  const [hours, minutes] = time.split(":").map(Number);

  // 현재 시간을 사용자 타임존으로 변환
  const nowInTz = new Date().toLocaleString("en-US", { timeZone: timezone });
  const now = new Date(nowInTz);

  const dayMap: Record<DayOfWeek, number> = {
    sunday: 0,
    monday: 1,
    tuesday: 2,
    wednesday: 3,
    thursday: 4,
    friday: 5,
    saturday: 6,
  };

  const scheduleDays = days.map((d) => dayMap[d]).sort((a, b) => a - b);
  const currentDay = now.getDay();
  const currentTime = now.getHours() * 60 + now.getMinutes();
  const scheduleTime = hours * 60 + minutes;

  // 오늘 아직 실행 안 된 스케줄이 있는지 확인
  if (scheduleDays.includes(currentDay) && currentTime < scheduleTime) {
    // 오늘 실행
    const next = new Date(now);
    next.setHours(hours, minutes, 0, 0);
    return convertFromTimezone(next, timezone);
  }

  // 다음 실행 요일 찾기
  let nextDay = scheduleDays.find((d) => d > currentDay);

  if (nextDay === undefined) {
    // 이번 주에 없으면 다음 주 첫 번째 요일
    nextDay = scheduleDays[0];
  }

  const daysUntilNext = (nextDay - currentDay + 7) % 7 || 7;

  const next = new Date(now);
  next.setDate(next.getDate() + daysUntilNext);
  next.setHours(hours, minutes, 0, 0);

  return convertFromTimezone(next, timezone);
}

// 사용자 타임존 시간을 UTC로 변환
function convertFromTimezone(date: Date, timezone: string): Date {
  const options: Intl.DateTimeFormatOptions = {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  };

  const formatter = new Intl.DateTimeFormat("en-CA", options);
  const parts = formatter.formatToParts(date);

  const getPart = (type: string) =>
    parts.find((p) => p.type === type)?.value || "0";

  const localDateStr = `${getPart("year")}-${getPart("month")}-${getPart(
    "day"
  )}T${getPart("hour")}:${getPart("minute")}:${getPart("second")}`;

  // 타임존 오프셋 계산하여 UTC로 변환
  const localDate = new Date(localDateStr);
  const utcDate = new Date(date.getTime() - getTimezoneOffset(timezone, date));

  return utcDate;
}
```

### 4. 팟캐스트 생성 Worker

```typescript
import Queue from "bull";

const podcastQueue = new Queue("podcast-generation", {
  redis: process.env.REDIS_URL,
});

podcastQueue.process("generate", async (job) => {
  const { scheduleId, userId, prompt, email } = job.data;

  // 1. 배치 토큰 확인 및 사용
  const batchToken = await db.query(
    `
    SELECT * FROM batch_tokens 
    WHERE user_id = $1 
      AND tokens_remaining > 0 
      AND valid_until > NOW()
    FOR UPDATE
  `,
    [userId]
  );

  if (!batchToken || batchToken.tokens_remaining <= 0) {
    throw new Error(
      "INSUFFICIENT_BATCH_TOKENS: No batch tokens remaining or expired"
    );
  }

  // 배치 토큰 1개 차감
  await db.query(
    `
    UPDATE batch_tokens 
    SET tokens_remaining = tokens_remaining - 1,
        updated_at = NOW()
    WHERE user_id = $1
  `,
    [userId]
  );

  // 2. 팟캐스트 레코드 생성
  const podcast = await db.query(
    `
    INSERT INTO podcasts (user_id, schedule_id, prompt, status)
    VALUES ($1, $2, $3, 'generating')
    RETURNING *
  `,
    [userId, scheduleId, prompt]
  );

  try {
    // 2. 진행 상태 업데이트 함수
    const updateProgress = async (step: string, progress: number) => {
      await redis.set(
        `podcast:${podcast.id}:status`,
        JSON.stringify({
          step,
          progress,
        })
      );
      job.progress(progress);
    };

    // 3. 프롬프트 분석 (10%)
    await updateProgress("prompting", 10);
    const keywords = await analyzePrompt(prompt);

    // 4. 웹 크롤링 (40%)
    await updateProgress("crawling", 40);
    const articles = await crawlNews(keywords);

    // 5. 요약 및 스크립트 생성 (70%)
    await updateProgress("summarizing", 70);
    const { title, script } = await generateScript(articles, prompt);

    // 6. TTS 오디오 생성 (90%)
    await updateProgress("generating", 90);
    const { audioUrl, duration } = await generateAudio(script);

    // 7. 완료 (100%)
    await updateProgress("completed", 100);

    // 8. DB 업데이트
    await db.query(
      `
      UPDATE podcasts 
      SET title = $1, script = $2, audio_url = $3, 
          duration = $4, status = 'completed', updated_at = NOW()
      WHERE id = $5
    `,
      [title, script, audioUrl, duration, podcast.id]
    );

    // 9. 이메일 발송
    await sendEmail({
      to: email,
      subject: `🎙️ ${title}`,
      template: "podcast-delivery",
      data: {
        title,
        audioUrl,
        scriptSummary: script.substring(0, 300) + "...",
        unsubscribeUrl: `https://dailynewspodcast.com/scheduler`,
      },
    });

    // 10. 상태 캐시 삭제
    await redis.del(`podcast:${podcast.id}:status`);

    return { success: true, podcastId: podcast.id };
  } catch (error) {
    // 실패 처리
    await db.query(
      `
      UPDATE podcasts 
      SET status = 'failed', error_message = $1, updated_at = NOW()
      WHERE id = $2
    `,
      [error.message, podcast.id]
    );

    await redis.del(`podcast:${podcast.id}:status`);

    throw error;
  }
});

// 실패 핸들러
podcastQueue.on("failed", async (job, err) => {
  console.error(`Job ${job.id} failed:`, err);

  // 최대 재시도 후 실패 시 알림
  if (job.attemptsMade >= job.opts.attempts) {
    await sendAdminAlert({
      type: "PODCAST_GENERATION_FAILED",
      jobId: job.id,
      error: err.message,
      data: job.data,
    });
  }
});
```

### 5. 크레딧 리셋 Cron

```typescript
// 매일 자정 실행 (0 0 * * *)
cron.schedule("0 0 * * *", async () => {
  console.log("Resetting expired credits...");

  // 리셋 날짜가 지난 크레딧 리셋
  await db.query(`
    UPDATE credits
    SET generations_used = 0,
        reset_date = reset_date + INTERVAL '1 month',
        updated_at = NOW()
    WHERE reset_date <= CURRENT_DATE
  `);
});
```

---

## Redis 키 구조

```
# 팟캐스트 생성 상태 (TTL: 1시간)
podcast:{podcastId}:status = {
  "step": "crawling",
  "progress": 40
}

# 사용자 세션 (TTL: 7일)
session:{userId} = {
  "token": "jwt...",
  "lastActivity": "2024-01-15T10:00:00Z"
}

# Rate Limiting (TTL: 1분)
ratelimit:{userId}:generate = 3
```

---

## 에러 처리

### 재시도 전략

| 에러 유형             | 재시도 | 대기 시간       |
| --------------------- | ------ | --------------- |
| 네트워크 오류         | 3회    | 5s, 25s, 125s   |
| API Rate Limit        | 3회    | 60s, 120s, 240s |
| 서버 오류 (5xx)       | 3회    | 10s, 30s, 90s   |
| 클라이언트 오류 (4xx) | 0회    | -               |

### Dead Letter Queue

```typescript
// 최대 재시도 후에도 실패한 Job
const deadLetterQueue = new Queue("failed-jobs");

podcastQueue.on("failed", async (job, err) => {
  if (job.attemptsMade >= job.opts.attempts) {
    await deadLetterQueue.add("podcast-generation", {
      originalJob: job.data,
      error: err.message,
      failedAt: new Date(),
    });
  }
});
```

---

## 모니터링

### 메트릭

```typescript
// Prometheus 메트릭 예시
const metrics = {
  // 스케줄 실행 수
  schedulesExecuted: new Counter({
    name: "schedules_executed_total",
    help: "Total number of schedules executed",
  }),

  // 팟캐스트 생성 시간
  podcastGenerationDuration: new Histogram({
    name: "podcast_generation_duration_seconds",
    help: "Duration of podcast generation",
    buckets: [30, 60, 120, 180, 300],
  }),

  // Queue 크기
  queueSize: new Gauge({
    name: "podcast_queue_size",
    help: "Number of jobs in the queue",
  }),
};
```

### 알림 조건

- Queue 크기 > 100: Warning
- 실패율 > 10%: Critical
- 평균 생성 시간 > 5분: Warning
- 크레딧 리셋 실패: Critical

---

## 테스트 체크리스트

- [ ] 스케줄 생성 시 nextRun 계산 정확성
- [ ] 다양한 타임존 테스트
- [ ] 요일 조합별 다음 실행 시간 계산
- [ ] 동시 다발 스케줄 처리
- [ ] 실패 시 재시도 동작
- [ ] 이메일 발송 성공/실패
- [ ] 크레딧 리셋 정확성
- [ ] 플랜 업그레이드 시 스케줄 한도 증가
