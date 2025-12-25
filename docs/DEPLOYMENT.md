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
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
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
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
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
---


## CloudWatch Logs Insights Query Templates

The TL;DW application uses structured JSON logging that's optimized for CloudWatch Logs Insights queries. This section provides pre-built query templates for common troubleshooting and monitoring scenarios.

### Prerequisites

1. **CloudWatch Logs Access**: Ensure you have access to the App Runner log group
2. **Log Group Name**: Typically `/aws/apprunner/tldw-transcript-service`
3. **CloudWatch Logs Insights**: Available in the AWS Console under CloudWatch > Logs > Insights

### Query Templates

#### Error and Timeout Analysis

**Basic Error Analysis** - Find recent errors and timeouts:
```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 200
```

**Detailed Error Classification** - Group errors by type and stage:
```sql
fields @timestamp, lvl, event, stage, outcome, detail, job_id, video_id, dur_ms, attempt, use_proxy, profile
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by stage, outcome, detail
| sort error_count desc
```

#### Success Rate Analysis

**Stage Funnel Analysis** - Success rates by pipeline stage:
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as success_count, 
        countif(outcome="error") as error_count,
        countif(outcome="timeout") as timeout_count,
        countif(outcome="blocked") as blocked_count,
        countif(outcome="no_captions") as no_captions_count,
        count(*) as total_attempts
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| eval error_rate = round(error_count * 100.0 / total_attempts, 2)
| eval timeout_rate = round(timeout_count * 100.0 / total_attempts, 2)
| sort success_rate asc
```

**Simple Success Rate by Stage**:
```sql
fields stage, outcome
| filter event = "stage_result"
| stats countif(outcome="success") as ok, count(*) as total by stage
| eval success_pct = round(ok * 100.0 / total, 2)
| sort success_pct asc
```

#### Performance Analysis

**P95 Duration by Stage** - Performance metrics for each pipeline stage:
```sql
fields stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms,
        pct(dur_ms, 50) as p50_ms,
        pct(dur_ms, 95) as p95_ms,
        pct(dur_ms, 99) as p99_ms,
        max(dur_ms) as max_ms,
        count() as sample_count
  by stage
| sort p95_ms desc
```

**Performance Trends Over Time**:
```sql
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by bin(5m), stage
| sort @timestamp desc
```

#### Job Correlation and Troubleshooting

**Complete Job Trace** - Follow a specific job through the pipeline:
```sql
fields @timestamp, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter job_id = "j-7f3d"
| sort @timestamp asc
```

**Video Processing History** - All attempts for a specific video:
```sql
fields @timestamp, job_id, event, stage, outcome, dur_ms, detail, attempt, use_proxy, profile
| filter video_id = "bbz2boNSeL0"
| sort @timestamp desc
| limit 100
```

**Job Lifecycle Events** - Key events for job tracking:
```sql
fields @timestamp, event, stage, outcome, dur_ms, detail
| filter job_id = "j-7f3d"
| filter event in ["job_received", "stage_start", "stage_result", "job_finished"]
| sort @timestamp asc
```

#### Specialized Analysis

**Failed Jobs Summary** - Jobs with the most failures:
```sql
fields job_id, video_id, stage, outcome, detail
| filter event = "stage_result" and outcome in ["error", "timeout", "blocked"]
| stats count() as failure_count by job_id, video_id
| sort failure_count desc
| limit 50
```

**Proxy Effectiveness** - Compare success rates with/without proxy:
```sql
fields use_proxy, outcome, stage
| filter event = "stage_result" and ispresent(use_proxy)
| stats countif(outcome="success") as success_count,
        count() as total_attempts
  by use_proxy, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, use_proxy
```

**Profile Analysis** - Success rates by browser profile:
```sql
fields profile, outcome, stage
| filter event = "stage_result" and ispresent(profile)
| stats countif(outcome="success") as success_count,
        count() as total_attempts
  by profile, stage
