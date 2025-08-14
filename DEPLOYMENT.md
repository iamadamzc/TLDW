# TL;DW Deployment Guide

This guide covers deployment options for the TL;DW application, with a focus on AWS App Runner (recommended) and Vercel as an alternative.

## AWS App Runner Deployment (Recommended)

AWS App Runner provides a simple way to deploy containerized applications with automatic scaling and load balancing.

### Prerequisites

1. **AWS Account**: Sign up at [aws.amazon.com](https://aws.amazon.com)
2. **GitHub Repository**: Push your code to GitHub
3. **Environment Variables**: Prepare the required environment variables

### Deployment Options

You can deploy using either **Docker Runtime** or **Python Runtime**. Both configurations are provided and tested.

#### Option 1: Docker Runtime (apprunner.yaml)
- Uses the existing Dockerfile
- Runs on port 8000
- More control over the environment
- Slightly longer build times

#### Option 2: Python Runtime (apprunner-python-runtime.yaml) - **Recommended**
- Uses App Runner's managed Python environment
- Runs on port 8080
- Faster deployments
- Automatic dependency management

### Step-by-Step Deployment

#### 1. Choose Your Configuration

**For Docker Runtime:**
- Use the existing `apprunner.yaml` file
- No changes needed

**For Python Runtime:**
- Rename `apprunner-python-runtime.yaml` to `apprunner.yaml`
- Or copy its contents to replace the existing `apprunner.yaml`

#### 2. Set Up App Runner Service

1. Go to [AWS App Runner Console](https://console.aws.amazon.com/apprunner/)
2. Click "Create service"
3. Choose "Source code repository"
4. Connect to GitHub and select your repository
5. Choose branch (usually `main`)
6. App Runner will automatically detect the `apprunner.yaml` configuration

#### 3. Configure Environment Variables

In the App Runner service configuration, add these environment variables:

```
SESSION_SECRET=your-super-secret-session-key-here
GOOGLE_OAUTH_CLIENT_ID=your-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=your-postgresql-database-url
RESEND_API_KEY=your-resend-api-key
```

#### 4. Deploy

1. Review your configuration
2. Click "Create & deploy"
3. App Runner will build and deploy your application
4. You'll get a unique App Runner URL

### Configuration Files Explained

#### Docker Runtime Configuration (apprunner.yaml)
```yaml
version: 1.0
runtime: docker
build:
  dockerfile: Dockerfile
```

#### Python Runtime Configuration (apprunner-python-runtime.yaml)
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - pip install -r requirements.txt
run:
  command: gunicorn --bind 0.0.0.0:8080 --workers 1 app:app
  network:
    port: 8080
```

### Google OAuth Setup for App Runner

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials
3. Add your App Runner URL to authorized redirect URIs:
   ```
   https://your-app-runner-url.region.awsapprunner.com/auth/callback
   ```

### Troubleshooting App Runner Deployment

#### Common Issues

1. **CREATE_FAILED Status**
   - **Cause**: Incorrect apprunner.yaml syntax
   - **Solution**: Ensure you're using the correct configuration for your chosen runtime
   - **Check**: Don't mix Docker and Python runtime syntax

2. **Build Failures**
   - **Cause**: Missing dependencies or syntax errors in requirements.txt
   - **Solution**: Verify all dependencies are properly listed with versions
   - **Check**: Test locally with `pip install -r requirements.txt`

3. **Health Check Failures**
   - **Cause**: Application not responding on the correct port
   - **Solution**: Ensure your app runs on port 8000 (Docker) or 8080 (Python)
   - **Check**: The `/health` endpoint should return HTTP 200

4. **Runtime Conflicts**
   - **Cause**: Using wrong configuration file
   - **Solution**: Use only one apprunner.yaml file with consistent runtime syntax

#### Debugging Steps

1. **Check App Runner Logs**
   - Go to App Runner console
   - View deployment and application logs
   - Look for specific error messages

2. **Validate Configuration Locally**
   ```bash
   # For Docker runtime
   docker build -t test-app .
   docker run -p 8000:8000 test-app
   curl http://localhost:8000/health
   
   # For Python runtime
   pip install -r requirements.txt
   gunicorn --bind 0.0.0.0:8080 --workers 1 app:app
   ```

3. **Check IAM Permissions**
   - Ensure App Runner has necessary permissions
   - Verify GitHub connection is working

### Performance and Scaling

App Runner automatically handles:
- **Auto Scaling**: Based on incoming requests
- **Load Balancing**: Distributes traffic across instances
- **Health Checks**: Uses the `/health` endpoint
- **HTTPS**: Automatic SSL certificate

---

## Vercel Deployment (Alternative)

### Prerequisites for Vercel

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **GitHub Repository**: Push your code to GitHub
3. **Environment Variables**: Prepare the required environment variables

## Required Environment Variables (Both Platforms)

Set these in your Vercel dashboard under Project Settings > Environment Variables:

### Required Variables
```
SESSION_SECRET=your-super-secret-session-key-here
GOOGLE_OAUTH_CLIENT_ID=your-google-oauth-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-oauth-client-secret
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=your-postgresql-database-url
RESEND_API_KEY=your-resend-api-key
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

1. **Test the application**: Visit your App Runner URL
2. **Check logs**: Use App Runner console to view deployment and application logs
3. **Test proxy configuration**: Run the proxy configuration test (see below)
4. **Monitor performance**: Watch for any timeout issues
5. **Test OAuth flow**: Ensure Google login works
6. **Test transcript fetching**: Verify YouTube transcript fetching works without IP blocking

### Testing Proxy Configuration

To verify that the proxy configuration is working properly in App Runner:

1. **SSH into App Runner instance** (if available) or check logs for the following test
2. **Run the proxy test script**:
   ```bash
   python test_proxy_config.py
   ```
3. **Expected output should show**:
   - ✅ USE_PROXIES environment variable set to "true"
   - ✅ OXYLABS_PROXY_CONFIG environment variable configured
   - ✅ AWS Secrets Manager access working
   - ✅ ProxyManager initialization successful
   - ✅ Proxy connectivity test passed

4. **Check application logs** for proxy usage:
   - Look for "ProxyManager initialized with Oxylabs proxy" messages
   - Monitor for "Session created" and "Request success" log entries
   - Watch for any "YouTube blocking detected" warnings

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

---

## Deployment Platform Comparison

| Feature | AWS App Runner | Vercel |
|---------|----------------|--------|
| **Ease of Setup** | Medium | Easy |
| **Auto Scaling** | ✅ Built-in | ✅ Built-in |
| **Custom Domains** | ✅ Supported | ✅ Supported |
| **Database** | External required | Vercel Postgres available |
| **Build Time** | Medium | Fast |
| **Cold Starts** | Minimal | Some |
| **Pricing** | Pay per use | Free tier + pay per use |
| **Docker Support** | ✅ Native | ❌ Limited |
| **Long-running Tasks** | ✅ Supported | ❌ 10s timeout |
| **WebSocket Support** | ✅ Supported | ❌ Limited |

### Recommendation

- **Choose App Runner** if you need:
  - Docker deployment flexibility
  - Long-running background tasks
  - Full control over the runtime environment
  - WebSocket support

- **Choose Vercel** if you need:
  - Fastest deployment setup
  - Built-in database options
  - Edge network optimization
  - Serverless architecture

## Support and Resources

### App Runner Resources
- **AWS App Runner Docs**: [docs.aws.amazon.com/apprunner](https://docs.aws.amazon.com/apprunner/)
- **Configuration Reference**: [docs.aws.amazon.com/apprunner/latest/dg/config-file.html](https://docs.aws.amazon.com/apprunner/latest/dg/config-file.html)

### Vercel Resources
- **Vercel Docs**: [vercel.com/docs](https://vercel.com/docs)
- **Flask on Vercel**: [vercel.com/guides/using-flask-with-vercel](https://vercel.com/guides/using-flask-with-vercel)

### General Support
- **GitHub Issues**: Report bugs and issues in the repository
- **Application Logs**: Check platform-specific logging for debugging