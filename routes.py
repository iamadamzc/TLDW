import logging
import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from cookie_utils import parse_netscape_for_both
from youtube_service import YouTubeService, AuthenticationError
from transcript_service import TranscriptService
from summarizer import VideoSummarizer
from email_service import EmailService
from models import update_user_session, get_user_session
from error_handler import (
    StructuredLogger, handle_transcript_error, handle_summarization_error, 
    handle_email_error, handle_job_error, handle_api_error, log_performance_metrics
)
from security_manager import secure_cookie_manager, credential_protector, setup_secure_logging

main_routes = Blueprint("main_routes", __name__)

def _cookies_dir() -> str:
    """Get the cookie storage directory path"""
    return os.getenv("COOKIE_LOCAL_DIR", "/app/cookies")

def _local_cookie_path(user_id: int) -> str:
    """Get the local cookie file path for a user"""
    return os.path.join(_cookies_dir(), f"{user_id}.txt")

def get_user_cookie_status(user_id: int) -> dict:
    """Get comprehensive cookie status for a user"""
    try:
        cookie_path = _local_cookie_path(user_id)
        
        if not os.path.exists(cookie_path):
            return {
                'has_cookies': False,
                'upload_date': None,
                'file_size_kb': None,
                'is_valid': False,
                'status_text': 'Not Configured',
                'status_class': 'warning'
            }
        
        # Get file stats
        stat = os.stat(cookie_path)
        file_size_bytes = stat.st_size
        file_size_kb = round(file_size_bytes / 1024, 1)
        upload_date = datetime.fromtimestamp(stat.st_mtime)
        
        # Check if file has content
        is_valid = file_size_bytes > 0
        
        return {
            'has_cookies': True,
            'upload_date': upload_date.isoformat(),
            'file_size_kb': file_size_kb,
            'is_valid': is_valid,
            'status_text': 'Active' if is_valid else 'Invalid',
            'status_class': 'success' if is_valid else 'danger'
        }
        
    except Exception as e:
        logging.warning(f"Error checking cookie status for user {user_id}: {e}")
        return {
            'has_cookies': False,
            'upload_date': None,
            'file_size_kb': None,
            'is_valid': False,
            'status_text': 'Unavailable',
            'status_class': 'secondary'
        }

@main_routes.route("/")
def index():
    """Homepage - shows login or dashboard based on auth status"""
    if current_user.is_authenticated:
        return redirect(url_for("main_routes.dashboard"))
    return render_template("index.html")

