import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from youtube_service import YouTubeService
from transcript_service import TranscriptService
from summarizer import VideoSummarizer
from email_service import EmailService
from models import update_user_session, get_user_session

main_routes = Blueprint("main_routes", __name__)

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
        
        youtube_service = YouTubeService(current_user.access_token)
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
                             selected_playlist_id=selected_playlist_id)
                             
    except Exception as e:
        logging.error(f"Error loading dashboard: {e}")
        flash("The YouTube API requires additional permissions. Please sign out and sign in again to grant YouTube access.", "error")
        return render_template("index.html", 
                             authenticated=True,
                             playlists=[], 
                             videos=[],
                             selected_playlist_id=None)

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
        youtube_service = YouTubeService(current_user.access_token)
        videos = youtube_service.get_playlist_videos(playlist_id)
        
        logging.info(f"Retrieved {len(videos)} videos from playlist {playlist_id}")
        
        # Log first few video titles for debugging
        for i, video in enumerate(videos[:3]):
            logging.info(f"Video {i+1}: {video.get('title', 'No title')}")
        
        return jsonify({"videos": videos})
        
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
        youtube_service = YouTubeService(current_user.access_token)
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
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": f"Error testing Watch Later: {str(e)}"
        })

@main_routes.route("/api/summarize", methods=["POST"])
@login_required
def summarize_videos():
    """API endpoint to summarize selected videos"""
    try:
        logging.info(f"Summarize endpoint called by user: {current_user.email}")
        
        data = request.get_json()
        if not data:
            logging.error("No JSON data received")
            return jsonify({"error": "Invalid request format"}), 400
            
        video_ids = data.get("video_ids", [])
        logging.info(f"Processing {len(video_ids)} video IDs: {video_ids}")
        
        if not video_ids:
            return jsonify({"error": "No videos selected"}), 400
        
        # Check if user has access token
        if not current_user.access_token:
            logging.error("User has no access token")
            return jsonify({"error": "Authentication required. Please sign in again."}), 401

        # Initialize services
        youtube_service = YouTubeService(current_user.access_token)
        transcript_service = TranscriptService()
        summarizer = VideoSummarizer()
        email_service = EmailService()
        
        logging.info("Services initialized successfully")
        
        summaries_data = []
        
        for video_id in video_ids:
            try:
                # Get video details
                video_details = youtube_service.get_video_details(video_id)
                if not video_details:
                    logging.warning(f"Could not get details for video {video_id}")
                    continue
                
                # Get transcript
                transcript = transcript_service.get_transcript(video_id)
                if not transcript:
                    logging.warning(f"Could not get transcript for video {video_id}")
                    continue
                
                # Generate summary
                summary = summarizer.summarize_video(transcript, video_id)
                if not summary:
                    logging.warning(f"Could not generate summary for video {video_id}")
                    continue
                
                summaries_data.append({
                    "video_id": video_id,
                    "title": video_details["title"],
                    "channel_title": video_details["channel_title"],
                    "thumbnail": video_details["thumbnail"],
                    "summary": summary
                })
                
            except Exception as e:
                logging.error(f"Error processing video {video_id}: {e}")
                continue
        
        if not summaries_data:
            return jsonify({"error": "No videos could be processed"}), 500
        
        # Send email digest
        success = email_service.send_digest_email(current_user.email, summaries_data)
        
        if success:
            return jsonify({
                "message": f"TL;DW digest sent to {current_user.email}!",
                "processed_count": len(summaries_data),
                "total_count": len(video_ids)
            })
        else:
            return jsonify({"error": "Failed to send email digest"}), 500
            
    except Exception as e:
        logging.error(f"Error in summarize_videos endpoint: {e}")
        logging.error(f"Error type: {type(e).__name__}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500
