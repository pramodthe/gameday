-- Preserve the previous ReadyRoom schema while installing GameDay Mirror.

DO $$
BEGIN
  IF to_regclass('public.streaks') IS NOT NULL
    AND to_regclass('public.readyroom_streaks_legacy') IS NULL
    AND EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'streaks'
        AND column_name = 'athlete_id'
    )
  THEN
    ALTER TABLE public.streaks RENAME TO readyroom_streaks_legacy;
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.athlete_profiles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id text NOT NULL,
  display_name text NOT NULL,
  sport text,
  primary_goal text,
  timezone text NOT NULL DEFAULT 'America/Los_Angeles',
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT athlete_profiles_user_unique UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS public.checkin_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  athlete_profile_id uuid NOT NULL REFERENCES public.athlete_profiles (id) ON DELETE CASCADE,
  livekit_room_name text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'complete', 'abandoned')),
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  demo_mode boolean NOT NULL DEFAULT false,
  CONSTRAINT checkin_sessions_room_unique UNIQUE (livekit_room_name)
);

CREATE TABLE IF NOT EXISTS public.checkin_answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.checkin_sessions (id) ON DELETE CASCADE,
  category text NOT NULL,
  transcript text NOT NULL,
  normalized_value numeric,
  unit text,
  confidence numeric CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT checkin_answers_session_category_unique UNIQUE (session_id, category)
);

CREATE TABLE IF NOT EXISTS public.daily_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.checkin_sessions (id) ON DELETE CASCADE,
  metric_key text NOT NULL,
  metric_value numeric,
  display_value text NOT NULL,
  status text NOT NULL CHECK (status IN ('neutral', 'good', 'attention', 'risk')),
  source_answer_id uuid REFERENCES public.checkin_answers (id) ON DELETE SET NULL,
  CONSTRAINT daily_metrics_session_key_unique UNIQUE (session_id, metric_key)
);

CREATE TABLE IF NOT EXISTS public.daily_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.checkin_sessions (id) ON DELETE CASCADE,
  actions_json jsonb NOT NULL DEFAULT '[]',
  memory_sources_json jsonb NOT NULL DEFAULT '[]',
  safety_status text NOT NULL DEFAULT 'rules_checked',
  accepted_at timestamptz,
  CONSTRAINT daily_plans_session_unique UNIQUE (session_id)
);

CREATE TABLE IF NOT EXISTS public.streaks (
  athlete_profile_id uuid PRIMARY KEY REFERENCES public.athlete_profiles (id) ON DELETE CASCADE,
  current_days integer NOT NULL DEFAULT 0,
  longest_days integer NOT NULL DEFAULT 0,
  last_completed_date date
);

CREATE INDEX IF NOT EXISTS idx_checkin_sessions_athlete
  ON public.checkin_sessions (athlete_profile_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkin_answers_session
  ON public.checkin_answers (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_session
  ON public.daily_metrics (session_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  public.athlete_profiles,
  public.checkin_sessions,
  public.checkin_answers,
  public.daily_metrics,
  public.daily_plans,
  public.streaks
TO authenticated;

ALTER TABLE public.athlete_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.checkin_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.checkin_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.streaks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS athlete_profiles_own ON public.athlete_profiles;
CREATE POLICY athlete_profiles_own ON public.athlete_profiles
  FOR ALL TO authenticated
  USING (user_id = auth.uid()::text)
  WITH CHECK (user_id = auth.uid()::text);

DROP POLICY IF EXISTS checkin_sessions_own ON public.checkin_sessions;
CREATE POLICY checkin_sessions_own ON public.checkin_sessions
  FOR ALL TO authenticated
  USING (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ))
  WITH CHECK (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ));

DROP POLICY IF EXISTS checkin_answers_own ON public.checkin_answers;
CREATE POLICY checkin_answers_own ON public.checkin_answers
  FOR ALL TO authenticated
  USING (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ))
  WITH CHECK (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ));

DROP POLICY IF EXISTS daily_metrics_own ON public.daily_metrics;
CREATE POLICY daily_metrics_own ON public.daily_metrics
  FOR ALL TO authenticated
  USING (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ))
  WITH CHECK (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ));

DROP POLICY IF EXISTS daily_plans_own ON public.daily_plans;
CREATE POLICY daily_plans_own ON public.daily_plans
  FOR ALL TO authenticated
  USING (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ))
  WITH CHECK (session_id IN (
    SELECT session.id
    FROM public.checkin_sessions AS session
    JOIN public.athlete_profiles AS athlete ON athlete.id = session.athlete_profile_id
    WHERE athlete.user_id = auth.uid()::text
  ));

DROP POLICY IF EXISTS streaks_own ON public.streaks;
CREATE POLICY streaks_own ON public.streaks
  FOR ALL TO authenticated
  USING (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ))
  WITH CHECK (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ));
