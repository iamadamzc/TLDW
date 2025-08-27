#!/usr/bin/env python3
"""
Cleanup script for deprecated structured logging code.
Removes old structured logging imports and code after successful migration.
"""

import os
import re
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Configure logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeprecatedLoggingCleanup:
    """Handles cleanup of deprecated structured logging code."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.backup_dir = self.workspace_root / "backup_deprecated_logging"
        self.files_to_update = []
        self.files_to_remove = []
        
    def scan_for_deprecated_imports(self) -> Dict[str, List[str]]:
        """Scan for files with deprecated structured logging imports."""
        deprecated_patterns = [
            r'from structured_logging import',
            r'import structured_logging',
            r'structured_logging\.',
        ]
        
        files_with_imports = {}
        
        # Scan Python files
        for py_file in self.workspace_root.rglob("*.py"):
            # Skip test files and backup directories
            if any(part.startswith('.') or part == '__pycache__' or 'backup' in str(py_file) for part in py_file.parts):
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                found_patterns = []
                for pattern in deprecated_patterns:
                    if re.search(pattern, content):
                        found_patterns.append(pattern)
                
                if found_patterns:
                    files_with_imports[str(py_file)] = found_patterns
                    
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")
        
        return files_with_imports
    
    def create_backup(self) -> bool:
        """Create backup of files before modification."""
        try:
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            
            self.backup_dir.mkdir(parents=True)
            
            # Backup structured_logging.py
            structured_logging_file = self.workspace_root / "structured_logging.py"
            if structured_logging_file.exists():
                shutil.copy2(structured_logging_file, self.backup_dir / "structured_logging.py")
                logger.info(f"✅ Backed up structured_logging.py")
            
            # Backup files that will be modified
            for file_path in self.files_to_update:
                rel_path = Path(file_path).relative_to(self.workspace_root)
                backup_path = self.backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_path)
            
            logger.info(f"✅ Created backup directory: {self.backup_dir}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create backup: {e}")
            return False
    
    def update_file_imports(self, file_path: str) -> bool:
        """Update imports in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Replace structured_logging imports with minimal logging equivalents
            replacements = [
                # Context management
                (r'from structured_logging import get_contextual_logger', 
                 'from logging_setup import get_logger as get_contextual_logger'),
                (r'from structured_logging import log_context', 
                 'from log_events import job_context as log_context'),
                (r'from structured_logging import log_performance', 
                 'from log_events import StageTimer as log_performance'),
                
                # Performance logging
                (r'from structured_logging import performance_logger', 
                 'from log_events import perf_evt'),
                (r'performance_logger\.log_stage_performance\(([^)]+)\)', 
                 r'perf_evt(event="stage_result", \1)'),
                
                # Setup function
                (r'from structured_logging import setup_structured_logging', 
                 'from logging_setup import configure_logging as setup_structured_logging'),
                
                # Direct module import
                (r'import structured_logging', 
                 '# Migrated to minimal logging system'),
                
                # Module usage patterns
                (r'structured_logging\.get_contextual_logger', 
                 'logging.getLogger'),
                (r'structured_logging\.log_context', 
                 'log_events.job_context'),
                (r'structured_logging\.setup_structured_logging', 
                 'logging_setup.configure_logging'),
            ]
            
            changes_made = False
            for pattern, replacement in replacements:
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    changes_made = True
            
            # Write updated content if changes were made
            if changes_made:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"✅ Updated imports in {file_path}")
                return True
            else:
                logger.info(f"ℹ️  No changes needed in {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update {file_path}: {e}")
            return False
    
    def remove_deprecated_files(self) -> bool:
        """Remove deprecated structured logging files."""
        files_to_remove = [
            "structured_logging.py"
        ]
        
        removed_files = []
        
        for filename in files_to_remove:
            file_path = self.workspace_root / filename
            if file_path.exists():
                try:
                    # Move to backup instead of deleting
                    backup_path = self.backup_dir / filename
                    shutil.move(str(file_path), str(backup_path))
                    removed_files.append(filename)
                    logger.info(f"✅ Removed {filename}")
                except Exception as e:
                    logger.error(f"❌ Failed to remove {filename}: {e}")
                    return False
        
        if removed_files:
            logger.info(f"✅ Removed {len(removed_files)} deprecated files")
        else:
            logger.info("ℹ️  No deprecated files to remove")
        
        return True
    
    def update_documentation(self) -> bool:
        """Update documentation references to new logging system."""
        doc_files = list(self.workspace_root.glob("docs/*.md")) + list(self.workspace_root.glob("*.md"))
        
        updated_files = []
        
        for doc_file in doc_files:
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Update documentation references
                replacements = [
                    (r'structured_logging\.py', 'logging_setup.py'),
                    (r'from structured_logging import', 'from logging_setup import'),
                    (r'import structured_logging', 'from logging_setup import configure_logging'),
                    (r'setup_structured_logging\(\)', 'configure_logging()'),
                    (r'get_contextual_logger', 'get_logger'),
                    (r'log_performance', 'StageTimer'),
                    (r'performance_logger', 'perf_evt'),
                ]
                
                for pattern, replacement in replacements:
                    content = re.sub(pattern, replacement, content)
                
                if content != original_content:
                    with open(doc_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    updated_files.append(str(doc_file))
                    logger.info(f"✅ Updated documentation in {doc_file}")
                    
            except Exception as e:
                logger.warning(f"Could not update documentation in {doc_file}: {e}")
        
        if updated_files:
            logger.info(f"✅ Updated {len(updated_files)} documentation files")
        else:
            logger.info("ℹ️  No documentation updates needed")
        
        return True
    
    def validate_cleanup(self) -> Dict[str, bool]:
        """Validate that cleanup was successful."""
        validation_results = {}
        
        # Check that structured_logging.py is removed
        structured_logging_exists = (self.workspace_root / "structured_logging.py").exists()
        validation_results['structured_logging_removed'] = not structured_logging_exists
        
        # Check for remaining deprecated imports
        remaining_imports = self.scan_for_deprecated_imports()
        validation_results['no_deprecated_imports'] = len(remaining_imports) == 0
        
        # Check that backup was created
        backup_exists = self.backup_dir.exists() and len(list(self.backup_dir.iterdir())) > 0
        validation_results['backup_created'] = backup_exists
        
        # Check that new logging system is importable
        try:
            import logging_setup
            import log_events
            validation_results['new_system_importable'] = True
        except ImportError as e:
            logger.error(f"New logging system not importable: {e}")
            validation_results['new_system_importable'] = False
        
        return validation_results
    
    def run_cleanup(self, dry_run: bool = False) -> bool:
        """Run the complete cleanup process."""
        logger.info("🚀 Starting deprecated logging cleanup...")
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
        
        # 1. Scan for deprecated imports
        logger.info("🔍 Scanning for deprecated imports...")
        deprecated_files = self.scan_for_deprecated_imports()
        
        if not deprecated_files:
            logger.info("✅ No deprecated imports found - cleanup not needed")
            return True
        
        logger.info(f"📊 Found deprecated imports in {len(deprecated_files)} files:")
        for file_path, patterns in deprecated_files.items():
            logger.info(f"   {file_path}: {patterns}")
        
        self.files_to_update = list(deprecated_files.keys())
        
        if dry_run:
            logger.info("🔍 DRY RUN: Would update the above files")
            return True
        
        # 2. Create backup
        logger.info("💾 Creating backup...")
        if not self.create_backup():
            logger.error("❌ Backup creation failed - aborting cleanup")
            return False
        
        # 3. Update file imports
        logger.info("🔄 Updating file imports...")
        update_success = True
        for file_path in self.files_to_update:
            if not self.update_file_imports(file_path):
                update_success = False
        
        if not update_success:
            logger.error("❌ Some file updates failed")
            return False
        
        # 4. Remove deprecated files
        logger.info("🗑️  Removing deprecated files...")
        if not self.remove_deprecated_files():
            logger.error("❌ Failed to remove deprecated files")
            return False
        
        # 5. Update documentation
        logger.info("📚 Updating documentation...")
        if not self.update_documentation():
            logger.warning("⚠️  Documentation update had issues")
        
        # 6. Validate cleanup
        logger.info("✅ Validating cleanup...")
        validation_results = self.validate_cleanup()
        
        logger.info("📊 Cleanup Validation Results:")
        for check, passed in validation_results.items():
            status = "✅" if passed else "❌"
            logger.info(f"   {status} {check}: {'PASSED' if passed else 'FAILED'}")
        
        all_passed = all(validation_results.values())
        
        if all_passed:
            logger.info("🎉 Deprecated logging cleanup completed successfully!")
            logger.info(f"💾 Backup available at: {self.backup_dir}")
            return True
        else:
            logger.error("❌ Cleanup validation failed")
            logger.error(f"💾 Restore from backup if needed: {self.backup_dir}")
            return False


def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up deprecated structured logging code')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--workspace', default='.', help='Workspace root directory')
    
    args = parser.parse_args()
    
    # Confirmation for non-dry-run
    if not args.dry_run:
        print("🚨 DEPRECATED LOGGING CLEANUP 🚨")
        print("This will remove deprecated structured logging code.")
        print("Ensure the following before proceeding:")
        print("  ✓ Production deployment is stable (>2 weeks)")
        print("  ✓ New logging system is working correctly")
        print("  ✓ Team is comfortable with new system")
        print("  ✓ Backup will be created automatically")
        print("")
        
        response = input("Proceed with cleanup? (y/N): ")
        if response.lower() != 'y':
            print("Cleanup aborted")
            return
    
    # Run cleanup
    cleanup = DeprecatedLoggingCleanup(workspace_root=args.workspace)
    success = cleanup.run_cleanup(dry_run=args.dry_run)
    
    if success:
        if args.dry_run:
            print("\n✅ Dry run completed - no issues found")
        else:
            print("\n🎉 Deprecated logging cleanup completed successfully!")
            print("   New minimal logging system is now the only logging system.")
            print("   Backup available in backup_deprecated_logging/ directory.")
        exit(0)
    else:
        print("\n❌ Cleanup failed - check logs for details")
        exit(1)


if __name__ == '__main__':
    main()