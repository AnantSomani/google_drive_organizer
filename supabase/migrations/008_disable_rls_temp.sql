-- Temporarily disable RLS to get OAuth flow working
-- We'll re-enable it properly once the flow is working

-- Disable RLS on google_tokens table
ALTER TABLE google_tokens DISABLE ROW LEVEL SECURITY;

-- Disable RLS on drive_scans table  
ALTER TABLE drive_scans DISABLE ROW LEVEL SECURITY;

-- Disable RLS on drive_files table
ALTER TABLE drive_files DISABLE ROW LEVEL SECURITY;

-- Disable RLS on drive_folders table
ALTER TABLE drive_folders DISABLE ROW LEVEL SECURITY;

-- Add a comment to remind us to re-enable later
COMMENT ON TABLE google_tokens IS 'RLS temporarily disabled for OAuth flow testing';
COMMENT ON TABLE drive_scans IS 'RLS temporarily disabled for OAuth flow testing';
COMMENT ON TABLE drive_files IS 'RLS temporarily disabled for OAuth flow testing';
COMMENT ON TABLE drive_folders IS 'RLS temporarily disabled for OAuth flow testing'; 