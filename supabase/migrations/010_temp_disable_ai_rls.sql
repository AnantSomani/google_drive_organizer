-- Temporarily disable RLS for AI tables during development
-- This allows the backend to insert data without authentication issues
ALTER TABLE ai_analyses DISABLE ROW LEVEL SECURITY;
ALTER TABLE ai_proposals DISABLE ROW LEVEL SECURITY;

-- Note: This is for development only. In production, you should:
-- 1. Use SUPABASE_SERVICE_ROLE_KEY in your backend
-- 2. Re-enable RLS with proper policies
-- 3. Use the service role key for backend operations 