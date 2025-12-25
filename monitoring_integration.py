"""
Monitoring Integration for TL;DW Application

This module integrates all monitoring components including dashboards, alerts,
metrics collection, and validation. Provides a unified interface for monitoring setup.
"""

import json
import logging
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from cloudwatch_dashboard_config import CloudWatchDashboardConfig
from cloudwatch_alerts_config import CloudWatchAlertsConfig
from cloudwatch_metrics_publisher import MetricsCollectionScheduler
from cloudwatch_logs_client import CloudWatchLogsClient


class MonitoringIntegration:
    """Unified monitoring integration for TL;DW application."""
    
    def __init__(self, 
                 log_group_name: str = None,
                 region: str = 'us-east-1',
                 sns_topic_arn: str = None,
                 metrics_namespace: str = 'TL-DW/Pipeline'):
        
        # Use environment variables with fallbacks
        self.log_group_name = log_group_name or os.getenv(
            'CLOUDWATCH_LOG_GROUP', 
            '/aws/apprunner/tldw-transcript-service'
        )
        self.region = region
        self.sns_topic_arn = sns_topic_arn or os.getenv('SNS_TOPIC_ARN')
        self.metrics_namespace = metrics_namespace
        
        # Initialize components
        self.dashboard_config = CloudWatchDashboardConfig(self.log_group_name, self.region)
        self.alerts_config = CloudWatchAlertsConfig(self.log_group_name, self.region, self.sns_topic_arn)
        self.logs_client = CloudWatchLogsClient(self.log_group_name, self.region)
        self.metrics_scheduler = None
        
        self.logger = logging.getLogger(__name__)
    
    def setup_monitoring(self, 
                        enable_dashboards: bool = True,
                        enable_alerts: bool = True,
                        enable_metrics_collection: bool = True,
                        metrics_interval: int = 300) -> Dict[str, Any]:
        """Set up complete monitoring infrastructure."""
        
        setup_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'log_group': self.log_group_name,
            'region': self.region,
            'components': {}
        }
        
        try:
            # Set up dashboards
            if enable_dashboards:
                dashboard_result = self._setup_dashboards()
                setup_results['components']['dashboards'] = dashboard_result
            
            # Set up alerts
            if enable_alerts:
                alerts_result = self._setup_alerts()
                setup_results['components']['alerts'] = alerts_result
            
            # Set up metrics collection
            if enable_metrics_collection:
                metrics_result = self._setup_metrics_collection(metrics_interval)
                setup_results['components']['metrics_collection'] = metrics_result
            
            setup_results['status'] = 'success'
            setup_results['message'] = 'Monitoring setup completed successfully'
            
            self.logger.info(f"Monitoring setup completed for log group: {self.log_group_name}")
            
        except Exception as e:
            setup_results['status'] = 'error'
            setup_results['error'] = str(e)
            self.logger.error(f"Error setting up monitoring: {e}")
        
        return setup_results
    
    def _setup_dashboards(self) -> Dict[str, Any]:
        """Set up CloudWatch dashboards."""
        try:
            # Generate dashboard configurations
            main_dashboard = self.dashboard_config.create_main_dashboard()
            performance_dashboard = self.dashboard_config.create_performance_dashboard()
            error_dashboard = self.dashboard_config.create_error_analysis_dashboard()
            
            dashboard_configs = {
                'main': main_dashboard,
                'performance': performance_dashboard,
                'errors': error_dashboard
            }
            
            # Export configurations for deployment
            export_dir = 'monitoring_exports/dashboards'
            os.makedirs(export_dir, exist_ok=True)
            
            for name, config in dashboard_configs.items():
                export_path = os.path.join(export_dir, f'{name}_dashboard.json')
                with open(export_path, 'w') as f:
                    json.dump(config, f, indent=2)
            
            return {
                'status': 'success',
                'dashboards_created': len(dashboard_configs),
                'export_directory': export_dir,
                'dashboard_urls': {
                    name: self.dashboard_config.get_dashboard_url(f'tldw-{name}')
                    for name in dashboard_configs.keys()
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _setup_alerts(self) -> Dict[str, Any]:
        """Set up CloudWatch alerts."""
        try:
            # Generate alert configurations
            all_alerts = self.alerts_config.create_all_alerts()
            
            # Export configurations for deployment
            export_dir = 'monitoring_exports/alerts'
            os.makedirs(export_dir, exist_ok=True)
            
            # Export as JSON
            json_path = os.path.join(export_dir, 'alerts.json')
            with open(json_path, 'w') as f:
                json.dump(all_alerts, f, indent=2)
            
            # Export as CloudFormation template
            cf_path = os.path.join(export_dir, 'alerts_cloudformation.json')
            with open(cf_path, 'w') as f:
                f.write(self.alerts_config.export_cloudformation_template())
            
            # Export as Terraform configuration
            tf_path = os.path.join(export_dir, 'alerts.tf')
            with open(tf_path, 'w') as f:
                f.write(self.alerts_config.export_terraform_config())
            
            return {
                'status': 'success',
                'alerts_created': len(all_alerts),
                'export_directory': export_dir,
                'exports': {
                    'json': json_path,
                    'cloudformation': cf_path,
                    'terraform': tf_path
                },
                'sns_topic_configured': bool(self.sns_topic_arn)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _setup_metrics_collection(self, interval: int = 300) -> Dict[str, Any]:
        """Set up metrics collection scheduler."""
        try:
            self.metrics_scheduler = MetricsCollectionScheduler(
                log_group_name=self.log_group_name,
                namespace=self.metrics_namespace,
                region=self.region,
                collection_interval=interval
            )
            
            # Test collection once to validate setup
            test_count = self.metrics_scheduler.collect_and_publish_once()
            
            return {
                'status': 'success',
                'collection_interval': interval,
                'namespace': self.metrics_namespace,
                'test_metrics_collected': test_count,
                'scheduler_ready': True
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def start_metrics_collection(self) -> bool:
        """Start the metrics collection scheduler."""
        if not self.metrics_scheduler:
            self.logger.error("Metrics scheduler not initialized. Run setup_monitoring first.")
            return False
        
        try:
            self.metrics_scheduler.start()
            self.logger.info("Started metrics collection scheduler")
            return True
        except Exception as e:
            self.logger.error(f"Error starting metrics collection: {e}")
            return False
    
    def stop_metrics_collection(self) -> bool:
        """Stop the metrics collection scheduler."""
        if not self.metrics_scheduler:
            return True
        
        try:
            self.metrics_scheduler.stop()
            self.logger.info("Stopped metrics collection scheduler")
            return True
        except Exception as e:
            self.logger.error(f"Error stopping metrics collection: {e}")
            return False
    
    def validate_monitoring_setup(self) -> Dict[str, Any]:
        """Validate that monitoring components are working correctly."""
        validation_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'components': {},
            'overall_status': 'unknown'
        }
        
        try:
            # Validate CloudWatch Logs access
            logs_validation = self._validate_logs_access()
            validation_results['components']['logs'] = logs_validation
            
            # Validate query templates
            queries_validation = self._validate_query_templates()
            validation_results['components']['queries'] = queries_validation
            
            # Validate dashboard configurations
            dashboard_validation = self._validate_dashboard_configs()
            validation_results['components']['dashboards'] = dashboard_validation
            
            # Validate alert configurations
            alerts_validation = self._validate_alert_configs()
            validation_results['components']['alerts'] = alerts_validation
            
            # Validate metrics collection
            metrics_validation = self._validate_metrics_collection()
            validation_results['components']['metrics'] = metrics_validation
            
            # Determine overall status
            component_statuses = [
                comp.get('status') for comp in validation_results['components'].values()
            ]
            
            if all(status == 'healthy' for status in component_statuses):
                validation_results['overall_status'] = 'healthy'
            elif any(status == 'error' for status in component_statuses):
                validation_results['overall_status'] = 'error'
            else:
                validation_results['overall_status'] = 'degraded'
            
        except Exception as e:
            validation_results['overall_status'] = 'error'
            validation_results['error'] = str(e)
        
        return validation_results
    
    def _validate_logs_access(self) -> Dict[str, Any]:
        """Validate CloudWatch Logs access."""
        try:
            # Try to run a simple query
            result = self.logs_client.run_query(
                'recent_activity',
                hours_back=1,
                wait_for_completion=True,
                max_wait_seconds=30
            )
            
            if result['status'] == 'Complete':
                return {
                    'status': 'healthy',
                    'message': 'CloudWatch Logs access working',
                    'query_time': result.get('statistics', {}).get('recordsMatched', 0)
                }
            else:
                return {
                    'status': 'error',
                    'message': f"Query failed: {result.get('error', 'Unknown error')}"
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f"CloudWatch Logs access failed: {str(e)}"
            }
    
    def _validate_query_templates(self) -> Dict[str, Any]:
        """Validate query templates."""
        try:
            from cloudwatch_query_templates import QUERY_TEMPLATES
            
            # Check that required templates exist
            required_templates = [
                'error_analysis', 'funnel_analysis', 'performance_analysis',
                'job_correlation', 'video_correlation'
            ]
            
            missing_templates = [
                template for template in required_templates
                if template not in QUERY_TEMPLATES
            ]
            
            if missing_templates:
                return {
                    'status': 'error',
                    'message': f"Missing query templates: {missing_templates}"
                }
            
            return {
                'status': 'healthy',
                'message': f"All {len(QUERY_TEMPLATES)} query templates available",
                'template_count': len(QUERY_TEMPLATES)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Query template validation failed: {str(e)}"
            }
    
    def _validate_dashboard_configs(self) -> Dict[str, Any]:
        """Validate dashboard configurations."""
        try:
            # Test dashboard generation
            main_dashboard = self.dashboard_config.create_main_dashboard()
            perf_dashboard = self.dashboard_config.create_performance_dashboard()
            error_dashboard = self.dashboard_config.create_error_analysis_dashboard()
            
            total_widgets = (
                len(main_dashboard.get('widgets', [])) +
                len(perf_dashboard.get('widgets', [])) +
                len(error_dashboard.get('widgets', []))
            )
            
            return {
                'status': 'healthy',
                'message': 'Dashboard configurations valid',
                'dashboards_count': 3,
                'total_widgets': total_widgets
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Dashboard validation failed: {str(e)}"
            }
    
    def _validate_alert_configs(self) -> Dict[str, Any]:
        """Validate alert configurations."""
        try:
            # Test alert generation
            all_alerts = self.alerts_config.create_all_alerts()
            
            # Check alert structure
            for alert in all_alerts[:3]:  # Check first few alerts
                required_fields = ['AlarmName', 'AlarmDescription', 'Threshold', 'ComparisonOperator']
                missing_fields = [field for field in required_fields if field not in alert]
                
                if missing_fields:
                    return {
                        'status': 'error',
                        'message': f"Alert missing fields: {missing_fields}"
                    }
            
            return {
                'status': 'healthy',
                'message': 'Alert configurations valid',
                'alerts_count': len(all_alerts),
                'sns_configured': bool(self.sns_topic_arn)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Alert validation failed: {str(e)}"
            }
    
    def _validate_metrics_collection(self) -> Dict[str, Any]:
        """Validate metrics collection."""
        try:
            if not self.metrics_scheduler:
                # Create temporary scheduler for validation
                temp_scheduler = MetricsCollectionScheduler(
                    log_group_name=self.log_group_name,
                    namespace=self.metrics_namespace,
                    region=self.region
                )
            else:
                temp_scheduler = self.metrics_scheduler
            
            # Test metrics collection
            metrics_count = temp_scheduler.collect_and_publish_once()
            
            return {
                'status': 'healthy',
                'message': 'Metrics collection working',
                'test_metrics_collected': metrics_count,
                'namespace': self.metrics_namespace
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Metrics collection validation failed: {str(e)}"
            }
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'configuration': {
                'log_group': self.log_group_name,
                'region': self.region,
                'metrics_namespace': self.metrics_namespace,
                'sns_topic_configured': bool(self.sns_topic_arn)
            },
            'components': {
                'metrics_scheduler_running': (
                    self.metrics_scheduler.running if self.metrics_scheduler else False
                ),
                'dashboard_config_ready': bool(self.dashboard_config),
                'alerts_config_ready': bool(self.alerts_config),
                'logs_client_ready': bool(self.logs_client)
            }
        }
    
    def export_monitoring_config(self, output_dir: str = 'monitoring_exports') -> Dict[str, Any]:
        """Export all monitoring configurations for deployment."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            export_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'output_directory': output_dir,
                'exports': {}
            }
            
            # Export dashboards
            dashboards_dir = os.path.join(output_dir, 'dashboards')
            os.makedirs(dashboards_dir, exist_ok=True)
            
            dashboard_types = ['main', 'performance', 'errors']
            for dashboard_type in dashboard_types:
                config_json = self.dashboard_config.export_dashboard_json(dashboard_type)
                export_path = os.path.join(dashboards_dir, f'{dashboard_type}_dashboard.json')
                with open(export_path, 'w') as f:
                    f.write(config_json)
                export_results['exports'][f'{dashboard_type}_dashboard'] = export_path
            
            # Export alerts
            alerts_dir = os.path.join(output_dir, 'alerts')
            os.makedirs(alerts_dir, exist_ok=True)
            
            # JSON format
            alerts_json_path = os.path.join(alerts_dir, 'alerts.json')
            with open(alerts_json_path, 'w') as f:
                json.dump(self.alerts_config.create_all_alerts(), f, indent=2)
            export_results['exports']['alerts_json'] = alerts_json_path
            
            # CloudFormation format
            cf_path = os.path.join(alerts_dir, 'alerts_cloudformation.json')
            with open(cf_path, 'w') as f:
                f.write(self.alerts_config.export_cloudformation_template())
            export_results['exports']['alerts_cloudformation'] = cf_path
            
            # Terraform format
            tf_path = os.path.join(alerts_dir, 'alerts.tf')
            with open(tf_path, 'w') as f:
                f.write(self.alerts_config.export_terraform_config())
            export_results['exports']['alerts_terraform'] = tf_path
            
            # Export deployment guide
            guide_path = os.path.join(output_dir, 'DEPLOYMENT_GUIDE.md')
            with open(guide_path, 'w') as f:
                f.write(self._generate_deployment_guide())
            export_results['exports']['deployment_guide'] = guide_path
            
            export_results['status'] = 'success'
            export_results['message'] = f"Monitoring configuration exported to {output_dir}"
            
            return export_results
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_deployment_guide(self) -> str:
        """Generate deployment guide for monitoring setup."""
        return f"""# TL;DW Monitoring Deployment Guide

## Overview

This directory contains the complete monitoring configuration for the TL;DW application,
including CloudWatch dashboards, alerts, and metrics collection setup.

## Configuration

- **Log Group**: `{self.log_group_name}`
- **Region**: `{self.region}`
- **Metrics Namespace**: `{self.metrics_namespace}`
- **SNS Topic**: `{self.sns_topic_arn or 'Not configured'}`

## Deployment Steps

### 1. Deploy Dashboards

Import the dashboard JSON files into CloudWatch:

```bash
# Using AWS CLI
aws cloudwatch put-dashboard --dashboard-name "TL-DW-Main" --dashboard-body file://dashboards/main_dashboard.json
aws cloudwatch put-dashboard --dashboard-name "TL-DW-Performance" --dashboard-body file://dashboards/performance_dashboard.json
aws cloudwatch put-dashboard --dashboard-name "TL-DW-Errors" --dashboard-body file://dashboards/errors_dashboard.json
```

### 2. Deploy Alerts

#### Option A: CloudFormation
```bash
aws cloudformation deploy --template-body file://alerts/alerts_cloudformation.json --stack-name tldw-monitoring-alerts --parameter-overrides SNSTopicArn={self.sns_topic_arn or 'YOUR_SNS_TOPIC_ARN'}
```

#### Option B: Terraform
```bash
cd alerts
terraform init
terraform plan
terraform apply
```

### 3. Set Up Metrics Collection

Deploy the metrics collection scheduler as a background service or Lambda function.

#### Environment Variables Required:
- `CLOUDWATCH_LOG_GROUP`: `{self.log_group_name}`
- `AWS_REGION`: `{self.region}`
- `METRICS_NAMESPACE`: `{self.metrics_namespace}`

### 4. Configure SNS Topic (if not already done)

Create an SNS topic for alert notifications:

```bash
aws sns create-topic --name tldw-monitoring-alerts
aws sns subscribe --topic-arn YOUR_TOPIC_ARN --protocol email --notification-endpoint your-email@example.com
```

## Validation

Run the monitoring validation to ensure everything is working:

```python
from monitoring_integration import MonitoringIntegration

monitor = MonitoringIntegration()
validation_result = monitor.validate_monitoring_setup()
print(validation_result)
```

## Dashboard URLs

After deployment, access your dashboards at:
- Main Dashboard: https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=TL-DW-Main
- Performance Dashboard: https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=TL-DW-Performance
- Error Analysis Dashboard: https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name=TL-DW-Errors

## Troubleshooting

1. **No data in dashboards**: Ensure the log group name is correct and logs are being generated
2. **Alerts not firing**: Check SNS topic configuration and alert thresholds
3. **Metrics not publishing**: Verify IAM permissions for CloudWatch metrics publishing

## Support

For issues with monitoring setup, check the validation results and ensure all AWS permissions are correctly configured.
"""


# CLI interface for monitoring integration
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='TL;DW Monitoring Integration')
    parser.add_argument('--setup', action='store_true', help='Set up monitoring infrastructure')
    parser.add_argument('--validate', action='store_true', help='Validate monitoring setup')
    parser.add_argument('--export', help='Export monitoring config to directory')
    parser.add_argument('--start-metrics', action='store_true', help='Start metrics collection')
    parser.add_argument('--stop-metrics', action='store_true', help='Stop metrics collection')
    parser.add_argument('--status', action='store_true', help='Show monitoring status')
    parser.add_argument('--log-group', help='CloudWatch log group name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')
    parser.add_argument('--sns-topic', help='SNS topic ARN for alerts')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize monitoring integration
    monitor = MonitoringIntegration(
        log_group_name=args.log_group,
        region=args.region,
        sns_topic_arn=args.sns_topic
    )
    
    if args.setup:
        print("Setting up monitoring infrastructure...")
        result = monitor.setup_monitoring()
        print(json.dumps(result, indent=2))
    
    elif args.validate:
        print("Validating monitoring setup...")
        result = monitor.validate_monitoring_setup()
        print(json.dumps(result, indent=2))
    
    elif args.export:
        print(f"Exporting monitoring configuration to {args.export}...")
        result = monitor.export_monitoring_config(args.export)
        print(json.dumps(result, indent=2))
    
    elif args.start_metrics:
        print("Starting metrics collection...")
        success = monitor.start_metrics_collection()
        print(f"Metrics collection started: {success}")
        if success:
            try:
                print("Press Ctrl+C to stop...")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                monitor.stop_metrics_collection()
                print("Metrics collection stopped")
    
    elif args.stop_metrics:
        print("Stopping metrics collection...")
        success = monitor.stop_metrics_collection()
        print(f"Metrics collection stopped: {success}")
    
    elif args.status:
        print("Monitoring status:")
        status = monitor.get_monitoring_status()
        print(json.dumps(status, indent=2))
    
    else:
        parser.print_help()