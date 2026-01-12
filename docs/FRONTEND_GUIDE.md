# Daily News Podcast - 프론트엔드 개발 가이드

## 개요

이 문서는 Daily News Podcast API와 연동하는 프론트엔드 개발을 위한 가이드입니다.

---

## 빠른 시작

### 1. Supabase 클라이언트 설정

```bash
npm install @supabase/supabase-js
```

```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

### 2. API 클라이언트 설정

```typescript
// lib/api.ts
import { supabase } from './supabase'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://api.dailynewspod.com/api/v2'

async function getAuthHeaders() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) {
    throw new Error('Not authenticated')
  }
  return {
    'Authorization': `Bearer ${session.access_token}`,
    'Content-Type': 'application/json'
  }
}

export const api = {
  async get<T>(endpoint: string): Promise<T> {
    const headers = await getAuthHeaders()
    const res = await fetch(`${API_BASE}${endpoint}`, { headers })
    const json = await res.json()
    if (!json.success) throw new Error(json.error?.message || 'API Error')
    return json.data
  },
  
  async post<T>(endpoint: string, body?: any): Promise<T> {
    const headers = await getAuthHeaders()
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers,
      body: body ? JSON.stringify(body) : undefined
    })
    const json = await res.json()
    if (!json.success) throw new Error(json.error?.message || 'API Error')
    return json.data
  },
  
  async patch<T>(endpoint: string, body: any): Promise<T> {
    const headers = await getAuthHeaders()
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(body)
    })
    const json = await res.json()
    if (!json.success) throw new Error(json.error?.message || 'API Error')
    return json.data
  },
  
  async delete<T>(endpoint: string): Promise<T> {
    const headers = await getAuthHeaders()
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'DELETE',
      headers
    })
    const json = await res.json()
    if (!json.success) throw new Error(json.error?.message || 'API Error')
    return json.data
  }
}
```

---

## 인증 플로우

### Google 로그인

```typescript
// components/LoginButton.tsx
import { supabase } from '@/lib/supabase'