| eval success_rate = round(success_count * 100.0 / total_attempts, 2)
| sort stage, success_rate desc
```

**FFmpeg Error Analysis** - Audio extraction failures:
```sql
fields @timestamp, job_id, video_id, detail, stderr_tail
| filter stage = "ffmpeg" and outcome = "error"
| sort @timestamp desc
| limit 50
```

**Timeout Analysis** - Timeout patterns by stage:
```sql
fields stage, dur_ms, detail
| filter outcome = "timeout"
| stats avg(dur_ms) as avg_timeout_ms,
        pct(dur_ms, 95) as p95_timeout_ms,
        count() as timeout_count
  by stage
| sort timeout_count desc
```

### Using Query Templates in Code

The application includes a `cloudwatch_query_templates.py` module with programmatic access to these queries:

```python
from cloudwatch_query_templates import QUERY_TEMPLATES, format_job_query

# Get error analysis query
error_query = QUERY_TEMPLATES['error_analysis']

# Format job-specific query
job_trace = format_job_query('job_correlation', 'j-7f3d')

# Use with boto3
import boto3
logs_client = boto3.client('logs')

response = logs_client.start_query(
    logGroupName='/aws/apprunner/tldw-transcript-service',
    startTime=int((datetime.now() - timedelta(hours=24)).timestamp()),
    endTime=int(datetime.now().timestamp()),
    queryString=error_query
)
```

### Common Query Patterns

#### Time Range Filters
Add these filters to limit query scope:
```sql
# Last hour
| filter @timestamp > @timestamp - 1h

# Last 24 hours  
| filter @timestamp > @timestamp - 24h

# Last week
| filter @timestamp > @timestamp - 7d
```

#### Log Level Filters
```sql
# Errors only
| filter lvl in ["ERROR", "CRITICAL"]

# Warnings and errors
| filter lvl in ["WARNING", "ERROR", "CRITICAL"]
```

#### Stage Filters
```sql
# Transcript extraction stages only
| filter stage in ["youtube-transcript-api", "timedtext", "youtubei", "asr"]

# Network-dependent stages
| filter stage in ["youtubei", "timedtext"]
```

### Monitoring and Alerting

#### Recommended CloudWatch Alarms

1. **High Error Rate**:
   - Metric: Custom metric from error analysis query
   - Threshold: >5% error rate over 15 minutes
   - Action: SNS notification

2. **High P95 Duration**:
   - Metric: Custom metric from performance analysis
   - Threshold: >30 seconds P95 duration
   - Action: SNS notification

3. **Job Failure Rate**:
   - Metric: Failed jobs per hour
   - Threshold: >10 failed jobs in 1 hour
   - Action: SNS notification

#### Dashboard Widgets

Create CloudWatch dashboards with these widgets:

1. **Error Rate Timeline**: Line chart showing error percentage over time
2. **Stage Success Rates**: Bar chart of success rates by stage
3. **Performance Heatmap**: Duration percentiles by stage over time
4. **Recent Failures**: Table of recent error events

### Troubleshooting Guide

#### High Error Rates
1. Run the **error analysis** query to identify error patterns
2. Check **proxy effectiveness** if network-related errors
3. Use **job correlation** to trace specific failures
4. Review **FFmpeg errors** for audio extraction issues

#### Performance Issues
1. Use **performance analysis** to identify slow stages
2. Check **timeout analysis** for stages hitting limits
3. Review **performance trends** for degradation over time
4. Analyze **profile effectiveness** for optimization opportunities

#### Failed Jobs Investigation
1. Start with **failed jobs summary** to identify problem videos
2. Use **video correlation** to see all attempts for a video
3. Run **job lifecycle trace** for complete job history
4. Check **stage funnel analysis** for pipeline bottlenecks

### Query Optimization Tips

1. **Use Time Ranges**: Always limit queries to relevant time periods
2. **Filter Early**: Add filters before stats operations for better performance
3. **Limit Results**: Use `limit` clause to prevent large result sets
4. **Index Fields**: The JSON schema is optimized for common query patterns
5. **Combine Filters**: Use `and`/`or` operators to combine multiple conditions

### Cost Optimization

1. **Query Scope**: Limit time ranges to reduce data scanned
2. **Log Retention**: Set appropriate retention periods (default: 30 days)
3. **Sampling**: Use sampling for high-volume analysis
4. **Scheduled Queries**: Use CloudWatch Events for regular monitoring queries

This structured logging and query system provides comprehensive observability into the TL;DW application's behavior, enabling quick troubleshooting and performance optimization.