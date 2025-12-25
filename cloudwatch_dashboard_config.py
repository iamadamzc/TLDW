"""
CloudWatch Dashboard Configuration for TL;DW Application

This module provides dashboard configurations optimized for the structured JSON logging format.
Creates comprehensive monitoring dashboards for error rates, performance metrics, and system health.
"""

import json
from typing import Dict, List, Any
from datetime import datetime


class CloudWatchDashboardConfig:
    """Configuration generator for CloudWatch dashboards."""
    
    def __init__(self, log_group_name: str = '/aws/apprunner/tldw-transcript-service', region: str = 'us-east-1'):
        self.log_group_name = log_group_name
        self.region = region
    
    def create_main_dashboard(self) -> Dict[str, Any]:
        """Create the main operational dashboard."""
        return {
            "widgets": [
                self._create_error_rate_widget(),
                self._create_stage_success_rates_widget(),
                self._create_performance_metrics_widget(),
                self._create_recent_errors_widget(),
                self._create_job_throughput_widget(),
                self._create_proxy_effectiveness_widget(),
                self._create_system_health_widget(),
                self._create_alert_summary_widget()
            ]
        }
    
    def create_performance_dashboard(self) -> Dict[str, Any]:
        """Create performance-focused dashboard."""
        return {
            "widgets": [
                self._create_stage_duration_heatmap(),
                self._create_p95_duration_trends(),
                self._create_timeout_analysis_widget(),
                self._create_performance_by_profile_widget(),
                self._create_ffmpeg_performance_widget(),
                self._create_memory_usage_widget()
            ]
        }
    
    def create_error_analysis_dashboard(self) -> Dict[str, Any]:
        """Create error analysis dashboard."""
        return {
            "widgets": [
                self._create_error_timeline_widget(),
                self._create_error_breakdown_widget(),
                self._create_failed_jobs_widget(),
                self._create_circuit_breaker_widget(),
                self._create_rate_limiting_widget(),
                self._create_error_correlation_widget()
            ]
        }
    
    def _create_error_rate_widget(self) -> Dict[str, Any]:
        """Create error rate monitoring widget."""
        return {
            "type": "log",
            "x": 0, "y": 0,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, stage, outcome
| filter event = "stage_result"
| stats countif(outcome="error") as errors, countif(outcome="timeout") as timeouts, count(*) as total by bin(5m)
| eval error_rate = round((errors + timeouts) * 100.0 / total, 2)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Error Rate Over Time",
                "view": "table"
            }
        }
    
    def _create_stage_success_rates_widget(self) -> Dict[str, Any]:
        """Create stage success rates widget."""
        return {
            "type": "log",
            "x": 12, "y": 0,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields stage, outcome
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result"
| stats countif(outcome="success") as success, count(*) as total by stage
| eval success_rate = round(success * 100.0 / total, 2)
| sort success_rate asc
''',
                "region": self.region,
                "title": "Stage Success Rates (Last Hour)",
                "view": "table"
            }
        }
    
    def _create_performance_metrics_widget(self) -> Dict[str, Any]:
        """Create performance metrics widget."""
        return {
            "type": "log",
            "x": 0, "y": 6,
            "width": 24, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by bin(5m), stage
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Performance Metrics by Stage",
                "view": "table"
            }
        }
    
    def _create_recent_errors_widget(self) -> Dict[str, Any]:
        """Create recent errors widget."""
        return {
            "type": "log",
            "x": 0, "y": 12,
            "width": 24, "height": 8,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, lvl, stage, outcome, detail, job_id, video_id, attempt, use_proxy
| filter @timestamp > @timestamp - 1h
| filter outcome in ["error", "timeout", "blocked"]
| sort @timestamp desc
| limit 50
''',
                "region": self.region,
                "title": "Recent Errors (Last Hour)",
                "view": "table"
            }
        }
    
    def _create_job_throughput_widget(self) -> Dict[str, Any]:
        """Create job throughput widget."""
        return {
            "type": "log",
            "x": 0, "y": 20,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, event, outcome
| filter event in ["job_received", "job_finished"]
| stats countif(event="job_received") as received, countif(event="job_finished") as finished by bin(10m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Job Throughput",
                "view": "table"
            }
        }
    
    def _create_proxy_effectiveness_widget(self) -> Dict[str, Any]:
        """Create proxy effectiveness widget."""
        return {
            "type": "log",
            "x": 12, "y": 20,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields use_proxy, outcome, stage
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result" and ispresent(use_proxy)
| stats countif(outcome="success") as success, count(*) as total by use_proxy, stage
| eval success_rate = round(success * 100.0 / total, 2)
| sort stage, use_proxy
''',
                "region": self.region,
                "title": "Proxy Effectiveness (Last Hour)",
                "view": "table"
            }
        }
    
    def _create_system_health_widget(self) -> Dict[str, Any]:
        """Create system health widget."""
        return {
            "type": "log",
            "x": 0, "y": 26,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, event, cpu, mem_mb
| filter event = "performance_metric"
| stats avg(cpu) as avg_cpu, avg(mem_mb) as avg_mem_mb by bin(5m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "System Resource Usage",
                "view": "table"
            }
        }
    
    def _create_alert_summary_widget(self) -> Dict[str, Any]:
        """Create alert summary widget."""
        return {
            "type": "log",
            "x": 12, "y": 26,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, lvl, event, stage, detail
| filter @timestamp > @timestamp - 1h
| filter lvl in ["ERROR", "CRITICAL"] or detail like /suppressed/
| stats count() as alert_count by lvl, bin(10m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Alert Activity (Last Hour)",
                "view": "table"
            }
        }
    
    def _create_stage_duration_heatmap(self) -> Dict[str, Any]:
        """Create stage duration heatmap widget."""
        return {
            "type": "log",
            "x": 0, "y": 0,
            "width": 24, "height": 8,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats pct(dur_ms, 50) as p50, pct(dur_ms, 95) as p95, pct(dur_ms, 99) as p99 by bin(10m), stage
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Stage Duration Heatmap",
                "view": "table"
            }
        }
    
    def _create_p95_duration_trends(self) -> Dict[str, Any]:
        """Create P95 duration trends widget."""
        return {
            "type": "log",
            "x": 0, "y": 8,
            "width": 24, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, stage, dur_ms
| filter event = "stage_result" and ispresent(dur_ms) and dur_ms > 0
| stats pct(dur_ms, 95) as p95_ms by bin(5m), stage
| sort @timestamp desc
''',
                "region": self.region,
                "title": "P95 Duration Trends by Stage",
                "view": "table"
            }
        }
    
    def _create_timeout_analysis_widget(self) -> Dict[str, Any]:
        """Create timeout analysis widget."""
        return {
            "type": "log",
            "x": 0, "y": 14,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields stage, dur_ms, detail
| filter @timestamp > @timestamp - 6h
| filter outcome = "timeout"
| stats avg(dur_ms) as avg_timeout_ms, count() as timeout_count by stage
| sort timeout_count desc
''',
                "region": self.region,
                "title": "Timeout Analysis (Last 6 Hours)",
                "view": "table"
            }
        }
    
    def _create_performance_by_profile_widget(self) -> Dict[str, Any]:
        """Create performance by profile widget."""
        return {
            "type": "log",
            "x": 12, "y": 14,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields profile, stage, dur_ms
| filter @timestamp > @timestamp - 1h
| filter event = "stage_result" and ispresent(profile) and ispresent(dur_ms)
| stats avg(dur_ms) as avg_ms, pct(dur_ms, 95) as p95_ms by profile, stage
| sort p95_ms desc
''',
                "region": self.region,
                "title": "Performance by Browser Profile",
                "view": "table"
            }
        }
    
    def _create_ffmpeg_performance_widget(self) -> Dict[str, Any]:
        """Create FFmpeg performance widget."""
        return {
            "type": "log",
            "x": 0, "y": 20,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, outcome, dur_ms, detail
| filter @timestamp > @timestamp - 1h
| filter stage = "ffmpeg"
| stats countif(outcome="success") as success, countif(outcome="error") as errors, avg(dur_ms) as avg_ms by bin(10m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "FFmpeg Performance (Last Hour)",
                "view": "table"
            }
        }
    
    def _create_memory_usage_widget(self) -> Dict[str, Any]:
        """Create memory usage widget."""
        return {
            "type": "log",
            "x": 12, "y": 20,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, cpu, mem_mb
| filter event = "performance_metric"
| stats avg(cpu) as avg_cpu, max(cpu) as max_cpu, avg(mem_mb) as avg_mem_mb, max(mem_mb) as max_mem_mb by bin(5m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Resource Usage Trends",
                "view": "table"
            }
        }
    
    def _create_error_timeline_widget(self) -> Dict[str, Any]:
        """Create error timeline widget."""
        return {
            "type": "log",
            "x": 0, "y": 0,
            "width": 24, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, stage, outcome
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by bin(5m), stage, outcome
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Error Timeline by Stage and Type",
                "view": "table"
            }
        }
    
    def _create_error_breakdown_widget(self) -> Dict[str, Any]:
        """Create error breakdown widget."""
        return {
            "type": "log",
            "x": 0, "y": 6,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields stage, outcome, detail
| filter @timestamp > @timestamp - 6h
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by stage, outcome, detail
| sort error_count desc
| limit 20
''',
                "region": self.region,
                "title": "Top Error Patterns (Last 6 Hours)",
                "view": "table"
            }
        }
    
    def _create_failed_jobs_widget(self) -> Dict[str, Any]:
        """Create failed jobs widget."""
        return {
            "type": "log",
            "x": 12, "y": 6,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, job_id, video_id, outcome, detail
| filter @timestamp > @timestamp - 6h
| filter event = "job_finished" and outcome in ["failed", "error"]
| sort @timestamp desc
| limit 20
''',
                "region": self.region,
                "title": "Recent Failed Jobs (Last 6 Hours)",
                "view": "table"
            }
        }
    
    def _create_circuit_breaker_widget(self) -> Dict[str, Any]:
        """Create circuit breaker widget."""
        return {
            "type": "log",
            "x": 0, "y": 12,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, event, detail
| filter event like /circuit_breaker/ or detail like /circuit.*breaker/
| sort @timestamp desc
| limit 50
''',
                "region": self.region,
                "title": "Circuit Breaker Events",
                "view": "table"
            }
        }
    
    def _create_rate_limiting_widget(self) -> Dict[str, Any]:
        """Create rate limiting widget."""
        return {
            "type": "log",
            "x": 12, "y": 12,
            "width": 12, "height": 6,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, event, stage, detail
| filter detail like /suppressed/
| stats count() as suppressed_count by bin(1m)
| sort @timestamp desc
''',
                "region": self.region,
                "title": "Rate Limiting Activity",
                "view": "table"
            }
        }
    
    def _create_error_correlation_widget(self) -> Dict[str, Any]:
        """Create error correlation widget."""
        return {
            "type": "log",
            "x": 0, "y": 18,
            "width": 24, "height": 8,
            "properties": {
                "query": f"SOURCE '{self.log_group_name}'\n" + '''
fields @timestamp, job_id, video_id, stage, outcome, detail, use_proxy, profile
| filter @timestamp > @timestamp - 1h
| filter outcome in ["error", "timeout", "blocked"]
| stats count() as error_count by job_id, video_id
| sort error_count desc
| limit 10
''',
                "region": self.region,
                "title": "Error Correlation by Job/Video (Last Hour)",
                "view": "table"
            }
        }
    
    def export_dashboard_json(self, dashboard_type: str = "main") -> str:
        """Export dashboard configuration as JSON."""
        if dashboard_type == "main":
            config = self.create_main_dashboard()
        elif dashboard_type == "performance":
            config = self.create_performance_dashboard()
        elif dashboard_type == "errors":
            config = self.create_error_analysis_dashboard()
        else:
            raise ValueError(f"Unknown dashboard type: {dashboard_type}")
        
        return json.dumps(config, indent=2)
    
    def get_dashboard_url(self, dashboard_name: str) -> str:
        """Get CloudWatch dashboard URL."""
        return f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard_name}"


# CLI interface for dashboard management
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate CloudWatch dashboard configurations')
    parser.add_argument('--type', choices=['main', 'performance', 'errors'], default='main',
                       help='Dashboard type to generate')
    parser.add_argument('--log-group', default='/aws/apprunner/tldw-transcript-service',
                       help='CloudWatch log group name')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--output', help='Output file for dashboard JSON')
    
    args = parser.parse_args()
    
    config = CloudWatchDashboardConfig(args.log_group, args.region)
    dashboard_json = config.export_dashboard_json(args.type)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(dashboard_json)
        print(f"Dashboard configuration written to {args.output}")
    else:
        print(dashboard_json)