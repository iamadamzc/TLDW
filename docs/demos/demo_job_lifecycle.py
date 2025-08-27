#!/usr/bin/env python3
"""
Demonstration of job lifecycle tracking with structured JSON logging.

This script shows how the job lifecycle events work in practice,
simulating a complete job processing flow.
"""

import time
import logging
from logging_setup import configure_logging, set_job_ctx, clear_job_ctx
from log_events import (
    job_received, job_finished, job_failed, video_processed, 
    classify_error_type, evt
)


def simulate_job_processing():
    """Simulate a complete job processing workflow."""
    
    # Configure JSON logging
    configure_logging("INFO", use_json=True)
    
    print("=== Job Lifecycle Tracking Demo ===\n")
    print("This demo shows structured JSON events for job processing.\n")
    
    # Simulate job processing
    job_id = "demo-job-12345"
    video_ids = ["abc123", "def456", "ghi789"]
    
    # Set job context
    set_job_ctx(job_id=job_id)
    
    print("1. Job received - starting processing...")
    job_received(
        video_count=len(video_ids),
        use_cookies=True,
        proxy_enabled=False,
        user_id=42
    )
    
    start_time = time.time()
    processed_count = 0
    
    # Process each video
    for i, video_id in enumerate(video_ids):
        print(f"\n2.{i+1}. Processing video {video_id}...")
        
        # Set video context
        set_job_ctx(job_id=job_id, video_id=video_id)
        
        video_start_time = time.time()
        
        # Simulate different outcomes
        if video_id == "def456":
            # Simulate a failed video
            time.sleep(0.1)  # Simulate processing time
            video_duration_ms = int((time.time() - video_start_time) * 1000)
            
            error = Exception("No transcript available for this video")
            error_type = classify_error_type(error)
            
            video_processed(
                video_id=video_id,
                outcome="error",
                duration_ms=video_duration_ms,
                transcript_source="none",
                error_type=error_type,
                error_detail=str(error),
                progress=f"{i+1}/{len(video_ids)}"
            )
            
            print(f"   ❌ Video {video_id} failed: {error}")
            
        else:
            # Simulate successful processing
            time.sleep(0.2)  # Simulate processing time
            video_duration_ms = int((time.time() - video_start_time) * 1000)
            
            # Simulate different transcript sources
            transcript_source = "yt_api" if i == 0 else "youtubei"
            
            video_processed(
                video_id=video_id,
                outcome="success",
                duration_ms=video_duration_ms,
                transcript_source=transcript_source,
                summary_length=250 + i * 50,
                progress=f"{i+1}/{len(video_ids)}"
            )
            
            processed_count += 1
            print(f"   ✅ Video {video_id} processed successfully via {transcript_source}")
    
    # Simulate email sending
    print(f"\n3. Sending digest email...")
    time.sleep(0.1)
    
    evt("email_sent", 
        recipient="user@example.com", 
        items_count=len(video_ids),
        outcome="success")
    
    # Job completion
    total_duration_ms = int((time.time() - start_time) * 1000)
    error_count = len(video_ids) - processed_count
    
    # Clear video context, keep job context
    set_job_ctx(job_id=job_id)
    
    if processed_count == len(video_ids):
        outcome = "success"
        print(f"\n4. ✅ Job completed successfully!")
    elif processed_count > 0:
        outcome = "partial_success"
        print(f"\n4. ⚠️  Job completed with partial success ({processed_count}/{len(video_ids)} videos)")
    else:
        outcome = "error"
        print(f"\n4. ❌ Job failed completely")
    
    job_finished(
        total_duration_ms=total_duration_ms,
        processed_count=processed_count,
        video_count=len(video_ids),
        outcome=outcome,
        email_sent=True,
        error_count=error_count
    )
    
    # Clear job context
    clear_job_ctx()
    
    print(f"\nJob processing complete in {total_duration_ms}ms")
    print(f"Processed: {processed_count}/{len(video_ids)} videos")
    print(f"Outcome: {outcome}")


def simulate_job_failure():
    """Simulate a job that fails at the job level."""
    
    print("\n\n=== Job Failure Demo ===\n")
    print("This demo shows job-level failure events.\n")
    
    job_id = "failed-job-67890"
    video_ids = ["xyz123", "uvw456"]
    
    set_job_ctx(job_id=job_id)
    
    print("1. Job received...")
    job_received(video_count=len(video_ids), use_cookies=False)
    
    start_time = time.time()
    
    try:
        print("2. Simulating critical job failure...")
        time.sleep(0.1)
        
        # Simulate a critical error (e.g., authentication failure)
        raise Exception("Authentication token expired - cannot access YouTube API")
        
    except Exception as e:
        total_duration_ms = int((time.time() - start_time) * 1000)
        error_type = classify_error_type(e)
        
        print(f"   ❌ Critical job failure: {e}")
        
        job_failed(
            total_duration_ms=total_duration_ms,
            processed_count=0,
            video_count=len(video_ids),
            error_type=error_type,
            error_detail=str(e)
        )
    
    clear_job_ctx()
    print("Job failed and context cleared.")


def demonstrate_error_classification():
    """Demonstrate error classification functionality."""
    
    print("\n\n=== Error Classification Demo ===\n")
    print("This demo shows how different errors are classified.\n")
    
    test_errors = [
        Exception("Authentication token expired"),
        Exception("Connection timeout occurred"),
        Exception("YouTube transcript API rate limited"),
        Exception("OpenAI API key invalid"),
        Exception("Resend email service unavailable"),
        Exception("Missing DEEPGRAM_API_KEY configuration"),
        Exception("Memory limit exceeded"),
        Exception("Unexpected service failure")
    ]
    
    for i, error in enumerate(test_errors, 1):
        error_type = classify_error_type(error)
        print(f"{i}. '{str(error)}' → {error_type}")


if __name__ == "__main__":
    # Run all demonstrations
    simulate_job_processing()
    simulate_job_failure()
    demonstrate_error_classification()
    
    print("\n=== Demo Complete ===")
    print("\nAll JSON events above show the structured logging format that will be")
    print("sent to CloudWatch Logs for analysis and monitoring.")