@main_routes.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard after login"""
    try:
        logging.info(f"Loading dashboard for user {current_user.email}")
        logging.info(f"Access token exists: {bool(current_user.access_token)}")
        
        # Get cookie status for the user
        cookie_status = get_user_cookie_status(current_user.id)
        
        youtube_service = YouTubeService(current_user)
        playlists = youtube_service.get_user_playlists()
        
        logging.info(f"Retrieved {len(playlists)} playlists")
        
        # Debug: Log Watch Later playlist details
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        if watch_later:
            logging.info(f"🎯 WATCH LATER PLAYLIST: {watch_later['title']} - {watch_later['video_count']} videos")
            if 'Error' in watch_later['title']:
                logging.warning(f"Watch Later error: {watch_later['description']}")
        else:
            logging.warning("Watch Later playlist not found in results")
        
        # Get user's selected playlist if any
        selected_playlist_id = current_user.selected_playlist_id
        videos = []
        
        if selected_playlist_id:
            videos = youtube_service.get_playlist_videos(selected_playlist_id)
        
        return render_template("index.html", 
                             authenticated=True,
                             playlists=playlists, 
                             videos=videos,
                             selected_playlist_id=selected_playlist_id,
                             cookie_status=cookie_status)
                             
    except AuthenticationError as e:
        logging.error(f"Authentication error loading dashboard for user {current_user.email}: {e}")
        flash("Your session has expired. Please sign in again to continue.", "error")
        return redirect(url_for("google_auth.login"))
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        flash("The YouTube API requires additional permissions. Please sign out and sign in again to grant YouTube access.", "error")
        
        # Still get cookie status even if YouTube API fails
        cookie_status = get_user_cookie_status(current_user.id)
        
        return render_template("index.html", 
                             authenticated=True,
                             playlists=[], 
                             videos=[],
                             selected_playlist_id=None,
                             cookie_status=cookie_status)

@main_routes.route("/api/select-playlist", methods=["POST"])
@login_required
def select_playlist():
    """API endpoint to select a playlist and get its videos"""
    try:
        logging.info(f"Select playlist API called by user: {current_user.email}")
        
        data = request.get_json()
        playlist_id = data.get("playlist_id")
        
        logging.info(f"Requested playlist ID: {playlist_id}")
        
        if not playlist_id:
            logging.error("No playlist ID provided")
            return jsonify({"error": "Playlist ID required"}), 400
        
        # Save user's playlist selection
        current_user.selected_playlist_id = playlist_id
        from app import db
        db.session.commit()
        
        logging.info(f"Saved playlist selection: {playlist_id}")
        
        # Get videos from the selected playlist
        youtube_service = YouTubeService(current_user)
        videos = youtube_service.get_playlist_videos(playlist_id)
        
        logging.info(f"Retrieved {len(videos)} videos from playlist {playlist_id}")
        
        # Log first few video titles for debugging
        for i, video in enumerate(videos[:3]):
            logging.info(f"Video {i+1}: {video.get('title', 'No title')}")
        
        return jsonify({"videos": videos})
        
    except AuthenticationError as e:
        logging.error(f"Authentication error selecting playlist for user {current_user.email}: {e}")
        return jsonify({
            "error": "Authentication failed",
            "message": "Your session has expired. Please refresh the page and sign in again.",
            "code": "AUTH_EXPIRED"
        }), 401
    except Exception as e:
        playlist_id_str = locals().get('playlist_id', 'unknown')
        logging.error(f"Error selecting playlist {playlist_id_str}: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to load playlist videos: {str(e)}"}), 500

@main_routes.route("/test-watch-later")
@login_required
def test_watch_later():
    """Test route to verify Watch Later fix"""
    try:
        youtube_service = YouTubeService(current_user)
        playlists = youtube_service.get_user_playlists()
        
        watch_later = next((p for p in playlists if p['id'] == 'WL'), None)
        
        if watch_later:
            result = {
                "status": "success",
                "watch_later": watch_later,
                "message": f"Watch Later playlist found with {watch_later['video_count']} videos"
            }
        else:
            result = {
                "status": "error",
                "message": "Watch Later playlist not found"
            }
            
        return jsonify(result)
        
    except AuthenticationError as e:
        logging.error(f"Authentication error testing Watch Later for user {current_user.email}: {e}")
        return jsonify({
            "status": "error",
            "message": "Authentication failed. Please refresh the page and sign in again.",
            "code": "AUTH_EXPIRED"
        })
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error testing Watch Later: {str(e)}"
        })

from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from flask import current_app

# ---- Enhanced job processing system ----
import threading
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class JobStatus:
    job_id: str
    status: str  # queued, processing, done, error
    created_at: datetime
    updated_at: datetime
    user_id: int
    video_count: int
    processed_count: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "user_id": self.user_id,
            "video_count": self.video_count,
            "processed_count": self.processed_count,
            "error_message": self.error_message
        }

class JobManager:
    def __init__(self, worker_concurrency: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=worker_concurrency)
        self.jobs: Dict[str, JobStatus] = {}
        self.lock = threading.Lock()
        # Semaphore for job concurrency control
        self.job_semaphore = threading.Semaphore(worker_concurrency)
    
    def submit_summarization_job(self, user_id: int, video_ids: list, app) -> str:
        """Submit job and return job_id immediately"""
        job_id = str(uuid4())
        
        with self.lock:
            self.jobs[job_id] = JobStatus(
                job_id=job_id,
                status="queued",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                user_id=user_id,
                video_count=len(video_ids)
            )
        
        # Submit job to executor
        self.executor.submit(self._run_summarize_job, app, job_id, user_id, video_ids)
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get current job status"""
        with self.lock:
            return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, error_message: str = None, processed_count: int = None):
        """Update job status thread-safely"""
        with self.lock:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                job.status = status
                job.updated_at = datetime.utcnow()
                if error_message:
                    job.error_message = error_message
                if processed_count is not None:
                    job.processed_count = processed_count

    def _run_summarize_job(self, app, job_id: str, user_id: int, video_ids: list[str]):
        """
        Execute summarization job with per-video error isolation and concurrency control
        """
        # Import logging setup and lifecycle events
        from logging_setup import set_job_ctx, clear_job_ctx
        from log_events import evt, job_received, job_finished, job_failed, video_processed, classify_error_type
        
        processed_count = 0  # ensure defined for job-level exception paths
        with self.job_semaphore:
            start_time = time.time()
            
            # Set job context at the start of processing
            set_job_ctx(job_id=job_id)
            
            # Emit job_received event
            job_received(video_count=len(video_ids), user_id=user_id)
            
            self.update_job_status(job_id, "processing")
            
            try:
                with app.app_context():
                    from models import User
                    user = User.query.get(user_id)
                    if not user:
                        raise Exception("User not found")

                    # Initialize services
                    yt = YouTubeService(user)
                    ts = TranscriptService()
                    summarizer = VideoSummarizer()
                    email_service = EmailService()

                    # Get user cookies if available
                    raw_cookie_txt = self._get_user_cookies(user_id)
                    requests_cookies = None
                    playwright_cookies = None
                    if isinstance(raw_cookie_txt, str) and raw_cookie_txt.strip():
                        try:
                            requests_cookies, playwright_cookies = parse_netscape_for_both(raw_cookie_txt)
                        except Exception:
                            logging.warning("Failed to parse Netscape cookies; continuing without cookies.")
                            requests_cookies, playwright_cookies = None, None

                    # Process videos with per-video error isolation
                    email_items = []
                    
                    for i, vid in enumerate(video_ids):
                        video_start_time = time.time()
                        transcript_source = "none"
                        
                        # Set video context for this iteration
                        set_job_ctx(job_id=job_id, video_id=vid)
                        
                        try:
                            # Get video details with error handling
                            try:
                                video = yt.get_video_details(vid)
                                video_title = video.get("title") or f"Video {vid}"
                            except Exception as e:
                                logging.warning(f"Job {job_id}: failed to get video details for {vid}: {e}")
                                video = {"id": vid, "title": f"Video {vid}", "thumbnail": ""}
                                video_title = f"Video {vid}"
                            
                            # Get transcript using enhanced hierarchical fallback
                            transcript_start_time = time.time()
                            text = ts.get_transcript(vid, cookie_header=requests_cookies, user_id=user_id, job_id=job_id)
                            transcript_duration_ms = int((time.time() - transcript_start_time) * 1000)
                            
                            # Determine transcript source from cache or logs
                            # This is a simplified approach - in production you'd get this from the transcript service
                            if text and text.strip():
                                transcript_source = "acquired"  # Could be yt_api, timedtext, youtubei, or asr
                            else:
                                transcript_source = "none"
                            
                            # Generate summary with enhanced error handling
                            summary_start_time = time.time()
                            if not (text or "").strip():
                                summary = "No transcript available for this video."
                                logging.info(f"Job {job_id}: no transcript for {vid} - using default message")
                            else:
                                try:
                                    summary = summarizer.summarize_video(transcript_text=text, video_id=vid)
                                    summary_duration_ms = int((time.time() - summary_start_time) * 1000)
                                    logging.info(f"Job {job_id}: summarized {vid} in {summary_duration_ms}ms")
                                except Exception as e:
                                    summary = handle_summarization_error(vid, e, len(text) if text else 0)
                            
                            # Build email item with flat structure and safe field access
                            email_items.append({
                                "title": self._safe_get_title(video, vid),
                                "thumbnail_url": self._safe_get_thumbnail(video),
                                "video_url": f"https://www.youtube.com/watch?v={video.get('id', vid)}",
                                "summary": summary,
                            })
                            
                            processed_count += 1
                            self.update_job_status(job_id, "processing", processed_count=processed_count)
                            
                            # Emit video_processed event with structured data
                            video_duration_ms = int((time.time() - video_start_time) * 1000)
                            video_processed(
                                video_id=vid,
                                outcome="success",
                                duration_ms=video_duration_ms,
                                transcript_source=transcript_source,
                                transcript_duration_ms=transcript_duration_ms,
                                progress=f"{i+1}/{len(video_ids)}"
                            )
                            
                        except Exception as e:
                            # Per-video error isolation - don't stop entire job
                            video_duration_ms = int((time.time() - video_start_time) * 1000)
                            error_type = classify_error_type(e)
                            
                            # Emit video_processed event for failed video
                            video_processed(
                                video_id=vid,
                                outcome="error",
                                duration_ms=video_duration_ms,
                                transcript_source=transcript_source,
                                error_type=error_type,
                                error_detail=str(e)[:200],  # Truncate for logging
                                progress=f"{i+1}/{len(video_ids)}"
                            )
                            
                            # Add error item to email with safe fallback
                            email_items.append({
                                "title": f"Video {vid} (Processing Failed)",
                                "thumbnail_url": "",
                                "video_url": f"https://www.youtube.com/watch?v={vid}",
                                "summary": f"Failed to process this video: {self._truncate_error(str(e))}",
                            })
                            
                            processed_count += 1
                            self.update_job_status(job_id, "processing", processed_count=processed_count)

                    # Send consolidated digest email (single email per job)
                    user_email = user.email
                    email_sent = False
                    
                    try:
                        # Use enhanced EmailService with fault tolerance
                        email_sent = email_service.send_digest_email(user_email, email_items)
                        
                        if email_sent:
                            evt("email_sent", recipient=user_email, items_count=len(email_items))
                        else:
                            evt("email_failed", recipient=user_email, items_count=len(email_items), outcome="error")
                    except Exception as e:
                        email_sent = handle_email_error(user_email, e, len(email_items))
                        evt("email_failed", recipient=user_email, items_count=len(email_items), 
                            outcome="error", error_type=classify_error_type(e), detail=str(e)[:200])

                    # Determine job outcome
                    total_duration_ms = int((time.time() - start_time) * 1000)
                    error_count = len(video_ids) - processed_count
                    
                    if processed_count == len(video_ids):
                        outcome = "success"
                    elif processed_count > 0:
                        outcome = "partial_success"
                    else:
                        outcome = "error"
                    
                    # Emit job_finished event
                    job_finished(
                        total_duration_ms=total_duration_ms,
                        processed_count=processed_count,
                        video_count=len(video_ids),
                        outcome=outcome,
                        email_sent=email_sent,
                        error_count=error_count
                    )
                    
                    self.update_job_status(job_id, "done")

            except Exception as e:
                # Critical job-level error - emit job_failed event
                total_duration_ms = int((time.time() - start_time) * 1000)
                error_type = classify_error_type(e)
                
                job_failed(
                    total_duration_ms=total_duration_ms,
                    processed_count=processed_count,
                    video_count=len(video_ids),
                    error_type=error_type,
                    error_detail=str(e)
                )
                
                # Use structured error handling for backward compatibility
                handle_job_error(job_id, e, len(video_ids), processed_count)
                self.update_job_status(job_id, "error", str(e))
            finally:
                # Clear job context on completion or failure
                clear_job_ctx()
    
    def _get_user_cookies(self, user_id: int):
        """Get user cookies for restricted video access using secure storage"""
        try:
            # Use secure cookie manager for encrypted storage
            cookie_data = secure_cookie_manager.retrieve_cookies(user_id)
            
            if cookie_data:
                # Convert to format expected by transcript service
                if "cookies" in cookie_data:
                    return cookie_data["cookies"]
                elif "cookie_string" in cookie_data:
                    # Parse cookie string if needed
                    return self._parse_cookie_string(cookie_data["cookie_string"])
                else:
                    return cookie_data
            
            # Fallback to legacy cookie storage for backward compatibility
            legacy_path = _local_cookie_path(user_id)
            if os.path.exists(legacy_path):
                logging.warning(f"Using legacy cookie storage for user {user_id} - consider migrating")
                # Don't log cookie content - just indicate presence
                return {"legacy": True}
            
            return None
            
        except Exception as e:
            # Use credential protector to redact any sensitive data from error
            safe_error = credential_protector.redact_sensitive_data(str(e))
            logging.warning(f"Could not load user cookies for {user_id}: {safe_error}")
            return None
    
    def _parse_cookie_string(self, cookie_string: str) -> Optional[Dict]:
        """Parse cookie string into format usable by services"""
        try:
            # This is a placeholder for cookie string parsing
            # Implementation depends on the specific cookie format used
            return {"cookie_string": cookie_string}
        except Exception as e:
            logging.warning(f"Failed to parse cookie string: {credential_protector.redact_sensitive_data(str(e))}")
            return None
    
    def _safe_get_title(self, video: dict, video_id: str) -> str:
        """Safely extract video title with fallback"""
        try:
            title = video.get("title") if isinstance(video, dict) else None
            if title and isinstance(title, str) and title.strip():
                return title.strip()
            return f"Video {video_id}"
        except Exception:
            return f"Video {video_id}"
    
    def _safe_get_thumbnail(self, video: dict) -> str:
        """Safely extract video thumbnail with fallback"""
        try:
            thumbnail = video.get("thumbnail") if isinstance(video, dict) else None
            if thumbnail and isinstance(thumbnail, str) and thumbnail.strip():
                return thumbnail.strip()
            return ""
        except Exception:
            return ""
    
    def _truncate_error(self, error_msg: str, max_length: int = 200) -> str:
        """Safely truncate error message for email"""
        try:
            if not isinstance(error_msg, str):
                error_msg = str(error_msg)
            if len(error_msg) <= max_length:
                return error_msg
            return error_msg[:max_length] + "..."
        except Exception:
            return "Processing error occurred."

