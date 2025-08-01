# Deployment Guide

This guide covers deploying the Drive Organizer application to production.

## Prerequisites

1. **Supabase Project**: Create a new project at [supabase.com](https://supabase.com)
2. **Google Cloud Project**: Set up OAuth 2.0 credentials for Google Drive API
3. **OpenAI API Key**: Get an API key from [platform.openai.com](https://platform.openai.com)
4. **Vercel Account**: For frontend deployment
5. **Railway Account**: For backend deployment

## 1. Supabase Setup

### Create Project
1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note down your project URL and anon key

### Configure Authentication
1. In Supabase Dashboard, go to Authentication > Providers
2. Enable Google provider
3. Add your Google OAuth credentials
4. Configure redirect URLs:
   - `https://your-vercel-domain.vercel.app/auth/callback`
   - `http://localhost:3000/auth/callback` (for development)

### Run Database Migrations
```bash
# Install Supabase CLI
npm install -g supabase

# Link your project
supabase link --project-ref your-project-ref

# Push migrations
supabase db push
```

## 2. Google Cloud Setup

### Enable APIs
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable Google Drive API v3
3. Create OAuth 2.0 credentials
4. Add authorized redirect URIs:
   - `https://your-supabase-project.supabase.co/auth/v1/callback`
   - `http://localhost:3000/auth/callback`

### Configure Scopes
Ensure your OAuth consent screen includes:
- `https://www.googleapis.com/auth/drive.metadata.readonly`
- `https://www.googleapis.com/auth/drive.file`

## 3. Frontend Deployment (Vercel)

### Connect Repository
1. Go to [vercel.com](https://vercel.com)
2. Import your GitHub repository
3. Configure build settings:
   - Framework Preset: Next.js
   - Root Directory: `apps/web`
   - Build Command: `cd ../.. && pnpm build:web`
   - Output Directory: `.next`

### Environment Variables
Add the following environment variables in Vercel:
```
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
NEXT_PUBLIC_API_URL=https://your-railway-app.railway.app
```

### Deploy
1. Push to main branch
2. Vercel will automatically deploy
3. Note your production URL

## 4. Backend Deployment (Railway)

### Connect Repository
1. Go to [railway.app](https://railway.app)
2. Create new project from GitHub
3. Select your repository
4. Configure service:
   - Root Directory: `apps/api`
   - Build Command: `poetry install`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Environment Variables
Add the following environment variables in Railway:
```
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
OPENAI_API_KEY=your_openai_api_key
```

### Deploy
1. Railway will automatically deploy on push to main
2. Note your production URL
3. Update the `NEXT_PUBLIC_API_URL` in Vercel with this URL

## 5. Final Configuration

### Update Redirect URLs
1. In Supabase, update the redirect URL to use your production Vercel domain
2. In Google Cloud Console, update OAuth redirect URIs

### Test Deployment
1. Visit your Vercel URL
2. Test the complete workflow:
   - Sign in with Google
   - Start metadata ingestion
   - Generate AI proposal
   - Apply structure
   - Test undo functionality

## 6. Monitoring & Maintenance

### Logs
- **Frontend**: View logs in Vercel dashboard
- **Backend**: View logs in Railway dashboard
- **Database**: Monitor in Supabase dashboard

### Performance
- Monitor API response times
- Track OpenAI API usage and costs
- Monitor Google Drive API quotas

### Security
- Regularly rotate API keys
- Monitor for suspicious activity
- Keep dependencies updated

## Troubleshooting

### Common Issues

1. **CORS Errors**: Ensure `NEXT_PUBLIC_API_URL` is correctly set
2. **Authentication Failures**: Check redirect URLs in Supabase and Google Cloud
3. **API Errors**: Verify all environment variables are set correctly
4. **Build Failures**: Check that all dependencies are properly installed

### Support
- Check the logs in respective dashboards
- Review the test suite for expected behavior
- Consult the API documentation for endpoint details 