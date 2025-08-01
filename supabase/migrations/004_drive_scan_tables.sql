-- Drop existing tables if they exist
DROP TABLE IF EXISTS drive_scans CASCADE;
DROP TABLE IF EXISTS drive_files CASCADE;
DROP TABLE IF EXISTS drive_folders CASCADE;

-- Drive scan tracking
CREATE TABLE drive_scans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  status text CHECK (status IN ('pending', 'processing', 'completed', 'error')) DEFAULT 'pending',
  include_folders boolean DEFAULT true,
  include_files boolean DEFAULT true,
  max_results integer DEFAULT 1000,
  file_count integer DEFAULT 0,
  folder_count integer DEFAULT 0,
  error_message text,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  created_at timestamptz DEFAULT now()
);

-- Drive files storage
CREATE TABLE drive_files (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id uuid REFERENCES drive_scans(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  files jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Drive folders storage
CREATE TABLE drive_folders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scan_id uuid REFERENCES drive_scans(id) ON DELETE CASCADE,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  folders jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Create indexes for better performance
CREATE INDEX idx_drive_scans_user_id ON drive_scans(user_id);
CREATE INDEX idx_drive_scans_status ON drive_scans(status);
CREATE INDEX idx_drive_files_scan_id ON drive_files(scan_id);
CREATE INDEX idx_drive_files_user_id ON drive_files(user_id);
CREATE INDEX idx_drive_folders_scan_id ON drive_folders(scan_id);
CREATE INDEX idx_drive_folders_user_id ON drive_folders(user_id);

-- Enable Row Level Security
ALTER TABLE drive_scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE drive_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE drive_folders ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view their own drive scans" ON drive_scans
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own drive scans" ON drive_scans
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own drive scans" ON drive_scans
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can view their own drive files" ON drive_files
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own drive files" ON drive_files
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own drive folders" ON drive_folders
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own drive folders" ON drive_folders
  FOR INSERT WITH CHECK (auth.uid() = user_id); 