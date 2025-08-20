import logging
import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from youtube_service import YouTubeService, AuthenticationError
from transcript_service import TranscriptService
from summarizer import VideoSummarizer
from email_service import EmailService
from models import update_user_session, get_user_session

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

# ---- lightweight job runner ----
WORKERS = int(os.getenv("WORKER_CONCURRENCY", "2"))
executor = ThreadPoolExecutor(max_workers=WORKERS)
JOBS = {}  # {job_id: {status, error}}

def _run_summarize_job(app, job_id: str, user_id: int, video_ids: list[str]):
    JOBS[job_id] = {"status": "processing", "error": None}
    try:
        with app.app_context():
            from models import User
            user = User.query.get(user_id)
            if not user:
                raise Exception("User not found")

            yt = YouTubeService(user)
            ts = TranscriptService()
            summarizer = VideoSummarizer()
            email_service = EmailService()

            summaries = []
            for vid in video_ids:
                video = yt.get_video_details(vid)
                text = ts.get_transcript(vid, user_cookies=None)
                summary = summarizer.summarize_video(video, text)
                summaries.append({"video": video, "summary": summary})

            user_email = user.email
            email_service.send_digest_email(user_email, summaries)

        JOBS[job_id] = {"status": "done", "error": None}
    except Exception as e:
        logging.exception("Summarize job failed")
        JOBS[job_id] = {"status": "error", "error": str(e)}

@main_routes.route("/api/summarize", methods=["POST"])
@login_required
def summarize_videos():
    payload = request.get_json(force=True) or {}
    video_ids = payload.get("video_ids", [])
    if not video_ids:
        return jsonify({"error": "video_ids is required"}), 400

    job_id = str(uuid4())
    app_obj = current_app._get_current_object()
    JOBS[job_id] = {"status": "queued", "error": None}
    executor.submit(_run_summarize_job, app_obj, job_id, current_user.id, video_ids)

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "message": "Got it! We’re working on your summary. You’ll receive an email when it’s ready."
    }), 202

@main_routes.route("/api/jobs/<job_id>")
@login_required
def get_job_status(job_id):
    info = JOBS.get(job_id)
    if not info:
        return jsonify({"error": "job not found"}), 404
    return jsonify({"job_id": job_id, **info})
