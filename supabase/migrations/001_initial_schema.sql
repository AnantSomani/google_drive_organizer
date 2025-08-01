-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
CREATE TYPE proposal_status AS ENUM ('draft', 'applied', 'reverted');
CREATE TYPE ingestion_status AS ENUM ('pending', 'processing', 'done', 'error');

-- Preferences table for user settings
CREATE TABLE preferences (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  ignore_mime text[] DEFAULT '{}',
  ignore_large boolean DEFAULT false,
  max_file_size_mb integer DEFAULT 100,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Raw metadata storage for Drive files
CREATE TABLE metadata_raw (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  snapshot_id uuid NOT NULL,
  file_metadata jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Session proposals for AI-generated folder structures
CREATE TABLE session_proposals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  snapshot_id uuid NOT NULL,
  proposal jsonb NOT NULL,
  status proposal_status DEFAULT 'draft',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Undo logs for tracking changes
CREATE TABLE undo_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  session_proposal_id uuid REFERENCES session_proposals(id) ON DELETE CASCADE,
  performed_at timestamptz DEFAULT now(),
  changes jsonb NOT NULL,
  reverted_at timestamptz,
  reverted boolean DEFAULT false
);

-- Ingestion status tracking
CREATE TABLE ingestion_status (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  status ingestion_status DEFAULT 'pending',
  total_files integer DEFAULT 0,
  processed_files integer DEFAULT 0,
  error_message text,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  created_at timestamptz DEFAULT now()
);

-- Create indexes for better performance
CREATE INDEX idx_metadata_raw_user_id ON metadata_raw(user_id);
CREATE INDEX idx_metadata_raw_snapshot_id ON metadata_raw(snapshot_id);
CREATE INDEX idx_session_proposals_user_id ON session_proposals(user_id);
CREATE INDEX idx_session_proposals_snapshot_id ON session_proposals(snapshot_id);
CREATE INDEX idx_undo_logs_user_id ON undo_logs(user_id);
CREATE INDEX idx_undo_logs_session_proposal_id ON undo_logs(session_proposal_id);
CREATE INDEX idx_ingestion_status_user_id ON ingestion_status(user_id);

-- Enable Row Level Security (RLS)
ALTER TABLE preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE metadata_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE undo_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_status ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY "Users can view own preferences" ON preferences
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences" ON preferences
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences" ON preferences
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own metadata" ON metadata_raw
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own metadata" ON metadata_raw
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own proposals" ON session_proposals
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own proposals" ON session_proposals
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own proposals" ON session_proposals
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own undo logs" ON undo_logs
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own undo logs" ON undo_logs
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own undo logs" ON undo_logs
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can view own ingestion status" ON ingestion_status
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own ingestion status" ON ingestion_status
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own ingestion status" ON ingestion_status
  FOR UPDATE USING (auth.uid() = user_id);

-- Create functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_preferences_updated_at BEFORE UPDATE ON preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_proposals_updated_at BEFORE UPDATE ON session_proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column(); 