#!/bin/bash

# TL;DW Vercel Deployment Script

echo "🚀 Deploying TL;DW to Vercel..."

# Check if vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "❌ Vercel CLI not found. Installing..."
    npm install -g vercel
fi

# Check if user is logged in
if ! vercel whoami &> /dev/null; then
    echo "🔐 Please log in to Vercel..."
    vercel login
fi

# Deploy to production
echo "📦 Deploying to production..."
vercel --prod

echo "✅ Deployment complete!"
echo ""
echo "🔧 Don't forget to:"
echo "1. Set up environment variables in Vercel dashboard"
echo "2. Configure your PostgreSQL database"
echo "3. Set up Google OAuth credentials"
echo "4. Add your OpenAI API key"
echo ""
echo "📚 See DEPLOYMENT.md for detailed instructions"