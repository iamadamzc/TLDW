#!/usr/bin/env python3
"""
Environment Variable Standardization Script

This script helps standardize Google OAuth environment variable names
from GOOGLE_OAUTH_CLIENT_* to GOOGLE_CLIENT_* across the codebase.
"""

import os
import sys
import re
import argparse
from typing import List, Tuple, Dict

def find_files_with_pattern(pattern: str, file_extensions: List[str], exclude_dirs: List[str] = None) -> List[str]:
    """
    Find files containing a specific pattern.
    
    Args:
        pattern: Regex pattern to search for
        file_extensions: List of file extensions to include (e.g., ['.py', '.sh'])
        exclude_dirs: List of directories to exclude
        
    Returns:
        List of file paths containing the pattern
    """
    if exclude_dirs is None:
        exclude_dirs = ['.git', '__pycache__', '.venv', 'node_modules']
    
    matching_files = []
    
    for root, dirs, files in os.walk('.'):
        # Remove excluded directories from the search
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if any(file.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if re.search(pattern, content):
                            matching_files.append(file_path)
                except (UnicodeDecodeError, PermissionError):
                    # Skip files that can't be read
                    continue
    
    return matching_files

def analyze_google_oauth_usage() -> Dict[str, List[str]]:
    """
    Analyze current Google OAuth environment variable usage.
    
    Returns:
        Dictionary with old and new variable usage
    """
    # Patterns to search for
    old_pattern = r'GOOGLE_OAUTH_CLIENT_(ID|SECRET)'
    new_pattern = r'GOOGLE_CLIENT_(ID|SECRET)'
    
    # File extensions to search
    extensions = ['.py', '.sh', '.json', '.yaml', '.yml', '.md']
    
    old_usage = find_files_with_pattern(old_pattern, extensions)
    new_usage = find_files_with_pattern(new_pattern, extensions)
    
    return {
        'old_format': old_usage,
        'new_format': new_usage
    }

def update_file_env_vars(file_path: str, dry_run: bool = True) -> Tuple[bool, List[str]]:
    """
    Update environment variable names in a file.
    
    Args:
        file_path: Path to the file to update
        dry_run: If True, only show what would be changed
        
    Returns:
        Tuple of (changes_made, list_of_changes)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError) as e:
        return False, [f"Error reading file: {e}"]
    
    original_content = content
    changes = []
    
    # Replace GOOGLE_CLIENT_ID with GOOGLE_CLIENT_ID
    new_content = re.sub(
        r'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_ID',
        content
    )
    
    if new_content != content:
        changes.append("GOOGLE_CLIENT_ID → GOOGLE_CLIENT_ID")
        content = new_content
    
    # Replace GOOGLE_CLIENT_SECRET with GOOGLE_CLIENT_SECRET
    new_content = re.sub(
        r'GOOGLE_CLIENT_SECRET',
        'GOOGLE_CLIENT_SECRET',
        content
    )
    
    if new_content != content:
        changes.append("GOOGLE_CLIENT_SECRET → GOOGLE_CLIENT_SECRET")
        content = new_content
    
    # Write changes if not dry run
    if not dry_run and content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes
        except PermissionError as e:
            return False, [f"Error writing file: {e}"]
    
    return content != original_content, changes

def create_migration_script() -> str:
    """
    Create a deployment migration script for environment variables.
    
    Returns:
        Path to the created migration script
    """
    script_content = '''#!/bin/bash

# Google OAuth Environment Variable Migration Script
# This script provides a one-time migration map for deployment rollout

# Migration mapping for backwards compatibility during rollout
export_google_oauth_vars() {
    echo "🔄 Setting up Google OAuth environment variable migration..."
    
    # Map old variable names to new ones during transition
    if [ -n "$GOOGLE_OAUTH_CLIENT_ID" ] && [ -z "$GOOGLE_CLIENT_ID" ]; then
        export GOOGLE_CLIENT_ID="$GOOGLE_OAUTH_CLIENT_ID"
        echo "   Mapped GOOGLE_OAUTH_CLIENT_ID → GOOGLE_CLIENT_ID"
    fi
    
    if [ -n "$GOOGLE_OAUTH_CLIENT_SECRET" ] && [ -z "$GOOGLE_CLIENT_SECRET" ]; then
        export GOOGLE_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET"
        echo "   Mapped GOOGLE_OAUTH_CLIENT_SECRET → GOOGLE_CLIENT_SECRET"
    fi
    
    # Verify both sets are available during transition
    if [ -n "$GOOGLE_CLIENT_ID" ]; then
        echo "   ✅ GOOGLE_CLIENT_ID is set"
    else
        echo "   ❌ GOOGLE_CLIENT_ID is not set"
    fi
    
    if [ -n "$GOOGLE_CLIENT_SECRET" ]; then
        echo "   ✅ GOOGLE_CLIENT_SECRET is set"
    else
        echo "   ❌ GOOGLE_CLIENT_SECRET is not set"
    fi
}

# Call the migration function
export_google_oauth_vars
'''
    
    script_path = 'deployment/migrate-google-oauth-vars.sh'
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Make script executable
    os.chmod(script_path, 0o755)
    
    return script_path

def analyze_command(args):
    """Analyze current environment variable usage."""
    print("🔍 Analyzing Google OAuth environment variable usage...")
    print()
    
    usage = analyze_google_oauth_usage()
    
    print("📋 Files using old format (GOOGLE_OAUTH_CLIENT_*):")
    if usage['old_format']:
        for file_path in usage['old_format']:
            print(f"   - {file_path}")
    else:
        print("   None found")
    
    print()
    print("📋 Files using new format (GOOGLE_CLIENT_*):")
    if usage['new_format']:
        for file_path in usage['new_format']:
            print(f"   - {file_path}")
    else:
        print("   None found")
    
    print()
    if usage['old_format']:
        print("💡 Recommendation: Update files to use consistent GOOGLE_CLIENT_* naming")
        print(f"   Run: {sys.argv[0]} update --dry-run")
    else:
        print("✅ All files are using consistent environment variable naming")
    
    return True

def update_command(args):
    """Update environment variable names in files."""
    print("🔄 Updating Google OAuth environment variable names...")
    print()
    
    usage = analyze_google_oauth_usage()
    
    if not usage['old_format']:
        print("✅ No files need updating - all use consistent naming")
        return True
    
    total_files = len(usage['old_format'])
    updated_files = 0
    
    for file_path in usage['old_format']:
        print(f"📝 Processing: {file_path}")
        
        changed, changes = update_file_env_vars(file_path, dry_run=args.dry_run)
        
        if changed:
            if args.dry_run:
                print(f"   [DRY RUN] Would make changes:")
            else:
                print(f"   ✅ Updated:")
            
            for change in changes:
                print(f"      - {change}")
            
            if not args.dry_run:
                updated_files += 1
        else:
            print(f"   ℹ️  No changes needed")
        
        print()
    
    if args.dry_run:
        print(f"📊 Summary: {total_files} files would be updated")
        print(f"💡 To apply changes, run: {sys.argv[0]} update")
    else:
        print(f"📊 Summary: {updated_files}/{total_files} files updated successfully")
        
        if updated_files > 0:
            print("🎉 Environment variable standardization complete!")
            print("📝 Next steps:")
            print("   1. Test the application with new variable names")
            print("   2. Update deployment scripts and secrets")
            print("   3. Use migration script during rollout if needed")
    
    return True

def migration_command(args):
    """Create migration script for deployment."""
    print("🛠️  Creating migration script for deployment rollout...")
    print()
    
    script_path = create_migration_script()
    
    print(f"✅ Migration script created: {script_path}")
    print()
    print("📝 Usage during deployment:")
    print(f"   source {script_path}")
    print()
    print("💡 This script provides backwards compatibility by mapping:")
    print("   GOOGLE_CLIENT_ID → GOOGLE_CLIENT_ID")
    print("   GOOGLE_CLIENT_SECRET → GOOGLE_CLIENT_SECRET")
    print()
    print("🔄 Use this during rollout to ensure both old and new variable names work")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Standardize Google OAuth environment variable names",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze current usage
  python standardize_env_vars.py analyze
  
  # Preview changes (dry run)
  python standardize_env_vars.py update --dry-run
  
  # Apply changes
  python standardize_env_vars.py update
  
  # Create migration script
  python standardize_env_vars.py migration
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze current environment variable usage')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update environment variable names')
    update_parser.add_argument('--dry-run', action='store_true', 
                              help='Show what would be changed without making changes')
    
    # Migration command
    migration_parser = subparsers.add_parser('migration', help='Create migration script for deployment')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    print("🔧 Google OAuth Environment Variable Standardization")
    print("=" * 55)
    print()
    
    success = False
    
    if args.command == 'analyze':
        success = analyze_command(args)
    elif args.command == 'update':
        success = update_command(args)
    elif args.command == 'migration':
        success = migration_command(args)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())