export function LoginButton() {
  const handleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/callback`
      }
    })
  }
  
  return <button onClick={handleLogin}>Google로 로그인</button>
}
```

### Auth Callback 처리

```typescript
// app/auth/callback/page.tsx (Next.js App Router)
'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { supabase } from '@/lib/supabase'

export default function AuthCallback() {
  const router = useRouter()
  
  useEffect(() => {
    supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session) {
        router.push('/dashboard')
      }
    })
  }, [router])
  
  return <div>로그인 중...</div>
}
```

### Auth Context

```typescript
// contexts/AuthContext.tsx
'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'

interface AuthContextType {
  user: User | null
  session: Session | null
  loading: boolean
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  loading: true,
  signOut: async () => {}
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })
    
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setSession(session)
        setUser(session?.user ?? null)
      }
    )
    
    return () => subscription.unsubscribe()
  }, [])
  
  const signOut = async () => {
    await supabase.auth.signOut()
  }
  
  return (
    <AuthContext.Provider value={{ user, session, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
```

---

## 주요 기능 구현

### 1. 사용자 통계 대시보드

```typescript
// hooks/useUserStats.ts
import useSWR from 'swr'
import { api } from '@/lib/api'

interface UserStats {
  plan_id: string
  subscription_status: string
  generations_used: number
  generations_limit: number
  batch_tokens_remaining: number
  active_schedules: number
  total_podcasts: number
}

export function useUserStats() {
  return useSWR<UserStats>('/users/me/stats', api.get)
}

// components/Dashboard.tsx
import { useUserStats } from '@/hooks/useUserStats'

export function Dashboard() {
  const { data: stats, error, isLoading } = useUserStats()
  
  if (isLoading) return <div>로딩 중...</div>
  if (error) return <div>에러: {error.message}</div>
  
  const creditsRemaining = stats.generations_limit === -1 
    ? '무제한' 
    : `${stats.generations_limit - stats.generations_used}/${stats.generations_limit}`
  
  const batchTokens = stats.batch_tokens_remaining === -1
    ? '무제한'
    : stats.batch_tokens_remaining
  
  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard title="플랜" value={stats.plan_id.toUpperCase()} />
      <StatCard title="크레딧" value={creditsRemaining} />
      <StatCard title="배치 토큰" value={batchTokens} />
      <StatCard title="활성 스케줄" value={stats.active_schedules} />
    </div>
  )
}
```

### 2. 스케줄 관리

```typescript
// hooks/useSchedules.ts
import useSWR from 'swr'
import { api } from '@/lib/api'

interface Schedule {
  id: string
  name: string
  prompt: string
  days: string[]
  time: string
  timezone: string
  email: string
  is_active: boolean
  next_run: string | null
}

export function useSchedules() {
  return useSWR<{ schedules: Schedule[]; total: number }>(
    '/schedules/me',
    api.get
  )
}

// components/ScheduleForm.tsx
import { useState } from 'react'
import { api } from '@/lib/api'
import { mutate } from 'swr'

const DAYS = [
  { value: 'monday', label: '월' },
  { value: 'tuesday', label: '화' },
  { value: 'wednesday', label: '수' },
  { value: 'thursday', label: '목' },
  { value: 'friday', label: '금' },
  { value: 'saturday', label: '토' },
  { value: 'sunday', label: '일' },
]

export function ScheduleForm({ onSuccess }: { onSuccess?: () => void }) {
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    prompt: '',
    days: [] as string[],
    time: '08:00',
    email: '',
  })
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    
    try {
      await api.post('/schedules', formData)
      await mutate('/schedules/me')
      onSuccess?.()
    } catch (error: any) {
      alert(error.message)
    } finally {
      setLoading(false)
    }
  }
  
  const toggleDay = (day: string) => {
    setFormData(prev => ({
      ...prev,
      days: prev.days.includes(day)
        ? prev.days.filter(d => d !== day)
        : [...prev.days, day]
    }))
  }
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="text"
        placeholder="스케줄 이름"
        value={formData.name}
        onChange={e => setFormData(p => ({ ...p, name: e.target.value }))}
      />
      
      <textarea
        placeholder="뉴스 검색 프롬프트 (예: AI 산업 뉴스)"
        value={formData.prompt}
        onChange={e => setFormData(p => ({ ...p, prompt: e.target.value }))}
        required
      />
      
      <div className="flex gap-2">
        {DAYS.map(day => (
          <button
            key={day.value}
            type="button"
            onClick={() => toggleDay(day.value)}
            className={formData.days.includes(day.value) ? 'bg-blue-500' : 'bg-gray-200'}
          >
            {day.label}
          </button>
        ))}
      </div>
      
      <input
        type="time"
        value={formData.time}
        onChange={e => setFormData(p => ({ ...p, time: e.target.value }))}
        required
      />
      
      <input
        type="email"
        placeholder="이메일"
        value={formData.email}
        onChange={e => setFormData(p => ({ ...p, email: e.target.value }))}
        required
      />
      
      <button type="submit" disabled={loading}>
        {loading ? '생성 중...' : '스케줄 생성'}
      </button>
    </form>
  )
}
```

### 3. 팟캐스트 생성 (실시간 상태)

```typescript
// hooks/usePodcastGeneration.ts
import { useState, useCallback, useRef } from 'react'
import { api } from '@/lib/api'

interface GenerationStep {
  id: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
}

interface PodcastStatus {
  id: string
  status: 'pending' | 'generating' | 'completed' | 'failed'
  progress: number
  current_step: string | null
  steps: GenerationStep[]
  error_message: string | null
}

export function usePodcastGeneration() {
  const [status, setStatus] = useState<PodcastStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<NodeJS.Timeout>()
  
  const generate = useCallback(async (prompt: string) => {
    try {
      setError(null)
      setStatus({
        id: '',
        status: 'pending',
        progress: 0,
        current_step: null,
        steps: [],
        error_message: null
      })
      
      // 생성 요청
      const { podcast_id } = await api.post<{ podcast_id: string }>('/podcasts/generate', {
        prompt,
        language: 'ko',
        tts_model: 'gemini'
      })
      
      // 상태 폴링 시작
      const poll = async () => {
        try {
          const statusData = await api.get<PodcastStatus>(`/podcasts/${podcast_id}/status`)
          setStatus(statusData)
          
          if (statusData.status === 'completed' || statusData.status === 'failed') {
            // 폴링 중단
            if (pollRef.current) clearInterval(pollRef.current)
            
            if (statusData.status === 'failed') {
              setError(statusData.error_message || '생성 실패')
            }
            
            return statusData
          }
        } catch (err: any) {
          setError(err.message)
          if (pollRef.current) clearInterval(pollRef.current)
        }
      }
      
      // 3초마다 폴링
      pollRef.current = setInterval(poll, 3000)
      await poll() // 첫 번째 폴링 즉시 실행
      
      return podcast_id
    } catch (err: any) {
      setError(err.message)
      throw err
    }
  }, [])
  
  const reset = useCallback(() => {
    setStatus(null)
    setError(null)
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])
  
  return { status, error, generate, reset }
}

// components/PodcastGenerator.tsx
import { useState } from 'react'
import { usePodcastGeneration } from '@/hooks/usePodcastGeneration'

export function PodcastGenerator() {
  const [prompt, setPrompt] = useState('')
  const { status, error, generate, reset } = usePodcastGeneration()
  
  const handleGenerate = async () => {
    if (!prompt.trim()) return
    await generate(prompt)
  }
  
  const getStepLabel = (stepId: string) => {
    const labels: Record<string, string> = {
      prompting: '프롬프트 분석',
      crawling: '뉴스 수집',
      summarizing: '요약 생성',
      generating: '오디오 생성'
    }
    return labels[stepId] || stepId
  }
  
  return (
    <div className="space-y-4">
      {!status ? (
        <>
          <textarea
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="어떤 뉴스를 팟캐스트로 만들까요?"
            className="w-full p-4 border rounded"
            rows={3}
          />
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim()}
            className="px-6 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
          >
            팟캐스트 생성
          </button>
        </>
      ) : (
        <div className="space-y-4">
          {/* 진행률 바 */}
          <div className="relative h-4 bg-gray-200 rounded overflow-hidden">
            <div
              className="absolute h-full bg-blue-500 transition-all duration-300"
              style={{ width: `${status.progress}%` }}
            />
          </div>
          
          {/* 단계별 상태 */}
          <div className="space-y-2">
            {status.steps.map(step => (
              <div key={step.id} className="flex items-center gap-2">
                <span className={
                  step.status === 'completed' ? 'text-green-500' :
                  step.status === 'in_progress' ? 'text-blue-500 animate-pulse' :
                  step.status === 'failed' ? 'text-red-500' :
                  'text-gray-400'
                }>
                  {step.status === 'completed' ? '✓' :
                   step.status === 'in_progress' ? '●' :
                   step.status === 'failed' ? '✗' : '○'}
                </span>
                <span>{getStepLabel(step.id)}</span>
              </div>
            ))}
          </div>
          
          {/* 완료/에러 */}
          {status.status === 'completed' && (
            <div className="p-4 bg-green-100 rounded">
              <p>✅ 팟캐스트가 생성되었습니다!</p>
              <button onClick={reset} className="mt-2 text-blue-500">
                새로 만들기
              </button>
            </div>
          )}
          
          {error && (
            <div className="p-4 bg-red-100 rounded">
              <p>❌ {error}</p>
              <button onClick={reset} className="mt-2 text-blue-500">
                다시 시도
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

### 4. 결제 (Stripe)

```typescript
// components/PricingCard.tsx
import { useState } from 'react'
import { api } from '@/lib/api'

interface Plan {
  plan_id: string
  name: string
  price_krw: number
  features: string[]
}

export function PricingCard({ plan }: { plan: Plan }) {
  const [loading, setLoading] = useState(false)
  
  const handleSubscribe = async () => {
    if (plan.plan_id === 'free') return
    
    setLoading(true)
    try {
      const { url } = await api.post<{ url: string }>('/payments/stripe/checkout', {
        plan_id: plan.plan_id,
        success_url: `${window.location.origin}/payment/success?session_id={CHECKOUT_SESSION_ID}`,
        cancel_url: `${window.location.origin}/pricing`
      })
      
      // Stripe 결제 페이지로 이동
      window.location.href = url
    } catch (error: any) {
      alert(error.message)
    } finally {
      setLoading(false)
    }
  }
  
  return (
    <div className="border rounded-lg p-6">
      <h3 className="text-xl font-bold">{plan.name}</h3>
      <p className="text-3xl font-bold mt-2">
        {plan.price_krw === 0 ? '무료' : `₩${plan.price_krw.toLocaleString()}/월`}
      </p>
      
      <ul className="mt-4 space-y-2">
        {plan.features.map((feature, i) => (
          <li key={i}>✓ {feature}</li>
        ))}
      </ul>
      
      <button
        onClick={handleSubscribe}
        disabled={loading || plan.plan_id === 'free'}
        className="mt-6 w-full py-2 bg-blue-500 text-white rounded disabled:opacity-50"
      >
        {plan.plan_id === 'free' ? '현재 플랜' : loading ? '처리 중...' : '구독하기'}
      </button>
    </div>
  )
}
```

### 5. 토스페이먼츠 결제

```typescript
// components/TossPayment.tsx
import { useEffect, useRef, useState } from 'react'
import { api } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'

interface TossPaymentProps {
  planId: string
  amount: number
  onSuccess: () => void
  onFail: (error: string) => void
}

export function TossPayment({ planId, amount, onSuccess, onFail }: TossPaymentProps) {
  const { user } = useAuth()
  const paymentRef = useRef<any>(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    // 토스페이먼츠 SDK 로드
    const script = document.createElement('script')
    script.src = 'https://js.tosspayments.com/v1/payment'
    script.onload = () => {
      paymentRef.current = (window as any).TossPayments(
        process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY
      )
      setLoading(false)
    }
    document.head.appendChild(script)
    
    return () => {
      document.head.removeChild(script)
    }
  }, [])
  
  const handlePayment = async () => {
    if (!paymentRef.current || !user) return
    
    const orderId = `${planId}_${user.id}_${Date.now()}`
    
    try {
      await paymentRef.current.requestPayment('카드', {
        amount,
        orderId,
        orderName: `Daily News Podcast - ${planId.toUpperCase()} Plan`,
        customerEmail: user.email,
        successUrl: `${window.location.origin}/payment/toss/success`,
        failUrl: `${window.location.origin}/payment/toss/fail`,
      })
    } catch (error: any) {
      onFail(error.message)
    }
  }
  
  return (
    <button
      onClick={handlePayment}
      disabled={loading}
      className="w-full py-3 bg-blue-600 text-white rounded-lg"
    >
      {loading ? '로딩 중...' : '토스페이먼츠로 결제'}
    </button>
  )
}

