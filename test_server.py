"""
Minimal Flask app for testing transcript extraction fixes without auth.
"""
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from transcript_service import TranscriptService
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <html>
    <body>
        <h1>TL;DW Transcript Test</h1>
        <p>Test the transcript extraction fixes</p>
        
        <h2>Test via Browser:</h2>
        <ul>
            <li><a href="/test/rNxC16mlO60">Test Video: rNxC16mlO60 (Rick Astley)</a></li>
            <li><a href="/test/dQw4w9WgXcQ">Test Video: dQw4w9WgXcQ (Alt)</a></li>
        </ul>
        
        <h2>Test via API:</h2>
        <p>POST to /api/test with JSON: {"video_id": "rNxC16mlO60"}</p>
    </body>
    </html>
    """

@app.route('/test/<video_id>')
def test_video(video_id):
    """Test transcript extraction for a video via browser"""
    print(f"\n{'='*80}")
    print(f"Testing transcript extraction for: {video_id}")
    print('='*80)
    
    service = TranscriptService(use_shared_managers=False)
    
    try:
        transcript = service.get_transcript(
            video_id=video_id,
            language_codes=["en"],
            user_id=None,
            job_id=f"browser_test_{video_id}",
            cookie_header=None
        )
        
        if transcript:
            if isinstance(transcript, list):
                segment_count = len(transcript)
                chars = sum(len(seg.get('text', '')) for seg in transcript)
                preview = transcript[0].get('text', '')[:200] if transcript else ''
            else:
                segment_count = "N/A"
                chars = len(transcript)
                preview = transcript[:200]
            
            return f"""
            <html>
            <body>
                <h1>✅ SUCCESS!</h1>
                <p><strong>Video:</strong> {video_id}</p>
                <p><strong>Segments:</strong> {segment_count}</p>
                <p><strong>Characters:</strong> {chars}</p>
                <p><strong>Preview:</strong></p>
                <pre>{preview}...</pre>
                <p><a href="/">Back to tests</a></p>
            </body>
            </html>
            """
        else:
            return f"""
            <html>
            <body>
                <h1>❌ Failed</h1>
                <p><strong>Video:</strong> {video_id}</p>
                <p>No transcript returned</p>
                <p><a href="/">Back to tests</a></p>
            </body>
            </html>
            """
            
    except Exception as e:
        return f"""
        <html>
        <body>
            <h1>❌ Error</h1>
            <p><strong>Video:</strong> {video_id}</p>
            <p><strong>Error:</strong> {str(e)}</p>
            <p><a href="/">Back to tests</a></p>
        </body>
        </html>
        """, 500

@app.route('/api/test', methods=['POST'])
def api_test():
    """Test transcript extraction via API"""
    data = request.get_json()
    video_id = data.get('video_id')
    
    if not video_id:
        return jsonify({"error": "video_id required"}), 400
    
    print(f"\n{'='*80}")
    print(f"API Test - Video: {video_id}")
    print('='*80)
    
    service = TranscriptService(use_shared_managers=False)
    
    try:
        transcript = service.get_transcript(
            video_id=video_id,
            language_codes=["en"],
            user_id=None,
            job_id=f"api_test_{video_id}",
            cookie_header=None
        )
        
        if transcript:
            if isinstance(transcript, list):
                return jsonify({
                    "status": "success",
                    "video_id": video_id,
                    "segments": len(transcript),
                    "characters": sum(len(seg.get('text', '')) for seg in transcript),
                    "preview": transcript[0].get('text', '')[:200] if transcript else ''
                })
            else:
                return jsonify({
                    "status": "success",
                    "video_id": video_id,
                    "characters": len(transcript),
                    "preview": transcript[:200]
                })
        else:
            return jsonify({
                "status": "failed",
                "video_id": video_id,
                "error": "No transcript returned"
            }), 404
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "video_id": video_id,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print("\n" + "="*80)
    print("TL;DW Transcript Test Server")
    print("="*80)
    print("\nStarting on http://localhost:5001")
    print("\nOpen your browser to:")
    print("  http://localhost:5001")
    print("\nOr test via PowerShell:")
    print('  Invoke-RestMethod -Uri http://localhost:5001/api/test -Method POST -ContentType "application/json" -Body \'{"video_id": "rNxC16mlO60"}\'')
    print("\n" + "="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
