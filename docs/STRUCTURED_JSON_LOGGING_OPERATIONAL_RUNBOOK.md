# Structured JSON Logging Operational Runbook

## Overview

This runbook provides step-by-step procedures for operating and analyzing the structured JSON logging system in the TL;DW application. It covers daily operations, incident response, performance monitoring, and maintenance tasks.

## Daily Operations

### Morning Health Check

**Frequency**: Daily at start of business hours  
**Duration**: 5-10 minutes  
**Responsibility**: Operations team

#### Procedure

1. **Check System Health**
   ```bash
   # Verify application health
   curl -s https://your-app-url/health | jq '.'
   
   # Check recent error rates
   aws logs start-query \
     --log-group-name "/aws/apprunner/tldw-transcript-service" \
     --start-time $(date -d '24 hours ago' +%s) \
     --end-time $(date +%s) \
     --query-string 'fields @timestamp | filter outcome = "error" | stats count() as error_count'
   ```

2. **Review Overnight Processing**
   ```sql
   # CloudWatch Logs Insights query
   fields @timestamp, job_id, event, outcome, dur_ms
   | filter @timestamp > datefloor(@timestamp, 1d) - 1d
   | filter event = "job_finished"
   | stats count() as total_jobs, countif(outcome="success") as successful_jobs, successful_jobs*100.0/total_jobs as success_rate
   ```

3. **Check Performance Metrics**
   ```sql
   # Stage performance review
   fields stage, dur_ms
   | filter @timestamp > datefloor(@timestamp, 1d) - 1d
   | filter event = "stage_result" and ispresent(dur_ms)
   | stats pct(dur_ms, 95) as p95_ms, avg(dur_ms) as avg_ms by stage
   | sort p95_ms desc
   ```

#### Expected Results
- Application health: `{"status": "healthy"}`
- Error rate: <5% of total events
- Job success rate: >90%
- P95 stage durations within normal ranges

#### Escalation Triggers
- Error rate >10%
- Job success rate <80%
- Any stage P95 duration >2x normal
- Application health check failures

### Log Volume Monitoring

**Frequency**: Twice daily  
**Duration**: 2-3 minutes

#### Procedure

1. **Check Log Ingestion Rate**
   ```bash
   # Get log ingestion metrics
   aws logs describe-metric-filters \
     --log-group-name "/aws/apprunner/tldw-transcript-service"
   
   # Check storage usage
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/apprunner/tldw" \
     --query 'logGroups[*].[logGroupName,storedBytes]'
   ```

2. **Monitor Rate Limiting Activity**
   ```sql
   fields @timestamp, @message
   | filter @message like /\[suppressed\]/
   | bin(@timestamp, 1h) as hour
   | stats count() as suppression_count by hour
   | sort hour desc
   | limit 24
   ```

#### Expected Results
- Log ingestion rate: 100-1000 events/minute during business hours
- Storage growth: <1GB per day
- Suppression events: <10 per hour

#### Actions Required
- If suppression >50/hour: Investigate noisy log sources
- If storage growth >2GB/day: Review log retention policies
- If ingestion rate drops to 0: Check application health

## Incident Response Procedures

### High Error Rate Alert

**Trigger**: Error rate >10% for 5 minutes  
**Severity**: P2  
**Response Time**: 15 minutes

#### Investigation Steps

1. **Identify Error Patterns**
   ```sql
   fields @timestamp, stage, outcome, detail, job_id, video_id
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | filter outcome in ["error", "timeout"]
   | stats count() as error_count by stage, detail
   | sort error_count desc
   | limit 20
   ```

2. **Check Affected Videos**
   ```sql
   fields video_id, stage, outcome, detail
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | filter outcome = "error"
   | stats count() as error_count by video_id
   | sort error_count desc
   | limit 10
   ```

3. **Analyze Error Timeline**
   ```sql
   fields @timestamp, stage, outcome, detail
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | filter outcome = "error"
   | bin(@timestamp, 5m) as time_window
   | stats count() as error_count by time_window, stage
   | sort time_window desc
   ```

