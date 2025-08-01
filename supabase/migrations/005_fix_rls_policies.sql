-- Fix RLS policies for drive_scans table
-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own drive scans" ON drive_scans;
DROP POLICY IF EXISTS "Users can insert their own drive scans" ON drive_scans;
DROP POLICY IF EXISTS "Users can update their own drive scans" ON drive_scans;

-- Create proper RLS policies for drive_scans
CREATE POLICY "Users can view their own drive scans" ON drive_scans
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own drive scans" ON drive_scans
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own drive scans" ON drive_scans
  FOR UPDATE USING (auth.uid() = user_id);

-- Add missing policies for drive_files and drive_folders
DROP POLICY IF EXISTS "Users can update their own drive files" ON drive_files;
DROP POLICY IF EXISTS "Users can update their own drive folders" ON drive_folders;

CREATE POLICY "Users can update their own drive files" ON drive_files
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own drive folders" ON drive_folders
  FOR UPDATE USING (auth.uid() = user_id); 