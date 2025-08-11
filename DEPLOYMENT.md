# TL;DW Vercel Deployment Guide

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Push your code to GitHub
3. **Environment Variables**: Prepare the required environment variables

## Required Environment Variables

Set these in your Vercel dashboard under Project Settings > Environment Variables:

### Required Variables
```
SESSION_SECRET=your-super-secret-session-key-here
GOOGLE_OAUTH_CLIENT_ID=your-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=your-postgresql-database-url
```

### Optional Variables
```
FLASK_ENV=production
PYTHONPATH=/var/task
```

## Database Setup

Since Vercel doesn't support SQLite in production, you'll need a PostgreSQL database:

### Option 1: Vercel Postgres (Recommended)
1. Go to your Vercel dashboard
2. Navigate to Storage tab
3. Create a new Postgres database
4. Copy the DATABASE_URL to your environment variables

### Option 2: External PostgreSQL
Use services like:
- **Supabase** (free tier available)
- **Railway** (free tier available)
- **PlanetScale** (MySQL alternative)
- **Heroku Postgres** (paid)

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Add your Vercel domain to authorized redirect URIs:
   ```
   https://your-app-name.vercel.app/auth/callback
   ```

## OpenAI API Setup

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Create an API key
3. Add it to your Vercel environment variables

## Deployment Steps

### Method 1: Vercel CLI (Recommended)
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

### Method 2: GitHub Integration
1. Connect your GitHub repository to Vercel
2. Vercel will automatically deploy on every push to main branch
3. Set up environment variables in Vercel dashboard

## Post-Deployment

1. **Test the application**: Visit your Vercel URL
2. **Check logs**: Use `vercel logs` or Vercel dashboard
3. **Monitor performance**: Watch for any timeout issues
4. **Test OAuth flow**: Ensure Google login works
5. **Test Watch Later fix**: Verify the playlist bug is fixed

## Troubleshooting

### Common Issues

1. **Import Errors**
   - Ensure all dependencies are in requirements.txt
   - Check Python path configuration

2. **Database Connection**
   - Verify DATABASE_URL is correct
   - Ensure database is accessible from Vercel

3. **OAuth Redirect Issues**
   - Check redirect URIs in Google Console
   - Verify HTTPS is used in production

4. **Function Timeout**
   - YouTube API calls might be slow
   - Consider increasing maxDuration in vercel.json

5. **Static Files**
   - Ensure static files are in the correct directory
   - Check static file routing in vercel.json

### Performance Optimization

1. **Database Connection Pooling**
   - Already configured in app.py
   - Monitor connection usage

2. **API Response Caching**
   - Consider caching YouTube API responses
   - Implement Redis for session storage

3. **Function Memory**
   - Increase memory if needed (currently set to 1024MB)
   - Monitor memory usage in Vercel dashboard

## Security Considerations

1. **Environment Variables**
   - Never commit secrets to git
   - Use Vercel's environment variable encryption

2. **HTTPS Only**
   - Vercel provides HTTPS by default
   - Ensure all OAuth redirects use HTTPS

3. **Session Security**
   - Use a strong SESSION_SECRET
   - Consider session timeout settings

## Monitoring

1. **Vercel Analytics**: Enable in dashboard
2. **Error Tracking**: Consider Sentry integration
3. **Performance**: Monitor function execution time
4. **API Usage**: Track YouTube API quota usage

## Support

- **Vercel Docs**: [vercel.com/docs](https://vercel.com/docs)
- **Flask on Vercel**: [vercel.com/guides/using-flask-with-vercel](https://vercel.com/guides/using-flask-with-vercel)
- **Issues**: Check Vercel dashboard logs and GitHub issues