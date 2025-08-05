#!/bin/bash

# Railway Deployment Script for Drive Organizer
set -e

echo "🚀 Starting Railway deployment for Drive Organizer..."

# Check if Railway CLI is available via npx
if ! npx @railway/cli --version &> /dev/null; then
    echo "❌ Railway CLI not found. Installing..."
    npm install -g @railway/cli
fi

# Check if user is logged in
if ! npx @railway/cli whoami &> /dev/null; then
    echo "🔐 Please login to Railway..."
    npx @railway/cli login
fi

# Initialize Railway project if not already done
if [ ! -f ".railway" ]; then
    echo "📁 Initializing Railway project..."
    npx @railway/cli init
fi

echo "📦 Deploying to Railway..."
npx @railway/cli up

echo "🌐 Getting deployment URL..."
npx @railway/cli domain

echo "✅ Deployment completed!"
echo ""
echo "📋 Next steps:"
echo "1. Set environment variables in Railway dashboard"
echo "2. Test the health endpoint: curl https://your-backend.railway.app/health"
echo "3. Deploy frontend to Vercel"
echo "4. Update frontend environment variables"
echo ""
echo "🔧 To view logs: npx @railway/cli logs"
echo "🔧 To check status: npx @railway/cli status" 