#### Resolution Actions

1. **If Single Stage Failing**:
   - Check stage-specific dependencies (proxy, API keys)
   - Review recent deployments
   - Consider disabling problematic stage temporarily

2. **If Multiple Stages Failing**:
   - Check system resources (CPU, memory)
   - Verify network connectivity
   - Review application logs for startup issues

3. **If Specific Videos Failing**:
   - Check video accessibility
   - Review content restrictions
   - Verify cookie/authentication status

### Performance Degradation

**Trigger**: P95 duration >2x baseline for 10 minutes  
**Severity**: P3  
**Response Time**: 30 minutes

#### Investigation Steps

1. **Identify Slow Stages**
   ```sql
   fields stage, dur_ms, job_id, video_id
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | filter event = "stage_result" and ispresent(dur_ms)
   | filter dur_ms > 30000
   | sort dur_ms desc
   | limit 20
   ```

2. **Check System Resources**
   ```sql
   fields @timestamp, cpu, mem_mb
   | filter event = "performance_metric"
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | bin(@timestamp, 5m) as time_window
   | stats avg(cpu) as avg_cpu, avg(mem_mb) as avg_memory by time_window
   | sort time_window desc
   ```

3. **Analyze Concurrent Load**
   ```sql
   fields @timestamp, job_id, event
   | filter event in ["job_received", "job_finished"]
   | filter @timestamp > datefloor(@timestamp, 1h) - 1h
   | bin(@timestamp, 5m) as time_window
   | stats countif(event="job_received") as started, countif(event="job_finished") as completed by time_window
   | sort time_window desc
   ```

#### Resolution Actions

1. **High CPU Usage**: Scale up application instances
2. **High Memory Usage**: Restart application, investigate memory leaks
3. **Network Issues**: Check proxy health, verify external API status
4. **Database Issues**: Check database performance, consider connection pooling

### Log Ingestion Failure

**Trigger**: No logs received for 10 minutes  
**Severity**: P1  
**Response Time**: 5 minutes

#### Investigation Steps

1. **Check Application Health**
   ```bash
   curl -s https://your-app-url/health
   ```

2. **Verify CloudWatch Connectivity**
   ```bash
   aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner/tldw"
   ```

3. **Check Application Logs**
   ```bash
   # Check container logs directly
   aws apprunner describe-service --service-arn YOUR_SERVICE_ARN
   ```

#### Resolution Actions

1. **Application Down**: Restart application service
2. **CloudWatch Issues**: Check IAM permissions, verify log group exists
3. **Network Issues**: Check AWS service status, verify connectivity

## Performance Monitoring

### Weekly Performance Review

**Frequency**: Weekly  
**Duration**: 30 minutes  
**Responsibility**: Development team

#### Metrics to Review

1. **Stage Performance Trends**
   ```sql
   fields stage, dur_ms
   | filter @timestamp > datefloor(@timestamp, 1d) - 7d
   | filter event = "stage_result" and ispresent(dur_ms)
   | bin(@timestamp, 1d) as day
   | stats pct(dur_ms, 95) as p95_ms, pct(dur_ms, 50) as p50_ms by day, stage
   | sort day desc, p95_ms desc
   ```

2. **Success Rate Trends**
   ```sql
   fields stage, outcome
   | filter @timestamp > datefloor(@timestamp, 1d) - 7d
   | filter event = "stage_result"
   | bin(@timestamp, 1d) as day
   | stats countif(outcome="success") as success, count() as total, success*100.0/total as success_rate by day, stage
   | sort day desc, success_rate asc
   ```

3. **Error Pattern Analysis**
   ```sql
   fields stage, detail
   | filter @timestamp > datefloor(@timestamp, 1d) - 7d
   | filter outcome = "error"
   | stats count() as error_count by stage, detail
   | sort error_count desc
   | limit 20
   ```

#### Actions Based on Trends

- **Degrading Performance**: Investigate infrastructure changes, optimize slow stages
- **Declining Success Rates**: Review external dependencies, update error handling
- **New Error Patterns**: Investigate root causes, implement fixes

