#!/usr/bin/env python3
"""
AWS Secrets Manager Proxy Secret Validation Script

This script validates that proxy secrets in AWS Secrets Manager have all required fields
and helps fix the "proxy_secret_missing_provider" error from production logs.
"""

import json
import sys
import argparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, List, Tuple

def validate_secret_schema(secret_data: Dict) -> Tuple[bool, List[str]]:
    """
    Validate proxy secret schema.
    
    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    # Handle None or non-dict input
    if not secret_data or not isinstance(secret_data, dict):
        required_fields = ["provider", "host", "port", "username", "password", "protocol"]
        return False, required_fields
    
    required_fields = ["provider", "host", "port", "username", "password", "protocol"]
    missing_fields = []
    
    for field in required_fields:
        if field not in secret_data:
            missing_fields.append(field)
        elif not secret_data[field] or (isinstance(secret_data[field], str) and not secret_data[field].strip()):
            missing_fields.append(f"{field} (empty)")
    
    return len(missing_fields) == 0, missing_fields

def get_secret_from_aws(secret_name: str, region: str = 'us-west-2') -> Dict:
    """
    Retrieve secret from AWS Secrets Manager.
    
    Args:
        secret_name: Name or ARN of the secret
        region: AWS region
        
    Returns:
        Dictionary containing the secret data
        
    Raises:
        Exception: If secret cannot be retrieved or parsed
    """
    try:
        client = boto3.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_name)
        
        secret_string = response['SecretString']
        return json.loads(secret_string)
        
    except NoCredentialsError:
        raise Exception("AWS credentials not configured. Run 'aws configure' or set environment variables.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            raise Exception(f"Secret '{secret_name}' not found in region '{region}'")
        elif error_code == 'AccessDeniedException':
            raise Exception(f"Access denied to secret '{secret_name}'. Check IAM permissions.")
        else:
            raise Exception(f"AWS error: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Secret contains invalid JSON: {e}")

def update_secret_in_aws(secret_name: str, secret_data: Dict, region: str = 'us-west-2') -> bool:
    """
    Update secret in AWS Secrets Manager.
    
    Args:
        secret_name: Name or ARN of the secret
        secret_data: Dictionary containing the secret data
        region: AWS region
        
    Returns:
        True if successful
        
    Raises:
        Exception: If secret cannot be updated
    """
    try:
        client = boto3.client('secretsmanager', region_name=region)
        
        secret_string = json.dumps(secret_data, indent=2)
        
        client.update_secret(
            SecretId=secret_name,
            SecretString=secret_string
        )
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            raise Exception(f"Secret '{secret_name}' not found in region '{region}'")
        elif error_code == 'AccessDeniedException':
            raise Exception(f"Access denied to update secret '{secret_name}'. Check IAM permissions.")
        else:
            raise Exception(f"AWS error: {e}")

def create_example_secret() -> Dict:
    """Create an example proxy secret with all required fields."""
    return {
        "provider": "oxylabs",
        "host": "pr.oxylabs.io",
        "port": 60000,
        "username": "your-username",
        "password": "your-password",
        "protocol": "http",
        "geo_enabled": False,
        "country": None,
        "version": 1
    }

def validate_command(args):
    """Validate an existing secret."""
    print(f"🔍 Validating secret: {args.secret_name}")
    print(f"   Region: {args.region}")
    print()
    
    try:
        # Retrieve secret
        print("📥 Retrieving secret from AWS Secrets Manager...")
        secret_data = get_secret_from_aws(args.secret_name, args.region)
        print("✅ Secret retrieved successfully")
        
        # Validate schema
        print("\n🔍 Validating secret schema...")
        is_valid, missing_fields = validate_secret_schema(secret_data)
        
        if is_valid:
            print("✅ Secret schema is valid!")
            print("\n📋 Secret contains all required fields:")
            required_fields = ["provider", "host", "port", "username", "password", "protocol"]
            for field in required_fields:
                value = secret_data[field]
                # Mask sensitive fields
                if field in ["password", "username"]:
                    if isinstance(value, str) and len(value) > 4:
                        display_value = value[:2] + "*" * (len(value) - 4) + value[-2:]
                    else:
                        display_value = "***"
                else:
                    display_value = value
                print(f"   ✅ {field}: {display_value}")
            
            # Show optional fields if present
            optional_fields = ["geo_enabled", "country", "version"]
            optional_present = [f for f in optional_fields if f in secret_data]
            if optional_present:
                print("\n📋 Optional fields present:")
                for field in optional_present:
                    print(f"   ℹ️  {field}: {secret_data[field]}")
            
            return True
            
        else:
            print("❌ Secret schema is invalid!")
            print(f"\n🚨 Missing required fields: {missing_fields}")
            print("\n💡 This will cause 'proxy_secret_missing_provider' errors in production")
            
            if args.fix:
                print("\n🔧 Attempting to fix the secret...")
                return fix_secret_interactive(args.secret_name, secret_data, args.region)
            else:
                print(f"\n🔧 To fix this issue, run:")
                print(f"   python {sys.argv[0]} validate {args.secret_name} --fix")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def fix_secret_interactive(secret_name: str, current_data: Dict, region: str) -> bool:
    """Interactively fix a secret with missing fields."""
    print("🛠️  Interactive secret fixing...")
    
    # Get current schema validation
    is_valid, missing_fields = validate_secret_schema(current_data)
    
    if is_valid:
        print("✅ Secret is already valid!")
        return True
    
    print(f"\n📝 Current secret is missing: {missing_fields}")
    print("Please provide the missing information:")
    
    # Create a copy to modify
    fixed_data = current_data.copy()
    
    # Required fields with prompts
    field_prompts = {
        "provider": "Proxy provider name (e.g., 'oxylabs', 'brightdata')",
        "host": "Proxy hostname (e.g., 'pr.oxylabs.io')",
        "port": "Proxy port number (e.g., 60000)",
        "username": "Proxy username",
        "password": "Proxy password",
        "protocol": "Proxy protocol (usually 'http')"
    }
    
    for field in ["provider", "host", "port", "username", "password", "protocol"]:
        if field not in fixed_data or not fixed_data[field]:
            prompt = field_prompts.get(field, f"{field}")
            
            while True:
                if field == "password":
                    import getpass
                    value = getpass.getpass(f"Enter {prompt}: ")
                else:
                    value = input(f"Enter {prompt}: ").strip()
                
                if not value:
                    print("❌ This field is required. Please enter a value.")
                    continue
                
                # Convert port to integer
                if field == "port":
                    try:
                        value = int(value)
                    except ValueError:
                        print("❌ Port must be a number. Please try again.")
                        continue
                
                fixed_data[field] = value
                break
    
    # Validate the fixed data
    is_valid, missing_fields = validate_secret_schema(fixed_data)
    
    if not is_valid:
        print(f"❌ Still missing fields after fixing: {missing_fields}")
        return False
    
    # Show what will be updated
    print("\n📋 Updated secret will contain:")
    for field in ["provider", "host", "port", "username", "password", "protocol"]:
        value = fixed_data[field]
        if field in ["password", "username"]:
            if isinstance(value, str) and len(value) > 4:
                display_value = value[:2] + "*" * (len(value) - 4) + value[-2:]
            else:
                display_value = "***"
        else:
            display_value = value
        print(f"   {field}: {display_value}")
    
    # Confirm update
    confirm = input("\n❓ Update the secret in AWS Secrets Manager? (y/N): ").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            print("📤 Updating secret in AWS Secrets Manager...")
            update_secret_in_aws(secret_name, fixed_data, region)
            print("✅ Secret updated successfully!")
            print("\n🎉 The 'proxy_secret_missing_provider' error should now be resolved.")
            return True
        except Exception as e:
            print(f"❌ Failed to update secret: {e}")
            return False
    else:
        print("❌ Secret update cancelled.")
        return False

def example_command(args):
    """Show an example secret."""
    print("📋 Example AWS Secrets Manager proxy secret:")
    print()
    
    example = create_example_secret()
    print(json.dumps(example, indent=2))
    
    print("\n📝 Required fields:")
    required_fields = ["provider", "host", "port", "username", "password", "protocol"]
    for field in required_fields:
        print(f"   • {field}: {type(example[field]).__name__}")
    
    print("\n📝 Optional fields:")
    optional_fields = ["geo_enabled", "country", "version"]
    for field in optional_fields:
        if field in example:
            print(f"   • {field}: {type(example[field]).__name__}")
    
    print("\n💡 To create this secret in AWS:")
    print("   aws secretsmanager create-secret \\")
    print("     --name 'my-proxy-secret' \\")
    print("     --description 'Proxy configuration for TL;DW' \\")
    print("     --secret-string file://proxy-secret.json")
    
    return True

def list_secrets_command(args):
    """List proxy-related secrets."""
    print(f"🔍 Searching for proxy secrets in region: {args.region}")
    print()
    
    try:
        client = boto3.client('secretsmanager', region_name=args.region)
        
        # List all secrets
        paginator = client.get_paginator('list_secrets')
        
        proxy_secrets = []
        
        for page in paginator.paginate():
            for secret in page['SecretList']:
                name = secret['Name']
                description = secret.get('Description', '')
                
                # Look for proxy-related keywords
                if any(keyword in name.lower() for keyword in ['proxy', 'oxylabs', 'brightdata']) or \
                   any(keyword in description.lower() for keyword in ['proxy', 'oxylabs', 'brightdata']):
                    proxy_secrets.append({
                        'name': name,
                        'description': description,
                        'arn': secret['ARN']
                    })
        
        if proxy_secrets:
            print(f"📋 Found {len(proxy_secrets)} potential proxy secrets:")
            for secret in proxy_secrets:
                print(f"\n   Name: {secret['name']}")
                print(f"   Description: {secret['description']}")
                print(f"   ARN: {secret['arn']}")
        else:
            print("❌ No proxy-related secrets found.")
            print("\n💡 Secrets are identified by keywords: 'proxy', 'oxylabs', 'brightdata'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error listing secrets: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Validate and fix AWS Secrets Manager proxy secrets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate a secret
  python validate_proxy_secret.py validate my-proxy-secret
  
  # Validate and fix a secret interactively
  python validate_proxy_secret.py validate my-proxy-secret --fix
  
  # Show example secret format
  python validate_proxy_secret.py example
  
  # List potential proxy secrets
  python validate_proxy_secret.py list
        """
    )
    
    parser.add_argument('--region', default='us-west-2', 
                       help='AWS region (default: us-west-2)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate a proxy secret')
    validate_parser.add_argument('secret_name', help='Secret name or ARN')
    validate_parser.add_argument('--fix', action='store_true', 
                                help='Interactively fix missing fields')
    
    # Example command
    example_parser = subparsers.add_parser('example', help='Show example secret format')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List potential proxy secrets')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    print("🔧 AWS Secrets Manager Proxy Secret Validator")
    print("=" * 50)
    
    success = False
    
    if args.command == 'validate':
        success = validate_command(args)
    elif args.command == 'example':
        success = example_command(args)
    elif args.command == 'list':
        success = list_secrets_command(args)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())