#!/usr/bin/env python3
"""
Documentation update script for structured JSON logging migration.
Updates all documentation references to use the new minimal logging system.
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple

# Configure logging for this script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentationUpdater:
    """Updates documentation references to new logging system."""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = Path(workspace_root)
        self.updated_files = []
        
    def get_documentation_files(self) -> List[Path]:
        """Get all documentation files that need updating."""
        doc_patterns = [
            "*.md",
            "docs/*.md", 
            "README*",
            "*.rst",
            "*.txt"
        ]
        
        doc_files = []
        for pattern in doc_patterns:
            doc_files.extend(self.workspace_root.glob(pattern))
            doc_files.extend(self.workspace_root.rglob(pattern))
        
        # Remove duplicates and filter out backup directories
        unique_files = []
        seen = set()
        for file_path in doc_files:
            if (str(file_path) not in seen and 
                not any(part.startswith('.') or 'backup' in part for part in file_path.parts)):
                unique_files.append(file_path)
                seen.add(str(file_path))
        
        return unique_files
    
    def update_file_content(self, file_path: Path) -> bool:
        """Update documentation content in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Define replacement patterns for documentation
            replacements = [
                # Module references
                (r'structured_logging\.py', 'logging_setup.py'),
                (r'`structured_logging`', '`logging_setup`'),
                
                # Import statements in code examples
                (r'from structured_logging import setup_structured_logging', 
                 'from logging_setup import configure_logging'),
                (r'from structured_logging import get_contextual_logger', 
                 'from logging_setup import get_logger'),
                (r'from structured_logging import log_context', 
                 'from log_events import job_context as log_context'),
                (r'from structured_logging import log_performance', 
                 'from log_events import StageTimer'),
                (r'from structured_logging import performance_logger', 
                 'from log_events import perf_evt'),
                (r'import structured_logging', 
                 'from logging_setup import configure_logging'),
                
                # Function calls
                (r'setup_structured_logging\(\)', 'configure_logging()'),
                (r'get_contextual_logger\(', 'get_logger('),
                (r'log_performance\(', 'StageTimer('),
                (r'performance_logger\.', 'perf_evt('),
                
                # Configuration references
                (r'STRUCTURED_LOGGING_ENABLED', 'USE_MINIMAL_LOGGING'),
                (r'structured logging system', 'minimal JSON logging system'),
                (r'structured JSON logging', 'minimal JSON logging'),
                
                # File references in deployment guides
                (r'structured_logging module', 'logging_setup module'),
                (r'StructuredFormatter', 'JsonFormatter'),
                (r'ContextualLogger', 'standard logger with context'),
                
                # CloudWatch references
                (r'structured log events', 'JSON log events'),
                (r'structured logging format', 'JSON logging format'),
                
                # Environment variable updates
                (r'ENABLE_STRUCTURED_LOGGING', 'USE_MINIMAL_LOGGING'),
                (r'STRUCTURED_LOG_LEVEL', 'LOG_LEVEL'),
            ]
            
            # Apply replacements
            changes_made = False
            for pattern, replacement in replacements:
                new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                if new_content != content:
                    content = new_content
                    changes_made = True
            
            # Special handling for code blocks
            content = self._update_code_blocks(content)
            if content != original_content:
                changes_made = True
            
            # Write updated content if changes were made
            if changes_made:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"✅ Updated {file_path}")
                self.updated_files.append(str(file_path))
                return True
            else:
                logger.debug(f"ℹ️  No changes needed in {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to update {file_path}: {e}")
            return False
    
    def _update_code_blocks(self, content: str) -> str:
        """Update code examples in documentation."""
        # Update Python code blocks
        code_block_pattern = r'```python\n(.*?)\n```'
        
        def update_python_code(match):
            code = match.group(1)
            
            # Update imports in code examples
            code = re.sub(r'from structured_logging import ([^\\n]+)', 
                         self._convert_import, code)
            code = re.sub(r'import structured_logging', 
                         'from logging_setup import configure_logging', code)
            
            # Update function calls
            code = re.sub(r'setup_structured_logging\(\)', 'configure_logging()', code)
            code = re.sub(r'get_contextual_logger\(([^)]+)\)', r'get_logger(\1)', code)
            code = re.sub(r'with log_performance\(([^)]+)\):', r'with StageTimer(\1):', code)
            
            return f'```python\n{code}\n```'
        
        return re.sub(code_block_pattern, update_python_code, content, flags=re.DOTALL)
    
    def _convert_import(self, match) -> str:
        """Convert structured_logging imports to new system."""
        imports = match.group(1).strip()
        
        # Map old imports to new ones
        import_mapping = {
            'setup_structured_logging': 'from logging_setup import configure_logging',
            'get_contextual_logger': 'from logging_setup import get_logger',
            'log_context': 'from log_events import job_context as log_context',
            'log_performance': 'from log_events import StageTimer',
            'performance_logger': 'from log_events import perf_evt',
        }
        
        # Handle multiple imports
        import_list = [imp.strip() for imp in imports.split(',')]
        new_imports = []
        
        for imp in import_list:
            if imp in import_mapping:
                new_imports.append(import_mapping[imp])
            else:
                # Keep unknown imports as-is but comment them
                new_imports.append(f'# {imp} - check migration guide')
        
        return '\n'.join(new_imports)
    
    def create_migration_summary(self) -> str:
        """Create a summary of documentation updates."""
        summary = f"""# Documentation Migration Summary

## Updated Files
Total files updated: {len(self.updated_files)}

"""
        
        for file_path in sorted(self.updated_files):
            summary += f"- {file_path}\n"
        
        summary += f"""

## Key Changes Made

### Import Statements
- `from structured_logging import setup_structured_logging` → `from logging_setup import configure_logging`
- `from structured_logging import get_contextual_logger` → `from logging_setup import get_logger`
- `from structured_logging import log_context` → `from log_events import job_context as log_context`
- `from structured_logging import log_performance` → `from log_events import StageTimer`
- `from structured_logging import performance_logger` → `from log_events import perf_evt`

### Function Calls
- `setup_structured_logging()` → `configure_logging()`
- `get_contextual_logger()` → `get_logger()`
- `log_performance()` → `StageTimer()`
- `performance_logger.` → `perf_evt()`

### Environment Variables
- `STRUCTURED_LOGGING_ENABLED` → `USE_MINIMAL_LOGGING`
- `ENABLE_STRUCTURED_LOGGING` → `USE_MINIMAL_LOGGING`

### Module References
- `structured_logging.py` → `logging_setup.py`
- `StructuredFormatter` → `JsonFormatter`
- `ContextualLogger` → `standard logger with context`

## Next Steps

1. Review updated documentation for accuracy
2. Test code examples in updated documentation
3. Update any remaining manual references
4. Notify team of documentation changes

Generated: {os.popen('date').read().strip()}
"""
        
        return summary
    
    def run_update(self, dry_run: bool = False) -> bool:
        """Run the complete documentation update process."""
        logger.info("🚀 Starting documentation update...")
        
        if dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be made")
        
        # Get all documentation files
        doc_files = self.get_documentation_files()
        logger.info(f"📚 Found {len(doc_files)} documentation files to check")
        
        if dry_run:
            logger.info("🔍 Files that would be checked:")
            for file_path in doc_files:
                logger.info(f"   {file_path}")
            return True
        
        # Update each file
        updated_count = 0
        for file_path in doc_files:
            if self.update_file_content(file_path):
                updated_count += 1
        
        logger.info(f"✅ Updated {updated_count} documentation files")
        
        # Create migration summary
        if self.updated_files:
            summary = self.create_migration_summary()
            summary_path = self.workspace_root / "docs" / "DOCUMENTATION_MIGRATION_SUMMARY.md"
            
            try:
                summary_path.parent.mkdir(exist_ok=True)
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                logger.info(f"📄 Created migration summary: {summary_path}")
            except Exception as e:
                logger.warning(f"Could not create migration summary: {e}")
        
        return True


def main():
    """Main documentation update function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update documentation references to new logging system')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--workspace', default='.', help='Workspace root directory')
    
    args = parser.parse_args()
    
    # Run update
    updater = DocumentationUpdater(workspace_root=args.workspace)
    success = updater.run_update(dry_run=args.dry_run)
    
    if success:
        if args.dry_run:
            print("\n✅ Dry run completed - ready to update documentation")
        else:
            print(f"\n🎉 Documentation update completed!")
            print(f"   Updated {len(updater.updated_files)} files")
            print("   Check docs/DOCUMENTATION_MIGRATION_SUMMARY.md for details")
        exit(0)
    else:
        print("\n❌ Documentation update failed - check logs for details")
        exit(1)


if __name__ == '__main__':
    main()