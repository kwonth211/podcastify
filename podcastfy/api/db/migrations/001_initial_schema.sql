-- ============================================================================
-- Daily News Podcast - Initial Database Schema
-- Run this migration in your Supabase SQL Editor
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ENUM Types
-- ============================================================================

CREATE TYPE subscription_status AS ENUM ('active', 'canceled', 'past_due', 'trialing', 'unpaid');
CREATE TYPE plan_type AS ENUM ('free', 'basic', 'pro');
CREATE TYPE day_of_week AS ENUM ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday');
CREATE TYPE podcast_status AS ENUM ('pending', 'generating', 'completed', 'failed');
CREATE TYPE payment_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'canceled', 'refunded');
CREATE TYPE payment_provider AS ENUM ('stripe', 'toss');

-- ============================================================================
-- Users Table
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    google_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    picture TEXT,
    auth_provider VARCHAR(50) DEFAULT 'google',
    supabase_auth_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_supabase_auth_id ON users(supabase_auth_id);

-- ============================================================================
-- Subscriptions Table
-- ============================================================================

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id plan_type NOT NULL DEFAULT 'free',
    status subscription_status NOT NULL DEFAULT 'active',
    current_period_start TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_period_end TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    stripe_subscription_id VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    toss_subscription_id VARCHAR(255),
    toss_customer_key VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_subscription UNIQUE (user_id)
);

CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_plan_id ON subscriptions(plan_id);

-- ============================================================================
-- Credits Table (for on-demand generations)
-- ============================================================================

CREATE TABLE credits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    generations_used INTEGER NOT NULL DEFAULT 0,
    generations_limit INTEGER NOT NULL DEFAULT 1,
    reset_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_credits UNIQUE (user_id)
);

CREATE INDEX idx_credits_user_id ON credits(user_id);
CREATE INDEX idx_credits_reset_date ON credits(reset_date);

-- ============================================================================
-- Batch Tokens Table (for scheduled generations)
-- ============================================================================

CREATE TABLE batch_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tokens_remaining INTEGER NOT NULL DEFAULT 0,
    tokens_total INTEGER NOT NULL DEFAULT 0,
    valid_until TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '7 days'),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_user_batch_tokens UNIQUE (user_id)
);

CREATE INDEX idx_batch_tokens_user_id ON batch_tokens(user_id);
CREATE INDEX idx_batch_tokens_valid_until ON batch_tokens(valid_until);

-- ============================================================================
-- Schedules Table
-- ============================================================================

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
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_schedules_user_id ON schedules(user_id);
CREATE INDEX idx_schedules_next_run ON schedules(next_run) WHERE is_active = TRUE;
CREATE INDEX idx_schedules_is_active ON schedules(is_active);

-- ============================================================================
-- Podcasts Table
-- ============================================================================

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
    duration INTEGER, -- seconds
    file_size INTEGER, -- bytes
    status podcast_status NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    current_step VARCHAR(50),
    play_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_podcasts_user_id ON podcasts(user_id);
CREATE INDEX idx_podcasts_schedule_id ON podcasts(schedule_id);
CREATE INDEX idx_podcasts_status ON podcasts(status);
CREATE INDEX idx_podcasts_created_at ON podcasts(created_at DESC);

-- ============================================================================
-- Payments Table
-- ============================================================================

CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id plan_type NOT NULL,
    amount INTEGER NOT NULL, -- cents or won
    currency VARCHAR(3) NOT NULL DEFAULT 'KRW', -- USD, KRW
    provider payment_provider NOT NULL,
    provider_payment_id VARCHAR(255),
    provider_order_id VARCHAR(255),
    status payment_status NOT NULL DEFAULT 'pending',
    description TEXT,
    metadata JSONB DEFAULT '{}',
    paid_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at DESC);
CREATE INDEX idx_payments_provider_payment_id ON payments(provider_payment_id);

-- ============================================================================
-- Scheduler Jobs Table (for tracking scheduled job execution)
-- ============================================================================