### Monthly Capacity Planning

**Frequency**: Monthly  
**Duration**: 1 hour  
**Responsibility**: DevOps team

#### Capacity Metrics

1. **Processing Volume Trends**
   ```sql
   fields @timestamp, job_id
   | filter event = "job_received"
   | filter @timestamp > datefloor(@timestamp, 1d) - 30d
   | bin(@timestamp, 1d) as day
   | stats count() as daily_jobs by day
   | sort day desc
   ```

2. **Resource Utilization**
   ```sql
   fields @timestamp, cpu, mem_mb
   | filter event = "performance_metric"
   | filter @timestamp > datefloor(@timestamp, 1d) - 30d
   | bin(@timestamp, 1d) as day
   | stats avg(cpu) as avg_cpu, max(cpu) as max_cpu, avg(mem_mb) as avg_memory, max(mem_mb) as max_memory by day
   | sort day desc
   ```

3. **Log Storage Growth**
   ```bash
   # Check log storage trends
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/apprunner/tldw" \
     --query 'logGroups[*].[logGroupName,storedBytes,creationTime]'
   ```

## Maintenance Procedures

### Log Retention Management

**Frequency**: Monthly  
**Duration**: 15 minutes

#### Procedure

1. **Review Current Retention**
   ```bash
   aws logs describe-log-groups \
     --log-group-name-prefix "/aws/apprunner/tldw" \
     --query 'logGroups[*].[logGroupName,retentionInDays,storedBytes]'
   ```

2. **Adjust Retention Policies**
   ```bash
   # Set 30-day retention for production
   aws logs put-retention-policy \
     --log-group-name "/aws/apprunner/tldw-transcript-service" \
     --retention-in-days 30
   
   # Set 7-day retention for staging
   aws logs put-retention-policy \
     --log-group-name "/aws/apprunner/tldw-transcript-service-staging" \
     --retention-in-days 7
   ```

3. **Monitor Storage Costs**
   ```bash
   # Check CloudWatch costs
   aws ce get-cost-and-usage \
     --time-period Start=2025-08-01,End=2025-08-31 \
     --granularity MONTHLY \
     --metrics BlendedCost \
     --group-by Type=DIMENSION,Key=SERVICE
   ```

### Query Template Updates

**Frequency**: Quarterly  
**Duration**: 2 hours

#### Procedure

1. **Review Query Performance**
   - Test all documented query templates
   - Measure execution times
   - Identify slow or failing queries

2. **Update Query Templates**
   - Optimize slow queries
   - Add new queries for common use cases
   - Remove obsolete queries

3. **Update Documentation**
   - Update query template guide
   - Add new examples
   - Document query optimization tips

### Dashboard Maintenance

**Frequency**: Monthly  
**Duration**: 1 hour

#### Procedure

1. **Review Dashboard Widgets**
   - Check all widgets are displaying data
   - Verify query syntax is current
   - Update time ranges as needed

2. **Update Alert Thresholds**
   - Review alert trigger rates
   - Adjust thresholds based on trends
   - Add new alerts for emerging patterns

3. **Test Alert Notifications**
   - Verify alert delivery mechanisms
   - Test escalation procedures
   - Update contact information

## Troubleshooting Workflows

### "No Data" in Queries

**Symptoms**: CloudWatch queries return no results

#### Troubleshooting Steps

1. **Verify Time Range**
   ```sql
   fields @timestamp, @message
   | limit 10
   ```

2. **Check Field Names**
   ```sql
   fields @timestamp, job_id, video_id, stage, event
   | filter ispresent(job_id)
   | limit 5
   ```

3. **Validate Log Group**
   ```bash
   aws logs describe-log-groups --log-group-name-prefix "/aws/apprunner/tldw"
   ```

### High Query Costs

**Symptoms**: Unexpected CloudWatch Logs Insights charges

#### Investigation Steps

1. **Review Query History**
   ```bash
   aws logs describe-queries --status Complete
   ```

