#!/usr/bin/env python3
"""
Staging log validation script for structured JSON logging migration.
Validates log output format and CloudWatch Logs Insights query functionality.
"""

import json
import time
import boto3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Configure basic logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StagingLogValidator:
    """Validates staging deployment log output and query functionality."""
    
    def __init__(self, region: str = "us-west-2", log_group: str = "/aws/apprunner/tldw-transcript-service-staging"):
        self.region = region
        self.log_group = log_group
        self.logs_client = boto3.client('logs', region_name=region)
        
    def validate_log_group_exists(self) -> bool:
        """Validate that the staging log group exists."""
        try:
            response = self.logs_client.describe_log_groups(
                logGroupNamePrefix=self.log_group
            )
            
            for group in response['logGroups']:
                if group['logGroupName'] == self.log_group:
                    logger.info(f"✅ Log group exists: {self.log_group}")
                    logger.info(f"   Retention: {group.get('retentionInDays', 'Never expire')} days")
                    return True
            
            logger.error(f"❌ Log group not found: {self.log_group}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking log group: {e}")
            return False
    
    def get_recent_log_events(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Get recent log events from the staging log group."""
        try:
            # Get log streams
            streams_response = self.logs_client.describe_log_streams(
                logGroupName=self.log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=10
            )
            
            if not streams_response['logStreams']:
                logger.warning("⚠️  No log streams found")
                return []
            
            # Get events from the most recent stream
            stream_name = streams_response['logStreams'][0]['logStreamName']
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=minutes)
            
            events_response = self.logs_client.get_log_events(
                logGroupName=self.log_group,
                logStreamName=stream_name,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                limit=100
            )
            
            logger.info(f"✅ Retrieved {len(events_response['events'])} log events from last {minutes} minutes")
            return events_response['events']
            
        except Exception as e:
            logger.error(f"❌ Error retrieving log events: {e}")
            return []
    
    def validate_json_format(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate that log events are in proper JSON format."""
        validation_results = {
            'total_events': len(events),
            'json_events': 0,
            'non_json_events': 0,
            'valid_schema_events': 0,
            'schema_errors': [],
            'sample_events': []
        }
        
        required_fields = ['ts', 'lvl']
        optional_fields = ['job_id', 'video_id', 'stage', 'event', 'outcome', 'dur_ms', 'detail']
        
        for event in events:
            message = event['message']
            
            try:
                # Try to parse as JSON
                log_data = json.loads(message)
                validation_results['json_events'] += 1
                
                # Validate schema
                has_required = all(field in log_data for field in required_fields)
                
                if has_required:
                    validation_results['valid_schema_events'] += 1
                    
                    # Store sample for inspection
                    if len(validation_results['sample_events']) < 5:
                        validation_results['sample_events'].append(log_data)
                else:
                    missing_fields = [f for f in required_fields if f not in log_data]
                    validation_results['schema_errors'].append(f"Missing fields: {missing_fields}")
                
            except json.JSONDecodeError:
                validation_results['non_json_events'] += 1
                # Store sample non-JSON for inspection
                if len(validation_results.get('non_json_samples', [])) < 3:
                    validation_results.setdefault('non_json_samples', []).append(message[:200])
        
        # Calculate percentages
        if validation_results['total_events'] > 0:
            json_pct = (validation_results['json_events'] / validation_results['total_events']) * 100
            schema_pct = (validation_results['valid_schema_events'] / validation_results['total_events']) * 100
            
            logger.info(f"📊 JSON Format Validation Results:")
            logger.info(f"   Total events: {validation_results['total_events']}")
            logger.info(f"   JSON events: {validation_results['json_events']} ({json_pct:.1f}%)")
            logger.info(f"   Valid schema: {validation_results['valid_schema_events']} ({schema_pct:.1f}%)")
            
            if validation_results['non_json_events'] > 0:
                logger.warning(f"⚠️  Non-JSON events: {validation_results['non_json_events']}")
            
            if validation_results['schema_errors']:
                logger.warning(f"⚠️  Schema errors: {len(validation_results['schema_errors'])}")
        
        return validation_results
    
    def test_cloudwatch_queries(self) -> Dict[str, Any]:
        """Test CloudWatch Logs Insights queries."""
        query_results = {}
        
        # Define test queries
        test_queries = {
            'basic_fields': {
                'query': 'fields @timestamp, lvl, event, stage | limit 10',
                'description': 'Basic field extraction'
            },
            'error_analysis': {
                'query': 'fields @timestamp, lvl, event, stage, outcome, detail | filter lvl = "ERROR" | limit 20',
                'description': 'Error event analysis'
            },
            'stage_results': {
                'query': 'fields @timestamp, stage, outcome, dur_ms | filter event = "stage_result" | limit 20',
                'description': 'Stage result events'
            },
            'job_correlation': {
                'query': 'fields @timestamp, job_id, video_id, stage, event | filter ispresent(job_id) | limit 10',
                'description': 'Job correlation validation'
            }
        }
        
        # Calculate time range (last hour)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        for query_name, query_info in test_queries.items():
            try:
                logger.info(f"🔍 Testing query: {query_info['description']}")
                
                # Start query
                response = self.logs_client.start_query(
                    logGroupName=self.log_group,
                    startTime=int(start_time.timestamp()),
                    endTime=int(end_time.timestamp()),
                    queryString=query_info['query']
                )
                
                query_id = response['queryId']
                
                # Wait for query completion
                max_wait = 30  # seconds
                wait_time = 0
                
                while wait_time < max_wait:
                    result = self.logs_client.get_query_results(queryId=query_id)
                    
                    if result['status'] == 'Complete':
                        query_results[query_name] = {
                            'status': 'success',
                            'results_count': len(result['results']),
                            'sample_results': result['results'][:3] if result['results'] else []
                        }
                        logger.info(f"   ✅ Query completed: {len(result['results'])} results")
                        break
                    elif result['status'] == 'Failed':
                        query_results[query_name] = {
                            'status': 'failed',
                            'error': 'Query execution failed'
                        }
                        logger.error(f"   ❌ Query failed")
                        break
                    
                    time.sleep(2)
                    wait_time += 2
                
                if wait_time >= max_wait:
                    query_results[query_name] = {
                        'status': 'timeout',
                        'error': 'Query timed out'
                    }
                    logger.warning(f"   ⚠️  Query timed out")
                
            except Exception as e:
                query_results[query_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                logger.error(f"   ❌ Query error: {e}")
        
        return query_results
    
    def validate_field_consistency(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate field consistency across log events."""
        field_stats = {}
        timestamp_formats = set()
        level_values = set()
        
        for event in events:
            try:
                log_data = json.loads(event['message'])
                
                # Track field presence
                for field in log_data.keys():
                    if field not in field_stats:
                        field_stats[field] = {'count': 0, 'sample_values': set()}
                    
                    field_stats[field]['count'] += 1
                    
                    # Store sample values for analysis
                    if len(field_stats[field]['sample_values']) < 5:
                        field_stats[field]['sample_values'].add(str(log_data[field])[:50])
                
                # Track timestamp formats
                if 'ts' in log_data:
                    ts_format = self._analyze_timestamp_format(log_data['ts'])
                    timestamp_formats.add(ts_format)
                
                # Track log levels
                if 'lvl' in log_data:
                    level_values.add(log_data['lvl'])
                
            except json.JSONDecodeError:
                continue
        
        # Convert sets to lists for JSON serialization
        for field in field_stats:
            field_stats[field]['sample_values'] = list(field_stats[field]['sample_values'])
        
        consistency_results = {
            'field_statistics': field_stats,
            'timestamp_formats': list(timestamp_formats),
            'log_levels': list(level_values),
            'total_analyzed': len([e for e in events if self._is_json(e['message'])])
        }
        
        logger.info(f"📊 Field Consistency Analysis:")
        logger.info(f"   Analyzed {consistency_results['total_analyzed']} JSON events")
        logger.info(f"   Unique fields: {len(field_stats)}")
        logger.info(f"   Timestamp formats: {timestamp_formats}")
        logger.info(f"   Log levels: {level_values}")
        
        return consistency_results
    
    def _analyze_timestamp_format(self, timestamp: str) -> str:
        """Analyze timestamp format."""
        if timestamp.endswith('Z') and 'T' in timestamp:
            if '.' in timestamp:
                return 'ISO8601_with_milliseconds'
            else:
                return 'ISO8601_without_milliseconds'
        return 'unknown_format'
    
    def _is_json(self, message: str) -> bool:
        """Check if message is valid JSON."""
        try:
            json.loads(message)
            return True
        except json.JSONDecodeError:
            return False
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run complete staging validation."""
        logger.info("🚀 Starting staging log validation...")
        
        validation_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'log_group': self.log_group,
            'region': self.region
        }
        
        # 1. Validate log group exists
        if not self.validate_log_group_exists():
            validation_report['log_group_exists'] = False
            validation_report['overall_status'] = 'FAILED'
            return validation_report
        
        validation_report['log_group_exists'] = True
        
        # 2. Get recent log events
        events = self.get_recent_log_events(minutes=30)
        if not events:
            logger.warning("⚠️  No recent log events found - application may not be logging yet")
            validation_report['events_found'] = False
            validation_report['overall_status'] = 'WARNING'
            return validation_report
        
        validation_report['events_found'] = True
        
        # 3. Validate JSON format
        json_validation = self.validate_json_format(events)
        validation_report['json_validation'] = json_validation
        
        # 4. Test CloudWatch queries
        query_results = self.test_cloudwatch_queries()
        validation_report['query_results'] = query_results
        
        # 5. Validate field consistency
        consistency_results = self.validate_field_consistency(events)
        validation_report['consistency_results'] = consistency_results
        
        # Determine overall status
        json_success_rate = (json_validation['valid_schema_events'] / json_validation['total_events']) * 100 if json_validation['total_events'] > 0 else 0
        query_success_count = sum(1 for r in query_results.values() if r['status'] == 'success')
        query_success_rate = (query_success_count / len(query_results)) * 100 if query_results else 0
        
        if json_success_rate >= 90 and query_success_rate >= 75:
            validation_report['overall_status'] = 'PASSED'
            logger.info("✅ Staging validation PASSED")
        elif json_success_rate >= 70 and query_success_rate >= 50:
            validation_report['overall_status'] = 'WARNING'
            logger.warning("⚠️  Staging validation has WARNINGS")
        else:
            validation_report['overall_status'] = 'FAILED'
            logger.error("❌ Staging validation FAILED")
        
        validation_report['success_metrics'] = {
            'json_success_rate': json_success_rate,
            'query_success_rate': query_success_rate
        }
        
        return validation_report


def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate staging deployment logs')
    parser.add_argument('--region', default='us-west-2', help='AWS region')
    parser.add_argument('--log-group', default='/aws/apprunner/tldw-transcript-service-staging', help='CloudWatch log group')
    parser.add_argument('--output', help='Output file for validation report (JSON)')
    
    args = parser.parse_args()
    
    # Run validation
    validator = StagingLogValidator(region=args.region, log_group=args.log_group)
    report = validator.run_full_validation()
    
    # Output report
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"📄 Validation report saved to: {args.output}")
    
    # Print summary
    print("\n" + "="*60)
    print("STAGING VALIDATION SUMMARY")
    print("="*60)
    print(f"Overall Status: {report['overall_status']}")
    print(f"Log Group: {report['log_group']}")
    print(f"Region: {report['region']}")
    
    if 'success_metrics' in report:
        print(f"JSON Success Rate: {report['success_metrics']['json_success_rate']:.1f}%")
        print(f"Query Success Rate: {report['success_metrics']['query_success_rate']:.1f}%")
    
    if report['overall_status'] == 'PASSED':
        print("\n✅ Staging validation completed successfully!")
        print("   Ready to proceed to production deployment.")
        exit(0)
    elif report['overall_status'] == 'WARNING':
        print("\n⚠️  Staging validation completed with warnings.")
        print("   Review issues before proceeding to production.")
        exit(1)
    else:
        print("\n❌ Staging validation failed.")
        print("   Fix issues before proceeding to production.")
        exit(2)


if __name__ == '__main__':
    main()