CREATE TABLE scheduler_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    schedule_id UUID NOT NULL REFERENCES schedules(id) ON DELETE CASCADE,
    podcast_id UUID REFERENCES podcasts(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued', -- queued, processing, completed, failed
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scheduler_jobs_schedule_id ON scheduler_jobs(schedule_id);
CREATE INDEX idx_scheduler_jobs_status ON scheduler_jobs(status);
CREATE INDEX idx_scheduler_jobs_created_at ON scheduler_jobs(created_at DESC);

-- ============================================================================
-- Updated At Trigger Function
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all relevant tables
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_credits_updated_at
    BEFORE UPDATE ON credits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_batch_tokens_updated_at
    BEFORE UPDATE ON batch_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schedules_updated_at
    BEFORE UPDATE ON schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_podcasts_updated_at
    BEFORE UPDATE ON podcasts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Row Level Security (RLS) Policies
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE podcasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_jobs ENABLE ROW LEVEL SECURITY;

-- Users: Users can only see and update their own data
CREATE POLICY "Users can view own data" ON users
    FOR SELECT USING (auth.uid() = supabase_auth_id);

CREATE POLICY "Users can update own data" ON users
    FOR UPDATE USING (auth.uid() = supabase_auth_id);

-- Subscriptions: Users can only view their own subscriptions
CREATE POLICY "Users can view own subscriptions" ON subscriptions
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Credits: Users can only view their own credits
CREATE POLICY "Users can view own credits" ON credits
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Batch Tokens: Users can only view their own batch tokens
CREATE POLICY "Users can view own batch_tokens" ON batch_tokens
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Schedules: Users can CRUD their own schedules
CREATE POLICY "Users can view own schedules" ON schedules
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can insert own schedules" ON schedules
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can update own schedules" ON schedules
    FOR UPDATE USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can delete own schedules" ON schedules
    FOR DELETE USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Podcasts: Users can CRUD their own podcasts
CREATE POLICY "Users can view own podcasts" ON podcasts
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can insert own podcasts" ON podcasts
    FOR INSERT WITH CHECK (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can update own podcasts" ON podcasts
    FOR UPDATE USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

CREATE POLICY "Users can delete own podcasts" ON podcasts
    FOR DELETE USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Payments: Users can only view their own payments
CREATE POLICY "Users can view own payments" ON payments
    FOR SELECT USING (
        user_id IN (SELECT id FROM users WHERE supabase_auth_id = auth.uid())
    );

-- Scheduler Jobs: Users can view jobs for their schedules
CREATE POLICY "Users can view own scheduler_jobs" ON scheduler_jobs
    FOR SELECT USING (
        schedule_id IN (
            SELECT s.id FROM schedules s
            JOIN users u ON s.user_id = u.id
            WHERE u.supabase_auth_id = auth.uid()
        )
    );

-- ============================================================================
-- Service Role Policies (for backend operations)
-- ============================================================================

-- These policies allow the service role (backend) to perform all operations
CREATE POLICY "Service role full access to users" ON users
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to subscriptions" ON subscriptions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to credits" ON credits
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to batch_tokens" ON batch_tokens
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to schedules" ON schedules
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to podcasts" ON podcasts
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to payments" ON payments
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to scheduler_jobs" ON scheduler_jobs
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function to create default subscription and credits for new users
CREATE OR REPLACE FUNCTION create_user_defaults()
RETURNS TRIGGER AS $$
BEGIN
    -- Create free subscription
    INSERT INTO subscriptions (user_id, plan_id, status)
    VALUES (NEW.id, 'free', 'active');
    
    -- Create default credits (1 free generation per month)
    INSERT INTO credits (user_id, generations_limit, reset_date)
    VALUES (NEW.id, 1, CURRENT_TIMESTAMP + INTERVAL '30 days');
    
    -- Create batch tokens (7 tokens for 7 days for free plan)
    INSERT INTO batch_tokens (user_id, tokens_remaining, tokens_total, valid_until)
    VALUES (NEW.id, 7, 7, CURRENT_TIMESTAMP + INTERVAL '7 days');
    
    RETURN NEW;
END;
$$ language 'plpgsql' SECURITY DEFINER;

CREATE TRIGGER on_user_created
    AFTER INSERT ON users
    FOR EACH ROW EXECUTE FUNCTION create_user_defaults();

-- Function to handle user signup from Supabase Auth
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO users (supabase_auth_id, email, name, picture, google_id)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'avatar_url',
        NEW.raw_user_meta_data->>'provider_id'
    )
    ON CONFLICT (supabase_auth_id) DO UPDATE SET
        email = EXCLUDED.email,
        name = COALESCE(EXCLUDED.name, users.name),
        picture = COALESCE(EXCLUDED.picture, users.picture),
        google_id = COALESCE(EXCLUDED.google_id, users.google_id),
        updated_at = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ language 'plpgsql' SECURITY DEFINER;

-- Trigger on auth.users to create application user
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ============================================================================
-- Plan Configuration View
-- ============================================================================

CREATE OR REPLACE VIEW plan_features AS
SELECT 
    'free'::plan_type as plan_id,
    'Free' as name,
    0 as price_usd,
    0 as price_krw,
    1 as generations_per_month,
    true as scheduler_enabled,
    -1 as max_schedules,
    false as premium_voices,
    false as priority_crawling,
    false as rss_feed,
    7 as batch_tokens,
    7 as batch_token_validity_days
UNION ALL
SELECT 
    'basic'::plan_type,
    'Basic',
    100,
    1500,
    3,
    true,
    -1,
    false,
    false,
    false,
    30,
    30
UNION ALL
SELECT 
    'pro'::plan_type,
    'Pro',
    1000,
    15000,
    -1,
    true,
    -1,
    true,
    true,
    true,
    -1,
    -1;

-- ============================================================================
-- Useful Queries for Admin Dashboard
-- ============================================================================

-- View for user statistics
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
