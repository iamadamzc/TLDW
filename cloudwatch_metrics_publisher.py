"""
CloudWatch Metrics Publisher for TL;DW Application

This module publishes custom metrics to CloudWatch based on structured log analysis.
Provides real-time metrics for stage success rates, performance, and system health.
"""

import boto3
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
from dataclasses import dataclass

from cloudwatch_logs_client import CloudWatchLogsClient
from cloudwatch_query_templates import QUERY_TEMPLATES


@dataclass
class MetricData:
    """Data structure for CloudWatch metric."""
    metric_name: str
    value: float
    unit: str
    dimensions: Dict[str, str]
    timestamp: datetime


class LogBasedMetricsCollector:
    """Collects metrics from structured logs for CloudWatch publishing."""
    
    def __init__(self, log_group_name: str = '/aws/apprunner/tldw-transcript-service', region: str = 'us-east-1'):
        self.log_group_name = log_group_name
        self.region = region
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.logs_client = CloudWatchLogsClient(log_group_name, region)
        self.logger = logging.getLogger(__name__)
        
        # Metric collection state
        self.last_collection_time = {}
        self.metric_cache = defaultdict(deque)
        self.collection_lock = threading.Lock()
    
    def collect_stage_success_rates(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect stage success rate metrics."""
        try:
            # Query for stage results in the time window
            query_result = self.logs_client.run_query(
                'stage_funnel_analysis',
                hours_back=1,  # Look back 1 hour but we'll filter to time window
                wait_for_completion=True
            )
            
            if query_result['status'] != 'Complete':
                self.logger.warning(f"Stage success rate query failed: {query_result.get('error')}")
                return []
            
            metrics = []
            current_time = datetime.utcnow()
            
            # Process query results
            for result_row in query_result.get('results', []):
                row_data = {field['field']: field.get('value', '') for field in result_row}
                
                stage = row_data.get('stage', 'unknown')
                success_pct = float(row_data.get('success_pct', 0))
                total_attempts = int(row_data.get('total', 0))
                
                if total_attempts > 0:  # Only publish metrics with actual data
                    # Success rate metric
                    metrics.append(MetricData(
                        metric_name='StageSuccessRate',
                        value=success_pct,
                        unit='Percent',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
                    
                    # Attempt count metric
                    metrics.append(MetricData(
                        metric_name='StageAttemptCount',
                        value=float(total_attempts),
                        unit='Count',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting stage success rates: {e}")
            return []
    
    def collect_performance_metrics(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect performance metrics from logs."""
        try:
            # Query for performance data
            query_result = self.logs_client.run_query(
                'performance_analysis',
                hours_back=1,
                wait_for_completion=True
            )
            
            if query_result['status'] != 'Complete':
                self.logger.warning(f"Performance metrics query failed: {query_result.get('error')}")
                return []
            
            metrics = []
            current_time = datetime.utcnow()
            
            # Process performance results
            for result_row in query_result.get('results', []):
                row_data = {field['field']: field.get('value', '') for field in result_row}
                
                stage = row_data.get('stage', 'unknown')
                avg_ms = float(row_data.get('avg_ms', 0))
                p95_ms = float(row_data.get('p95_ms', 0))
                p99_ms = float(row_data.get('p99_ms', 0))
                sample_count = int(row_data.get('sample_count', 0))
                
                if sample_count > 0:
                    # Average duration
                    metrics.append(MetricData(
                        metric_name='StageDurationAverage',
                        value=avg_ms,
                        unit='Milliseconds',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
                    
                    # P95 duration
                    metrics.append(MetricData(
                        metric_name='StageDurationP95',
                        value=p95_ms,
                        unit='Milliseconds',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
                    
                    # P99 duration
                    metrics.append(MetricData(
                        metric_name='StageDurationP99',
                        value=p99_ms,
                        unit='Milliseconds',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting performance metrics: {e}")
            return []
    
    def collect_error_rate_metrics(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect error rate metrics."""
        try:
            # Use the error rate query
            query_result = self.logs_client.run_query(
                'error_rate_by_stage',
                hours_back=1,
                wait_for_completion=True
            )
            
            if query_result['status'] != 'Complete':
                return []
            
            metrics = []
            current_time = datetime.utcnow()
            
            for result_row in query_result.get('results', []):
                row_data = {field['field']: field.get('value', '') for field in result_row}
                
                stage = row_data.get('stage', 'unknown')
                error_rate = float(row_data.get('error_rate', 0))
                errors = int(row_data.get('errors', 0))
                timeouts = int(row_data.get('timeouts', 0))
                total = int(row_data.get('total', 0))
                
                if total > 0:
                    # Overall error rate
                    metrics.append(MetricData(
                        metric_name='StageErrorRate',
                        value=error_rate,
                        unit='Percent',
                        dimensions={'Stage': stage},
                        timestamp=current_time
                    ))
                    
                    # Error count
                    metrics.append(MetricData(
                        metric_name='StageErrorCount',
                        value=float(errors),
                        unit='Count',
                        dimensions={'Stage': stage, 'ErrorType': 'Error'},
                        timestamp=current_time
                    ))
                    
                    # Timeout count
                    metrics.append(MetricData(
                        metric_name='StageErrorCount',
                        value=float(timeouts),
                        unit='Count',
                        dimensions={'Stage': stage, 'ErrorType': 'Timeout'},
                        timestamp=current_time
                    ))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting error rate metrics: {e}")
            return []
    
    def collect_job_metrics(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect job-level metrics."""
        try:
            # Query for job completion data
            query = f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, event, outcome
| filter @timestamp > @timestamp - {time_window_minutes}m
| filter event in ["job_received", "job_finished"]
| stats countif(event="job_received") as received, 
        countif(event="job_finished" and outcome="success") as completed_success,
        countif(event="job_finished" and outcome in ["failed", "error"]) as completed_failed,
        countif(event="job_finished" and outcome="partial_success") as completed_partial
'''
            
            response = self.cloudwatch_client.start_query(
                logGroupName=self.log_group_name,
                startTime=int((datetime.utcnow() - timedelta(minutes=time_window_minutes)).timestamp()),
                endTime=int(datetime.utcnow().timestamp()),
                queryString=query
            )
            
            # Wait for completion (simplified for this example)
            time.sleep(5)
            
            result = self.cloudwatch_client.get_query_results(queryId=response['queryId'])
            
            if result['status'] != 'Complete' or not result.get('results'):
                return []
            
            metrics = []
            current_time = datetime.utcnow()
            
            # Process first (and likely only) result row
            row_data = {field['field']: field.get('value', '0') for field in result['results'][0]}
            
            received = int(row_data.get('received', 0))
            completed_success = int(row_data.get('completed_success', 0))
            completed_failed = int(row_data.get('completed_failed', 0))
            completed_partial = int(row_data.get('completed_partial', 0))
            
            # Job throughput metrics
            metrics.append(MetricData(
                metric_name='JobsReceived',
                value=float(received),
                unit='Count',
                dimensions={},
                timestamp=current_time
            ))
            
            metrics.append(MetricData(
                metric_name='JobsCompleted',
                value=float(completed_success + completed_failed + completed_partial),
                unit='Count',
                dimensions={},
                timestamp=current_time
            ))
            
            # Job outcome metrics
            if completed_success > 0:
                metrics.append(MetricData(
                    metric_name='JobOutcome',
                    value=float(completed_success),
                    unit='Count',
                    dimensions={'Outcome': 'Success'},
                    timestamp=current_time
                ))
            
            if completed_failed > 0:
                metrics.append(MetricData(
                    metric_name='JobOutcome',
                    value=float(completed_failed),
                    unit='Count',
                    dimensions={'Outcome': 'Failed'},
                    timestamp=current_time
                ))
            
            if completed_partial > 0:
                metrics.append(MetricData(
                    metric_name='JobOutcome',
                    value=float(completed_partial),
                    unit='Count',
                    dimensions={'Outcome': 'Partial'},
                    timestamp=current_time
                ))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting job metrics: {e}")
            return []
    
    def collect_system_health_metrics(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect system health metrics."""
        try:
            # Query for system metrics
            query = f'''
SOURCE '{self.log_group_name}'
| fields @timestamp, event, cpu, mem_mb, detail
| filter @timestamp > @timestamp - {time_window_minutes}m
| filter event = "performance_metric" or detail like /suppressed/
| stats avg(cpu) as avg_cpu, max(cpu) as max_cpu, avg(mem_mb) as avg_mem_mb, max(mem_mb) as max_mem_mb,
        countif(detail like /suppressed/) as suppressed_count
'''
            
            response = self.cloudwatch_client.start_query(
                logGroupName=self.log_group_name,
                startTime=int((datetime.utcnow() - timedelta(minutes=time_window_minutes)).timestamp()),
                endTime=int(datetime.utcnow().timestamp()),
                queryString=query
            )
            
            time.sleep(5)  # Wait for completion
            
            result = self.cloudwatch_client.get_query_results(queryId=response['queryId'])
            
            if result['status'] != 'Complete' or not result.get('results'):
                return []
            
            metrics = []
            current_time = datetime.utcnow()
            
            row_data = {field['field']: field.get('value', '0') for field in result['results'][0]}
            
            avg_cpu = float(row_data.get('avg_cpu', 0))
            max_cpu = float(row_data.get('max_cpu', 0))
            avg_mem_mb = float(row_data.get('avg_mem_mb', 0))
            max_mem_mb = float(row_data.get('max_mem_mb', 0))
            suppressed_count = int(row_data.get('suppressed_count', 0))
            
            # CPU metrics
            if avg_cpu > 0:
                metrics.append(MetricData(
                    metric_name='CPUUtilization',
                    value=avg_cpu,
                    unit='Percent',
                    dimensions={'Statistic': 'Average'},
                    timestamp=current_time
                ))
                
                metrics.append(MetricData(
                    metric_name='CPUUtilization',
                    value=max_cpu,
                    unit='Percent',
                    dimensions={'Statistic': 'Maximum'},
                    timestamp=current_time
                ))
            
            # Memory metrics
            if avg_mem_mb > 0:
                metrics.append(MetricData(
                    metric_name='MemoryUtilization',
                    value=avg_mem_mb,
                    unit='Megabytes',
                    dimensions={'Statistic': 'Average'},
                    timestamp=current_time
                ))
                
                metrics.append(MetricData(
                    metric_name='MemoryUtilization',
                    value=max_mem_mb,
                    unit='Megabytes',
                    dimensions={'Statistic': 'Maximum'},
                    timestamp=current_time
                ))
            
            # Rate limiting metric
            metrics.append(MetricData(
                metric_name='RateLimitingSuppression',
                value=float(suppressed_count),
                unit='Count',
                dimensions={},
                timestamp=current_time
            ))
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error collecting system health metrics: {e}")
            return []
    
    def collect_all_metrics(self, time_window_minutes: int = 5) -> List[MetricData]:
        """Collect all available metrics."""
        all_metrics = []
        
        try:
            # Collect different metric types
            all_metrics.extend(self.collect_stage_success_rates(time_window_minutes))
            all_metrics.extend(self.collect_performance_metrics(time_window_minutes))
            all_metrics.extend(self.collect_error_rate_metrics(time_window_minutes))
            all_metrics.extend(self.collect_job_metrics(time_window_minutes))
            all_metrics.extend(self.collect_system_health_metrics(time_window_minutes))
            
            self.logger.info(f"Collected {len(all_metrics)} metrics from logs")
            
        except Exception as e:
            self.logger.error(f"Error collecting metrics: {e}")
        
        return all_metrics


class CloudWatchMetricsPublisher:
    """Publishes metrics to CloudWatch."""
    
    def __init__(self, namespace: str = 'TL-DW/Pipeline', region: str = 'us-east-1'):
        self.namespace = namespace
        self.region = region
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        self.logger = logging.getLogger(__name__)
        
        # Publishing state
        self.publish_queue = deque()
        self.publish_lock = threading.Lock()
        self.batch_size = 20  # CloudWatch limit
    
    def publish_metrics(self, metrics: List[MetricData]) -> bool:
        """Publish metrics to CloudWatch."""
        if not metrics:
            return True
        
        try:
            # Split into batches
            for i in range(0, len(metrics), self.batch_size):
                batch = metrics[i:i + self.batch_size]
                self._publish_batch(batch)
            
            self.logger.info(f"Published {len(metrics)} metrics to CloudWatch")
            return True
            
        except Exception as e:
            self.logger.error(f"Error publishing metrics: {e}")
            return False
    
    def _publish_batch(self, metrics: List[MetricData]):
        """Publish a batch of metrics."""
        metric_data = []
        
        for metric in metrics:
            metric_entry = {
                'MetricName': metric.metric_name,
                'Value': metric.value,
                'Unit': metric.unit,
                'Timestamp': metric.timestamp
            }
            
            if metric.dimensions:
                metric_entry['Dimensions'] = [
                    {'Name': name, 'Value': value}
                    for name, value in metric.dimensions.items()
                ]
            
            metric_data.append(metric_entry)
        
        # Publish to CloudWatch
        self.cloudwatch_client.put_metric_data(
            Namespace=self.namespace,
            MetricData=metric_data
        )


class MetricsCollectionScheduler:
    """Scheduler for periodic metrics collection and publishing."""
    
    def __init__(self, 
                 log_group_name: str = '/aws/apprunner/tldw-transcript-service',
                 namespace: str = 'TL-DW/Pipeline',
                 region: str = 'us-east-1',
                 collection_interval: int = 300):  # 5 minutes
        
        self.collector = LogBasedMetricsCollector(log_group_name, region)
        self.publisher = CloudWatchMetricsPublisher(namespace, region)
        self.collection_interval = collection_interval
        self.logger = logging.getLogger(__name__)
        
        self.running = False
        self.scheduler_thread = None
    
    def start(self):
        """Start the metrics collection scheduler."""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info(f"Started metrics collection scheduler (interval: {self.collection_interval}s)")
    
    def stop(self):
        """Stop the metrics collection scheduler."""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=10)
        
        self.logger.info("Stopped metrics collection scheduler")
    
    def _collection_loop(self):
        """Main collection loop."""
        while self.running:
            try:
                # Collect metrics
                metrics = self.collector.collect_all_metrics(
                    time_window_minutes=self.collection_interval // 60
                )
                
                # Publish metrics
                if metrics:
                    success = self.publisher.publish_metrics(metrics)
                    if not success:
                        self.logger.warning("Failed to publish some metrics")
                else:
                    self.logger.debug("No metrics collected in this interval")
                
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")
            
            # Wait for next collection
            time.sleep(self.collection_interval)
    
    def collect_and_publish_once(self) -> int:
        """Collect and publish metrics once (for testing/manual execution)."""
        try:
            metrics = self.collector.collect_all_metrics()
            if metrics:
                success = self.publisher.publish_metrics(metrics)
                if success:
                    return len(metrics)
            return 0
        except Exception as e:
            self.logger.error(f"Error in one-time collection: {e}")
            return 0


# CLI interface for metrics collection
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect and publish CloudWatch metrics from logs')
    parser.add_argument('--log-group', default='/aws/apprunner/tldw-transcript-service',
                       help='CloudWatch log group name')
    parser.add_argument('--namespace', default='TL-DW/Pipeline',
                       help='CloudWatch metrics namespace')
    parser.add_argument('--region', default='us-east-1',
                       help='AWS region')
    parser.add_argument('--interval', type=int, default=300,
                       help='Collection interval in seconds')
    parser.add_argument('--once', action='store_true',
                       help='Run collection once and exit')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon process')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scheduler = MetricsCollectionScheduler(
        args.log_group,
        args.namespace,
        args.region,
        args.interval
    )
    
    if args.once:
        # Run once and exit
        count = scheduler.collect_and_publish_once()
        print(f"Collected and published {count} metrics")
    elif args.daemon:
        # Run as daemon
        try:
            scheduler.start()
            print(f"Started metrics collection daemon (interval: {args.interval}s)")
            print("Press Ctrl+C to stop")
            
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping metrics collection...")
            scheduler.stop()
            print("Stopped")
    else:
        # Interactive mode
        scheduler.start()
        try:
            input("Metrics collection started. Press Enter to stop...\n")
        finally:
            scheduler.stop()