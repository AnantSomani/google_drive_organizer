#!/bin/bash

set -e

echo "🚀 Provisioning infrastructure for Drive Organizer..."

# Check if required tools are installed
command -v supabase >/dev/null 2>&1 || { echo "❌ Supabase CLI is required but not installed. Visit: https://supabase.com/docs/guides/cli"; exit 1; }
command -v vercel >/dev/null 2>&1 || { echo "❌ Vercel CLI is required but not installed. Run: npm i -g vercel"; exit 1; }
command -v railway >/dev/null 2>&1 || { echo "❌ Railway CLI is required but not installed. Visit: https://docs.railway.app/develop/cli"; exit 1; }

# Initialize Supabase project
echo "📦 Setting up Supabase project..."
if [ ! -d ".supabase" ]; then
    supabase init
fi

# Start Supabase locally for development
echo "🏠 Starting Supabase locally..."
supabase start

# Get Supabase credentials
SUPABASE_URL=$(supabase status --output json | jq -r '.api.url')
SUPABASE_ANON_KEY=$(supabase status --output json | jq -r '.api.anon_key')

echo "✅ Supabase URL: $SUPABASE_URL"
echo "✅ Supabase Anon Key: $SUPABASE_ANON_KEY"

# Create .env file with Supabase credentials
cat > .env << EOF
# Supabase
SUPABASE_URL=$SUPABASE_URL
SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY

# Google OAuth (to be configured)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# OpenAI (to be configured)
OPENAI_API_KEY=

# API Configuration
API_URL=http://localhost:3030
EOF

echo "📝 Created .env file with Supabase credentials"
echo "⚠️  Please configure Google OAuth and OpenAI API keys in .env"

# Initialize Vercel project (if not already done)
echo "🌐 Setting up Vercel project..."
if [ ! -f ".vercel/project.json" ]; then
    vercel --yes
fi

# Initialize Railway project (if not already done)
echo "🚂 Setting up Railway project..."
if [ ! -f ".railway/project.json" ]; then
    railway login
    railway init
fi

echo "✅ Infrastructure provisioning complete!"
echo ""
echo "Next steps:"
echo "1. Configure Google OAuth credentials in .env"
echo "2. Add OpenAI API key to .env"
echo "3. Run 'pnpm setup' to install dependencies"
echo "4. Run 'pnpm dev' to start development servers" 