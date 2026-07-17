CREATE TABLE IF NOT EXISTS public.movement_analyses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES public.checkin_sessions (id) ON DELETE CASCADE,
  athlete_profile_id uuid NOT NULL REFERENCES public.athlete_profiles (id) ON DELETE CASCADE,
  movement text NOT NULL DEFAULT 'squat',
  reps integer NOT NULL DEFAULT 0 CHECK (reps >= 0),
  score integer NOT NULL CHECK (score >= 0 AND score <= 100),
  confidence numeric CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  pose_metrics jsonb NOT NULL DEFAULT '{}',
  feedback jsonb NOT NULL DEFAULT '{}',
  source text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_movement_analyses_athlete
  ON public.movement_analyses (athlete_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_movement_analyses_session
  ON public.movement_analyses (session_id, created_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.movement_analyses TO authenticated;

ALTER TABLE public.movement_analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS movement_analyses_own ON public.movement_analyses;
CREATE POLICY movement_analyses_own ON public.movement_analyses
  FOR ALL TO authenticated
  USING (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ))
  WITH CHECK (athlete_profile_id IN (
    SELECT id FROM public.athlete_profiles WHERE user_id = auth.uid()::text
  ));
