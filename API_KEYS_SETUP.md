# API Keys Setup Guide for TL;DW

## 1. SESSION_SECRET ✅ 
**Use one of these generated values:**

```bash
# Option 1 (Complex):
SESSION_SECRET=tarT@AjJHgMYS88c&vAf&pj#4cVMGwAPNg&OCPhBU8FWufULgLNf%l#7pGWRol2U

# Option 2 (URL-safe):
SESSION_SECRET=tCv0_bBRRytIVR4DCrbjBvpFv_RrGY1Lyf5BxYiegKQ
```

## 2. GOOGLE_OAUTH_CLIENT_ID & GOOGLE_OAUTH_CLIENT_SECRET

### Step-by-Step Setup:

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/

2. **Create or Select Project**
   - Click "Select a project" → "New Project"
   - Name: "TL;DW" or similar
   - Click "Create"

3. **Enable YouTube Data API v3**
   - Go to "APIs & Services" → "Library"
   - Search for "YouTube Data API v3"
   - Click on it and press "Enable"

4. **Create OAuth 2.0 Credentials**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "OAuth 2.0 Client IDs"
   - Choose "Web application"
   - Name: "TL;DW Web App"

5. **Configure Authorized Redirect URIs**
   ```
   # For local development:
   http://localhost:5000/auth/callback
   
   # For Vercel production (replace with your actual domain):
   https://your-app-name.vercel.app/auth/callback
   ```

6. **Copy Your Credentials**
   - Client ID: `123456789-abcdefghijklmnop.apps.googleusercontent.com`
   - Client Secret: `GOCSPX-abcdefghijklmnopqrstuvwxyz`

### Required Scopes:
Your app needs these YouTube scopes (already configured in code):
- `https://www.googleapis.com/auth/youtube.readonly`
- `https://www.googleapis.com/auth/youtube`

## 3. OPENAI_API_KEY

### Step-by-Step Setup:

1. **Go to OpenAI Platform**
   - Visit: https://platform.openai.com/

2. **Sign Up/Login**
   - Create account or login with existing account

3. **Create API Key**
   - Go to "API Keys" section
   - Click "Create new secret key"
   - Name: "TL;DW Production"
   - Copy the key: `sk-proj-abcdefghijklmnopqrstuvwxyz...`

4. **Add Billing (Required)**
   - Go to "Billing" section
   - Add payment method
   - Set usage limits if desired

### API Usage:
- Your app uses GPT models for video summarization
- Estimated cost: ~$0.01-0.05 per video summary
- Monitor usage in OpenAI dashboard

## 4. DATABASE_URL

### Option A: Vercel Postgres (Recommended)

1. **In Vercel Dashboard**
   - Go to your project
   - Click "Storage" tab
   - Click "Create Database"
   - Choose "Postgres"
   - Select region (same as your app)

2. **Get Connection String**
   - Vercel will automatically add `DATABASE_URL` to your environment variables
   - Format: `postgresql://username:password@host:port/database`

### Option B: Supabase (Free Alternative)

1. **Go to Supabase**
   - Visit: https://supabase.com/
   - Sign up and create new project

2. **Get Database URL**
   - Go to Settings → Database
   - Copy "Connection string"
   - Format: `postgresql://postgres:[password]@[host]:5432/postgres`

### Option C: Railway (Free Alternative)

1. **Go to Railway**
   - Visit: https://railway.app/
   - Sign up and create new project

2. **Add PostgreSQL**
   - Click "New" → "Database" → "PostgreSQL"
   - Copy connection string from variables

## 5. Complete Environment Variables

Once you have all values, set these in Vercel:

```bash
SESSION_SECRET=tCv0_bBRRytIVR4DCrbjBvpFv_RrGY1Lyf5BxYiegKQ
GOOGLE_OAUTH_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz
OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz...
DATABASE_URL=postgresql://username:password@host:port/database
```

## 6. Setting Environment Variables in Vercel

### Via Vercel Dashboard:
1. Go to your project in Vercel dashboard
2. Click "Settings" tab
3. Click "Environment Variables"
4. Add each variable:
   - Name: `SESSION_SECRET`
   - Value: `tCv0_bBRRytIVR4DCrbjBvpFv_RrGY1Lyf5BxYiegKQ`
   - Environment: Production, Preview, Development

### Via Vercel CLI:
```bash
vercel env add SESSION_SECRET
vercel env add GOOGLE_OAUTH_CLIENT_ID
vercel env add GOOGLE_OAUTH_CLIENT_SECRET
vercel env add OPENAI_API_KEY
vercel env add DATABASE_URL
```

## 7. Testing Your Setup

1. **Deploy to Vercel**
   ```bash
   vercel --prod
   ```

2. **Test Health Check**
   ```bash
   curl https://your-app.vercel.app/api/health
   ```

3. **Test OAuth Flow**
   - Visit your app
   - Try to login with Google
   - Check if Watch Later playlist shows correct video count

## 8. Security Best Practices

- ✅ Never commit API keys to git
- ✅ Use different keys for development/production
- ✅ Monitor API usage and set limits
- ✅ Rotate keys periodically
- ✅ Use Vercel's encrypted environment variables

## 9. Troubleshooting

### Common Issues:

1. **OAuth Redirect Mismatch**
   - Ensure redirect URI in Google Console matches your domain exactly
   - Include both HTTP (dev) and HTTPS (prod) versions

2. **Database Connection Failed**
   - Check DATABASE_URL format
   - Ensure database is accessible from Vercel's IP ranges

3. **OpenAI API Errors**
   - Verify API key is correct
   - Check billing is set up
   - Monitor rate limits

4. **Session Issues**
   - Ensure SESSION_SECRET is set
   - Check if it's the same across all environments

## 10. Cost Estimation

- **Vercel**: Free tier covers most small apps
- **Database**: 
  - Vercel Postgres: ~$20/month
  - Supabase: Free tier available
- **OpenAI**: ~$0.01-0.05 per video summary
- **Google APIs**: Free quota usually sufficient

## Support

If you need help with any of these steps:
1. Check the service's documentation
2. Look for error messages in Vercel logs
3. Test each component individually
4. Verify environment variables are set correctly