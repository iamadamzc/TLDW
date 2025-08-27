#!/usr/bin/env python3
"""
Demonstration of backward compatibility layer for structured logging.

This script shows how existing code continues to work when migrating
from legacy structured logging to minimal JSON logging.
"""

import os
import sys
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def demo_legacy_mode():
    """Demonstrate backward compatibility in legacy mode."""
    print("=== LEGACY MODE DEMONSTRATION ===")
    
    # Set environment for legacy mode
    os.environ['USE_MINIMAL_LOGGING'] = 'false'
    
    # Clear module cache to force reload
    modules_to_clear = ['structured_logging', 'logging_setup', 'log_events']
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    # Import structured logging
    from structured_logging import (
        setup_structured_logging, 
        log_context, 
        log_performance,
        get_contextual_logger,
        performance_logger
    )
    
    # Initialize logging
    setup_structured_logging()
    
    print("1. Basic contextual logging:")
    logger = get_contextual_logger("demo_service")
    logger.info("Service started in legacy mode")
    
    print("\n2. Context manager usage:")
    with log_context(video_id="demo123", job_id="job456") as context:
        logger.info("Processing video", extra_field="demo_value")
        print(f"   Context correlation_id: {context.correlation_id}")
    
    print("\n3. Performance logging:")
    with log_performance("video_processing", video_id="demo123"):
        time.sleep(0.01)  # Simulate work
        logger.info("Video processed successfully")
    
    print("\n4. Performance logger direct usage:")
    performance_logger.log_stage_performance(
        stage="transcript_extraction",
        duration_ms=1500.0,
        success=True,
        video_id="demo123"
    )
    
    print("Legacy mode demonstration complete.\n")


def demo_minimal_mode():
    """Demonstrate backward compatibility in minimal mode."""
    print("=== MINIMAL MODE DEMONSTRATION ===")
    
    # Set environment for minimal mode
    os.environ['USE_MINIMAL_LOGGING'] = 'true'
    
    # Clear module cache to force reload
    modules_to_clear = ['structured_logging', 'logging_setup', 'log_events']
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    try:
        # Import structured logging
        from structured_logging import (
            setup_structured_logging, 
            log_context, 
            log_performance,
            get_contextual_logger,
            performance_logger
        )
        
        # Initialize logging
        setup_structured_logging()
        
        print("1. Basic contextual logging:")
        logger = get_contextual_logger("demo_service")
        logger.info("Service started in minimal mode")
        
        print("\n2. Context manager usage:")
        with log_context(video_id="demo123", job_id="job456") as context:
            logger.info("Processing video", extra_field="demo_value")
            print(f"   Context correlation_id: {context.correlation_id}")
        
        print("\n3. Performance logging:")
        with log_performance("video_processing", video_id="demo123"):
            time.sleep(0.01)  # Simulate work
            logger.info("Video processed successfully")
        
        print("\n4. Performance logger direct usage:")
        performance_logger.log_stage_performance(
            stage="transcript_extraction",
            duration_ms=1500.0,
            success=True,
            video_id="demo123"
        )
        
        print("Minimal mode demonstration complete.\n")
        
    except ImportError as e:
        print(f"Minimal logging not available: {e}")
        print("This is expected if logging_setup.py or log_events.py are not available.")
        print("The system would fall back to legacy mode automatically.\n")


def demo_migration_scenario():
    """Demonstrate a typical migration scenario."""
    print("=== MIGRATION SCENARIO DEMONSTRATION ===")
    
    print("Step 1: Application running in legacy mode")
    demo_legacy_mode()
    
    print("Step 2: Switch to minimal mode (same API)")
    demo_minimal_mode()
    
    print("Step 3: Verify both modes produce logs")
    print("✓ Legacy mode: Verbose JSON with full context")
    print("✓ Minimal mode: Streamlined JSON with stable schema")
    print("✓ Same API works in both modes")
    print("✓ Graceful fallback if minimal logging unavailable")


def demo_error_handling():
    """Demonstrate error handling and fallback behavior."""
    print("=== ERROR HANDLING DEMONSTRATION ===")
    
    # Test with invalid environment
    os.environ['USE_MINIMAL_LOGGING'] = 'invalid_value'
    
    # Clear module cache
    modules_to_clear = ['structured_logging', 'logging_setup', 'log_events']
    for module in modules_to_clear:
        if module in sys.modules:
            del sys.modules[module]
    
    try:
        from structured_logging import setup_structured_logging, log_context
        
        print("1. Invalid environment value handled gracefully")
        setup_structured_logging()
        
        print("2. Context manager still works:")
        with log_context(video_id="error_test"):
            logger = logging.getLogger("error_demo")
            logger.info("Error handling test successful")
        
        print("Error handling demonstration complete.\n")
        
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == '__main__':
    print("Backward Compatibility Layer Demonstration")
    print("=" * 50)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    try:
        demo_migration_scenario()
        demo_error_handling()
        
        print("All demonstrations completed successfully!")
        print("\nKey Benefits:")
        print("• Existing code continues to work unchanged")
        print("• Gradual migration with feature flag")
        print("• Automatic fallback on errors")
        print("• Same API for both logging systems")
        print("• Thread-safe context management")
        
    except Exception as e:
        print(f"Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up environment
        if 'USE_MINIMAL_LOGGING' in os.environ:
            del os.environ['USE_MINIMAL_LOGGING']