2. **Identify Expensive Queries**
   - Check queries scanning large time ranges
   - Look for queries without filters
   - Identify frequently run queries

3. **Optimize Query Patterns**
   - Add time filters to all queries
   - Use field filters early in query
   - Limit result sets appropriately

### Missing Correlation IDs

**Symptoms**: Log entries missing job_id or video_id

#### Investigation Steps

1. **Check Context Setting**
   ```sql
   fields @timestamp, job_id, video_id, stage, event
   | filter ispresent(stage) and not ispresent(job_id)
   | limit 10
   ```

2. **Identify Affected Components**
   ```sql
   fields @timestamp, @message
   | filter not ispresent(job_id) and ispresent(stage)
   | stats count() by stage
   ```

3. **Review Thread Context**
   - Check if context is set in worker threads
   - Verify context inheritance in async operations
   - Ensure context clearing doesn't happen prematurely

## Emergency Contacts

### Escalation Matrix

| Issue Type | Severity | Primary Contact | Secondary Contact | Escalation Time |
|------------|----------|----------------|-------------------|-----------------|
| Application Down | P1 | On-call Engineer | DevOps Lead | 5 minutes |
| High Error Rate | P2 | Development Lead | Product Owner | 15 minutes |
| Performance Issues | P3 | Development Team | DevOps Team | 30 minutes |
| Log Analysis Issues | P4 | Operations Team | Development Team | 2 hours |

### Contact Information

- **On-call Engineer**: [Phone/Slack]
- **Development Lead**: [Phone/Email]
- **DevOps Lead**: [Phone/Email]
- **Product Owner**: [Email/Slack]
- **AWS Support**: [Case system/Phone]

## Standard Operating Procedures

### Daily Checklist

- [ ] Morning health check completed
- [ ] Error rates within normal ranges
- [ ] Performance metrics reviewed
- [ ] Log volume monitored
- [ ] Any alerts investigated and resolved

### Weekly Checklist

- [ ] Performance trends analyzed
- [ ] Success rate trends reviewed
- [ ] Error patterns investigated
- [ ] Capacity planning data collected
- [ ] Dashboard accuracy verified

### Monthly Checklist

- [ ] Log retention policies reviewed
- [ ] Storage costs analyzed
- [ ] Query templates updated
- [ ] Dashboard maintenance completed
- [ ] Alert thresholds tuned

### Quarterly Checklist

- [ ] Comprehensive system review
- [ ] Documentation updates
- [ ] Team training conducted
- [ ] Process improvements implemented
- [ ] Disaster recovery procedures tested

## Metrics and KPIs

### Operational Metrics

- **System Availability**: >99.9%
- **Error Rate**: <5%
- **Job Success Rate**: >90%
- **P95 Response Time**: <30 seconds per stage
- **Log Ingestion Latency**: <30 seconds

### Business Metrics

- **Mean Time to Detection (MTTD)**: <5 minutes
- **Mean Time to Resolution (MTTR)**: <30 minutes
- **Customer Impact**: <1% of jobs affected by incidents
- **Operational Efficiency**: 80% of issues resolved using logs

### Cost Metrics

- **CloudWatch Logs Storage**: <$100/month
- **Logs Insights Queries**: <$50/month
- **Operational Overhead**: <2 hours/week
- **Cost per Job**: <$0.01 in logging costs

## Continuous Improvement

### Monthly Review Process

1. **Collect Feedback**: Gather input from development and operations teams
2. **Analyze Metrics**: Review operational and business metrics
3. **Identify Improvements**: Document areas for enhancement
4. **Plan Changes**: Prioritize and schedule improvements
5. **Implement Updates**: Execute approved changes
6. **Measure Impact**: Validate improvement effectiveness

### Common Improvement Areas

- **Query Optimization**: Improve query performance and reduce costs
- **Alert Tuning**: Reduce false positives and improve signal-to-noise ratio
- **Dashboard Enhancement**: Add new visualizations and improve usability
- **Process Automation**: Automate routine maintenance tasks
- **Documentation Updates**: Keep procedures current and comprehensive