// pages/payment/toss/success.tsx
import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { api } from '@/lib/api'

export default function TossSuccessPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState('')
  
  useEffect(() => {
    const confirm = async () => {
      const paymentKey = searchParams.get('paymentKey')
      const orderId = searchParams.get('orderId')
      const amount = searchParams.get('amount')
      
      if (!paymentKey || !orderId || !amount) {
        setStatus('error')
        setError('결제 정보가 없습니다')
        return
      }
      
      try {
        await api.post('/payments/toss/confirm', {
          payment_key: paymentKey,
          order_id: orderId,
          amount: parseInt(amount)
        })
        
        setStatus('success')
        setTimeout(() => router.push('/dashboard'), 2000)
      } catch (err: any) {
        setStatus('error')
        setError(err.message)
      }
    }
    
    confirm()
  }, [searchParams, router])
  
  if (status === 'loading') return <div>결제 확인 중...</div>
  if (status === 'error') return <div>결제 실패: {error}</div>
  
  return (
    <div className="text-center p-8">
      <h1 className="text-2xl font-bold text-green-600">결제 완료!</h1>
      <p className="mt-2">잠시 후 대시보드로 이동합니다...</p>
    </div>
  )
}
```

---

## 환경변수

```bash
# .env.local
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...
NEXT_PUBLIC_API_URL=https://api.dailynewspod.com/api/v2
NEXT_PUBLIC_TOSS_CLIENT_KEY=test_ck_xxx
```

---

## 에러 처리

```typescript
// utils/error-handler.ts
export function handleAPIError(error: any): string {
  const errorMessages: Record<string, string> = {
    'UNAUTHORIZED': '로그인이 필요합니다',
    'FORBIDDEN': '권한이 없습니다',
    'NOT_FOUND': '찾을 수 없습니다',
    'INSUFFICIENT_CREDITS': '크레딧이 부족합니다. 플랜을 업그레이드하세요.',
    'INSUFFICIENT_BATCH_TOKENS': '배치 토큰이 부족합니다.',
    'SCHEDULE_LIMIT_EXCEEDED': '스케줄 한도를 초과했습니다.',
    'PAYMENT_FAILED': '결제에 실패했습니다.',
    'RATE_LIMIT_EXCEEDED': '요청이 너무 많습니다. 잠시 후 다시 시도하세요.',
  }
  
  const code = error?.code || error?.response?.data?.error?.code
  return errorMessages[code] || error.message || '오류가 발생했습니다'
}
```

---

## 참고 문서

- [API 명세서](./BACKEND_SPEC.md) - 전체 API 문서
- [스케줄러 플로우](./SCHEDULER_FLOW.md) - 스케줄 시스템 상세
- [Supabase Auth 문서](https://supabase.com/docs/guides/auth)
- [토스페이먼츠 문서](https://docs.tosspayments.com)
