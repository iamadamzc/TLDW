"""
CloudWatch Alerts Configuration for TL;DW Application

This module provides alert configurations for monitoring error rates, performance thresholds,
and system health using CloudWatch Logs Insights metrics and alarms.
"""

import json
from typing import Dict, List, Any, Optional
from datetime import datetime


class CloudWatchAlertsConfig:
    """Configuration generator for CloudWatch alerts and alarms."""
    
    def __init__(self, 
                 log_group_name: str = '/aws/apprunner/tldw-transcript-service',
                 region: str = 'us-east-1',
                 sns_topic_arn: str = None):
        self.log_group_name = log_group_name
        self.region = region
        self.sns_topic_arn = sns_topic_arn
    
    def create_error_rate_alerts(self) -> List[Dict[str, Any]]:
        """Create error rate monitoring alerts."""
        return [
            self._create_high_error_rate_alert(),
            self._create_timeout_spike_alert(),
            self._create_stage_failure_alert(),
            self._create_job_failure_spike_alert()
        ]
    
    def create_performance_alerts(self) -> List[Dict[str, Any]]:
        """Create performance threshold alerts."""
        return [
            self._create_high_p95_duration_alert(),
            self._create_slow_stage_alert(),
            self._create_ffmpeg_timeout_alert(),
            self._create_memory_usage_alert()
        ]
    
    def create_system_health_alerts(self) -> List[Dict[str, Any]]:
        """Create system health monitoring alerts."""
        return [
            self._create_circuit_breaker_alert(),
            self._create_rate_limiting_alert(),
            self._create_log_volume_alert(),
            self._create_proxy_failure_alert()
        ]
    
    def _create_high_error_rate_alert(self) -> Dict[str, Any]:
        """Create alert for high error rates across all stages."""
        return {
            "AlarmName": "TL-DW-High-Error-Rate",
            "AlarmDescription": "Alert when error rate exceeds 5% over 15 minutes",
            "MetricName": "ErrorRate",
            "Namespace": "TL-DW/Pipeline",
            "Statistic": "Average",
            "Period": 300,  # 5 minutes
            "EvaluationPeriods": 3,  # 15 minutes total
            "Threshold": 5.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, stage, outcome
| filter event = "stage_result"
| stats countif(outcome in ["error", "timeout", "blocked"]) as errors, count(*) as total by bin(5m)
| eval error_rate = errors * 100.0 / total
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "ErrorRate"},
                {"Key": "Severity", "Value": "High"}
            ]
        }
    
    def _create_timeout_spike_alert(self) -> Dict[str, Any]:
        """Create alert for timeout spikes."""
        return {
            "AlarmName": "TL-DW-Timeout-Spike",
            "AlarmDescription": "Alert when timeout rate exceeds 10% over 10 minutes",
            "MetricName": "TimeoutRate",
            "Namespace": "TL-DW/Pipeline",
            "Statistic": "Average",
            "Period": 300,
            "EvaluationPeriods": 2,  # 10 minutes total
            "Threshold": 10.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, stage, outcome
| filter event = "stage_result"
| stats countif(outcome = "timeout") as timeouts, count(*) as total by bin(5m)
| eval timeout_rate = timeouts * 100.0 / total
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "TimeoutRate"},
                {"Key": "Severity", "Value": "Medium"}
            ]
        }
    
    def _create_stage_failure_alert(self) -> Dict[str, Any]:
        """Create alert for specific stage failures."""
        return {
            "AlarmName": "TL-DW-Stage-Failure",
            "AlarmDescription": "Alert when any stage has >20% failure rate over 20 minutes",
            "MetricName": "StageFailureRate",
            "Namespace": "TL-DW/Pipeline",
            "Statistic": "Maximum",
            "Period": 300,
            "EvaluationPeriods": 4,  # 20 minutes total
            "Threshold": 20.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, stage, outcome
| filter event = "stage_result"
| stats countif(outcome in ["error", "timeout", "blocked"]) as failures, count(*) as total by bin(5m), stage
| eval failure_rate = failures * 100.0 / total
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "StageFailure"},
                {"Key": "Severity", "Value": "High"}
            ]
        }
    
    def _create_job_failure_spike_alert(self) -> Dict[str, Any]:
        """Create alert for job failure spikes."""
        return {
            "AlarmName": "TL-DW-Job-Failure-Spike",
            "AlarmDescription": "Alert when >10 jobs fail in 1 hour",
            "MetricName": "JobFailureCount",
            "Namespace": "TL-DW/Jobs",
            "Statistic": "Sum",
            "Period": 3600,  # 1 hour
            "EvaluationPeriods": 1,
            "Threshold": 10,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, job_id, outcome
| filter event = "job_finished" and outcome in ["failed", "error"]
| stats count() as failed_jobs by bin(1h)
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "JobFailure"},
                {"Key": "Severity", "Value": "Critical"}
            ]
        }
    
    def _create_high_p95_duration_alert(self) -> Dict[str, Any]:
        """Create alert for high P95 durations."""
        return {
            "AlarmName": "TL-DW-High-P95-Duration",
            "AlarmDescription": "Alert when P95 duration exceeds 30 seconds for any stage",
            "MetricName": "P95Duration",
            "Namespace": "TL-DW/Performance",
            "Statistic": "Maximum",
            "Period": 600,  # 10 minutes
            "EvaluationPeriods": 2,  # 20 minutes total
            "Threshold": 30000,  # 30 seconds in milliseconds
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats pct(dur_ms, 95) as p95_ms by bin(10m), stage
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "Performance"},
                {"Key": "Severity", "Value": "Medium"}
            ]
        }
    
    def _create_slow_stage_alert(self) -> Dict[str, Any]:
        """Create alert for consistently slow stages."""
        return {
            "AlarmName": "TL-DW-Slow-Stage",
            "AlarmDescription": "Alert when average stage duration exceeds 20 seconds",
            "MetricName": "AverageDuration",
            "Namespace": "TL-DW/Performance",
            "Statistic": "Maximum",
            "Period": 900,  # 15 minutes
            "EvaluationPeriods": 2,  # 30 minutes total
            "Threshold": 20000,  # 20 seconds in milliseconds
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms by bin(15m), stage
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "Performance"},
                {"Key": "Severity", "Value": "Medium"}
            ]
        }
    
    def _create_ffmpeg_timeout_alert(self) -> Dict[str, Any]:
        """Create alert for FFmpeg timeout issues."""
        return {
            "AlarmName": "TL-DW-FFmpeg-Timeout",
            "AlarmDescription": "Alert when FFmpeg timeout rate exceeds 15%",
            "MetricName": "FFmpegTimeoutRate",
            "Namespace": "TL-DW/FFmpeg",
            "Statistic": "Average",
            "Period": 600,  # 10 minutes
            "EvaluationPeriods": 2,  # 20 minutes total
            "Threshold": 15.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, outcome
| filter stage = "ffmpeg"
| stats countif(outcome = "timeout") as timeouts, count(*) as total by bin(10m)
| eval timeout_rate = timeouts * 100.0 / total
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "FFmpegTimeout"},
                {"Key": "Severity", "Value": "High"}
            ]
        }
    
    def _create_memory_usage_alert(self) -> Dict[str, Any]:
        """Create alert for high memory usage."""
        return {
            "AlarmName": "TL-DW-High-Memory-Usage",
            "AlarmDescription": "Alert when memory usage exceeds 85%",
            "MetricName": "MemoryUsage",
            "Namespace": "TL-DW/System",
            "Statistic": "Maximum",
            "Period": 300,  # 5 minutes
            "EvaluationPeriods": 3,  # 15 minutes total
            "Threshold": 85.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, mem_mb
| filter event = "performance_metric" and ispresent(mem_mb)
| stats max(mem_mb) as max_mem_mb by bin(5m)
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "MemoryUsage"},
                {"Key": "Severity", "Value": "High"}
            ]
        }
    
    def _create_circuit_breaker_alert(self) -> Dict[str, Any]:
        """Create alert for circuit breaker state changes."""
        return {
            "AlarmName": "TL-DW-Circuit-Breaker-Open",
            "AlarmDescription": "Alert when circuit breaker opens",
            "MetricName": "CircuitBreakerEvents",
            "Namespace": "TL-DW/System",
            "Statistic": "Sum",
            "Period": 300,  # 5 minutes
            "EvaluationPeriods": 1,
            "Threshold": 1,
            "ComparisonOperator": "GreaterThanOrEqualToThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, event, detail
| filter event like /circuit_breaker/ or detail like /circuit.*breaker.*open/
| stats count() as cb_events by bin(5m)
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "CircuitBreaker"},
                {"Key": "Severity", "Value": "Critical"}
            ]
        }
    
    def _create_rate_limiting_alert(self) -> Dict[str, Any]:
        """Create alert for excessive rate limiting."""
        return {
            "AlarmName": "TL-DW-Excessive-Rate-Limiting",
            "AlarmDescription": "Alert when rate limiting suppresses >100 messages in 10 minutes",
            "MetricName": "RateLimitingSuppression",
            "Namespace": "TL-DW/System",
            "Statistic": "Sum",
            "Period": 600,  # 10 minutes
            "EvaluationPeriods": 1,
            "Threshold": 100,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, detail
| filter detail like /suppressed/
| stats count() as suppressed_count by bin(10m)
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "RateLimiting"},
                {"Key": "Severity", "Value": "Medium"}
            ]
        }
    
    def _create_log_volume_alert(self) -> Dict[str, Any]:
        """Create alert for unusual log volume."""
        return {
            "AlarmName": "TL-DW-Low-Log-Volume",
            "AlarmDescription": "Alert when log volume drops significantly (possible service issue)",
            "MetricName": "LogVolume",
            "Namespace": "TL-DW/System",
            "Statistic": "Sum",
            "Period": 600,  # 10 minutes
            "EvaluationPeriods": 2,  # 20 minutes total
            "Threshold": 10,  # Less than 10 log entries in 10 minutes
            "ComparisonOperator": "LessThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "breaching",  # Treat missing data as a problem
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp
| stats count() as log_count by bin(10m)
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "LogVolume"},
                {"Key": "Severity", "Value": "High"}
            ]
        }
    
    def _create_proxy_failure_alert(self) -> Dict[str, Any]:
        """Create alert for proxy failure rates."""
        return {
            "AlarmName": "TL-DW-Proxy-Failure-Rate",
            "AlarmDescription": "Alert when proxy usage has >30% failure rate",
            "MetricName": "ProxyFailureRate",
            "Namespace": "TL-DW/Proxy",
            "Statistic": "Average",
            "Period": 900,  # 15 minutes
            "EvaluationPeriods": 2,  # 30 minutes total
            "Threshold": 30.0,
            "ComparisonOperator": "GreaterThanThreshold",
            "AlarmActions": [self.sns_topic_arn] if self.sns_topic_arn else [],
            "TreatMissingData": "notBreaching",
            "LogInsightsQuery": f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, use_proxy, outcome
| filter event = "stage_result" and use_proxy = true
| stats countif(outcome in ["error", "timeout", "blocked"]) as failures, count(*) as total by bin(15m)
| eval failure_rate = failures * 100.0 / total
| sort @timestamp desc
''',
            "Tags": [
                {"Key": "Service", "Value": "TL-DW"},
                {"Key": "AlertType", "Value": "ProxyFailure"},
                {"Key": "Severity", "Value": "Medium"}
            ]
        }
    
    def create_all_alerts(self) -> List[Dict[str, Any]]:
        """Create all alert configurations."""
        all_alerts = []
        all_alerts.extend(self.create_error_rate_alerts())
        all_alerts.extend(self.create_performance_alerts())
        all_alerts.extend(self.create_system_health_alerts())
        return all_alerts
    
    def export_cloudformation_template(self) -> str:
        """Export alerts as CloudFormation template."""
        alerts = self.create_all_alerts()
        
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Description": "CloudWatch Alarms for TL;DW Application Monitoring",
            "Parameters": {
                "SNSTopicArn": {
                    "Type": "String",
                    "Description": "SNS Topic ARN for alert notifications",
                    "Default": self.sns_topic_arn or ""
                },
                "LogGroupName": {
                    "Type": "String",
                    "Description": "CloudWatch Log Group Name",
                    "Default": self.log_group_name
                }
            },
            "Resources": {}
        }
        
        for i, alert in enumerate(alerts):
            resource_name = f"Alarm{i+1}{alert['AlarmName'].replace('-', '').replace('_', '')}"
            template["Resources"][resource_name] = {
                "Type": "AWS::CloudWatch::Alarm",
                "Properties": {
                    k: v for k, v in alert.items() 
                    if k not in ["LogInsightsQuery", "Tags"]
                }
            }
            
            # Add tags if present
            if "Tags" in alert:
                template["Resources"][resource_name]["Properties"]["Tags"] = alert["Tags"]
        
        return json.dumps(template, indent=2)
    
    def export_terraform_config(self) -> str:
        """Export alerts as Terraform configuration."""
        alerts = self.create_all_alerts()
        
        terraform_config = []
        terraform_config.append('# CloudWatch Alarms for TL;DW Application')
        terraform_config.append('')
        
        for i, alert in enumerate(alerts):
            resource_name = alert['AlarmName'].lower().replace('-', '_').replace(' ', '_')
            
            terraform_config.append(f'resource "aws_cloudwatch_metric_alarm" "{resource_name}" {{')
            terraform_config.append(f'  alarm_name          = "{alert["AlarmName"]}"')
            terraform_config.append(f'  alarm_description   = "{alert["AlarmDescription"]}"')
            terraform_config.append(f'  metric_name         = "{alert["MetricName"]}"')
            terraform_config.append(f'  namespace           = "{alert["Namespace"]}"')
            terraform_config.append(f'  statistic           = "{alert["Statistic"]}"')
            terraform_config.append(f'  period              = {alert["Period"]}')
            terraform_config.append(f'  evaluation_periods  = {alert["EvaluationPeriods"]}')
            terraform_config.append(f'  threshold           = {alert["Threshold"]}')
            terraform_config.append(f'  comparison_operator = "{alert["ComparisonOperator"]}"')
            terraform_config.append(f'  treat_missing_data  = "{alert["TreatMissingData"]}"')
            
            if alert.get("AlarmActions"):
                terraform_config.append(f'  alarm_actions       = ["{alert["AlarmActions"][0]}"]')
            
            if alert.get("Tags"):
                terraform_config.append('  tags = {')
                for tag in alert["Tags"]:
                    terraform_config.append(f'    {tag["Key"]} = "{tag["Value"]}"')
                terraform_config.append('  }')
            
            terraform_config.append('}')
            terraform_config.append('')
        
        return '\n'.join(terraform_config)


# CLI interface for alert management
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CloudWatch alert configurations')
    parser.add_argument('--format', choices=['json', 'cloudformation', 'terraform'], default='json',
                       help='Output format')
    parser.add_argument('--log-group', default='/aws/apprunner/tldw-transcript-service',
                       help='CloudWatch log group name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--sns-topic', help='SNS topic ARN for notifications')
    parser.add_argument('--output', help='Output file')
    
    args = parser.parse_args()
    
    config = CloudWatchAlertsConfig(args.log_group, args.region, args.sns_topic)
    
    if args.format == 'json':
        output = json.dumps(config.create_all_alerts(), indent=2)
    elif args.format == 'cloudformation':
        output = config.export_cloudformation_template()
    elif args.format == 'terraform':
        output = config.export_terraform_config()
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Alert configuration written to {args.output}")
    else:
        print(output)