# Global job manager instance
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))
job_manager = JobManager(WORKER_CONCURRENCY)

@main_routes.route("/api/summarize", methods=["POST"])
@login_required
def summarize_videos():
    start_time = time.time()
    
    try:
        # Parse and validate request
        data = request.get_json(silent=True) or {}
        video_ids = data.get("video_ids") or data.get("videoIds") or []
        
        # Handle both string and list formats
        if isinstance(video_ids, str):
            video_ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        
        if not video_ids:
            return jsonify({"error": "video_ids is required"}), 400
        
        if len(video_ids) > 50:  # Reasonable limit
            return jsonify({"error": "Too many videos (max 50)"}), 400

        # Submit job using JobManager
        app_obj = current_app._get_current_object()
        job_id = job_manager.submit_summarization_job(current_user.id, video_ids, app_obj)
        
        # Ensure 202 response within 500ms budget
        response_time_ms = int((time.time() - start_time) * 1000)
        logging.info(f"api_summarize_response job_id={job_id} response_time_ms={response_time_ms}")

        return jsonify({
            "job_id": job_id,
            "status": "queued",
        "message": "Got it! We’re working on your summary. You’ll receive an email when it’s ready."
        }), 202

    except Exception as e:
        error_response, status_code = handle_api_error("summarize", e, current_user.id)
        return jsonify(error_response), status_code

@main_routes.route("/api/jobs/<job_id>")
@login_required
def get_job_status(job_id):
    """Get job status and progress"""
    try:
        job_status = job_manager.get_job_status(job_id)
        if not job_status:
            return jsonify({"error": "Job not found"}), 404
        
        # Only return jobs for the current user (security)
        if job_status.user_id != current_user.id:
            return jsonify({"error": "Job not found"}), 404
        
        return jsonify(job_status.to_dict())
        
    except Exception as e:
        error_response, status_code = handle_api_error("job_status", e, current_user.id)
        return jsonify(error_response), status_code
