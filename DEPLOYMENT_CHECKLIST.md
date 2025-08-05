# 🚀 Railway Deployment Checklist

## Pre-Deployment Steps

### 1. Environment Variables Setup
Make sure you have these environment variables ready:

```bash
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# API Configuration
FRONTEND_URL=https://your-app.vercel.app
```

### 2. Database Migration
```bash
# Deploy Supabase migrations
supabase db push
```

### 3. Google OAuth Configuration
Update your Google Cloud Console OAuth 2.0 client with:
- **Authorized redirect URIs**: `https://your-backend.railway.app/api/google/callback`
- **Authorized JavaScript origins**: `https://your-backend.railway.app`

## Deployment Steps

### 1. Install Railway CLI
```bash
npm install -g @railway/cli
```

### 2. Login to Railway
```bash
railway login
```

### 3. Initialize Railway Project
```bash
cd /Users/anantsomani/Drive_Organizer
railway init
```

### 4. Set Environment Variables
```bash
railway variables set SUPABASE_URL=your_supabase_url
railway variables set SUPABASE_ANON_KEY=your_supabase_anon_key
railway variables set GOOGLE_CLIENT_ID=your_google_client_id
railway variables set GOOGLE_CLIENT_SECRET=your_google_client_secret
railway variables set OPENAI_API_KEY=your_openai_api_key
railway variables set FRONTEND_URL=https://your-app.vercel.app
```

### 5. Deploy
```bash
railway up
```

### 6. Get Your Backend URL
```bash
railway domain
```

## Post-Deployment Verification

### 1. Health Check
```bash
curl https://your-backend.railway.app/health
```

### 2. Test API Endpoints
```bash
# Test authentication
curl -X POST https://your-backend.railway.app/api/google/store-token \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"access_token":"test","refresh_token":"test","expires_at":1234567890}'
```

### 3. Check Logs
```bash
railway logs
```

## Troubleshooting

### Common Issues:
1. **Environment variables not set**: Check Railway dashboard
2. **Database connection failed**: Verify Supabase credentials
3. **CORS errors**: Update CORS configuration in main.py
4. **Port issues**: Railway automatically sets PORT environment variable

### Debug Commands:
```bash
# View logs
railway logs

# Check environment variables
railway variables

# Restart service
railway service restart

# View service status
railway status
```

## Next Steps After Backend Deployment

1. **Deploy Frontend to Vercel**
2. **Update Frontend Environment Variables**
3. **Test Full Integration**
4. **Set Up Monitoring**

## Cost Estimation
- **Railway**: $5-20/month (depending on usage)
- **Supabase**: $0-25/month (depending on usage)
- **OpenAI**: $0.01-5/month (depending on usage) 