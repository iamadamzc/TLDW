# cookies_routes.py
import os
import tempfile
import re
import logging
from typing import Optional
from flask import Blueprint, request, render_template_string, redirect, url_for, flash
from flask_login import login_required, current_user

bp_cookies = Blueprint("cookies_routes", __name__, url_prefix="/account")

MAX_COOKIE_BYTES = 256 * 1024  # 256 KB limit
NETSCAPE_HEADER_RE = re.compile(r"^\s*#\s*HttpOnly_.*|^\s*#\s*Mozilla.*|^\s*#\s*Cookies\s*for", re.I)


def _cookies_dir() -> str:
    return os.getenv("COOKIE_LOCAL_DIR", "/app/cookies")


def _local_cookie_path(user_id: int) -> str:
    return os.path.join(_cookies_dir(), f"{user_id}.txt")


def _looks_like_netscape_format(sample: str) -> bool:
    # quick sanity check: file starts with comment lines and tab-separated fields appear
    return ("\t" in sample) and (sample.startswith("#") or bool(NETSCAPE_HEADER_RE.match(sample.splitlines()[0])))


def _store_local(user_id: int, data: bytes) -> str:
    cookie_dir = _cookies_dir()
    os.makedirs(cookie_dir, exist_ok=True)
    
    # Set secure permissions on cookie directory
    try:
        os.chmod(cookie_dir, 0o700)
    except Exception as e:
        logging.warning(f"Could not set chmod 700 on cookie directory {cookie_dir}: {e}")
    
    path = _local_cookie_path(user_id)
    with open(path, "wb") as f:
        f.write(data)
    
    # Set secure permissions on cookie file
    try:
        os.chmod(path, 0o600)
    except Exception as e:
        logging.warning(f"Could not set chmod 600 on cookie file {path}: {e}")
    
    return path


def _store_s3_if_configured(user_id: int, data: bytes) -> Optional[str]:
    bucket = os.getenv("COOKIE_S3_BUCKET")
    if not bucket:
        return None
    try:
        import boto3
        s3 = boto3.client("s3")
        key = f"cookies/{user_id}.txt"
        # Write to tmp then upload (no need to keep file on disk)
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(data)
            tmp_path = tf.name
        
        # Upload with explicit SSE-KMS encryption
        s3.upload_file(
            tmp_path, 
            bucket, 
            key,
            ExtraArgs={'ServerSideEncryption': 'aws:kms'}
        )
        os.unlink(tmp_path)
        return f"s3://{bucket}/{key}"
    except Exception as e:
        logging.warning(f"S3 upload failed for user {user_id}: {e}")
        return None




FORM_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Cookies - Advanced Settings</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            padding: 2rem 1rem;
        }
        .container { max-width: 720px; margin: 0 auto; }
        .card { background: white; border-radius: 12px; padding: 2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1.5rem; }
        h1 { font-size: 1.75rem; font-weight: 600; color: #2c3e50; margin-bottom: 0.5rem; }
        .subtitle { color: #6c757d; font-size: 0.95rem; margin-bottom: 2rem; }
        .badge { 
            display: inline-block; 
            padding: 0.35rem 0.75rem; 
            border-radius: 6px; 
            font-size: 0.8rem; 
            font-weight: 500; 
            margin-bottom: 1rem;
        }
        .badge-info { background: #e7f3ff; color: #0066cc; }
        .badge-success { background: #d4edda; color: #155724; }
        .badge-warning { background: #fff3cd; color: #856404; }
        h2 { font-size: 1.25rem; font-weight: 600; color: #2c3e50; margin: 1.5rem 0 1rem; }
        .section-title { font-size: 1rem; font-weight: 600; color: #495057; margin: 1.25rem 0 0.75rem; }
        ul { margin-left: 1.5rem; margin-bottom: 1rem; line-height: 1.7; }
        li { margin-bottom: 0.5rem; color: #495057; }
        code { 
            background: #f1f3f5; 
            padding: 0.2rem 0.5rem; 
            border-radius: 4px; 
            font-size: 0.9rem; 
            color: #e83e8c;
        }
        .alert { 
            padding: 1rem; 
            border-radius: 8px; 
            margin: 1rem 0; 
            border-left: 4px solid;
        }
        .alert-info { background: #e7f3ff; border-color: #0066cc; color: #004085; }
        .alert-warning { background: #fff3cd; border-color: #ffc107; color: #856404; }
        strong { color: #2c3e50; }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 500;
            text-decoration: none;
            border: none;
            cursor: pointer;
            font-size: 0.95rem;
            transition: all 0.2s;
        }
        .btn-primary { background: #0066cc; color: white; }
        .btn-primary:hover { background: #0052a3; }
        .btn-outline { background: white; color: #6c757d; border: 1px solid #dee2e6; }
        .btn-outline:hover { background: #f8f9fa; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-danger:hover { background: #c82333; }
        input[type="file"] { 
            padding: 0.75rem; 
            border: 2px dashed #dee2e6; 
            border-radius: 8px; 
            width: 100%; 
            margin: 1rem 0;
            cursor: pointer;
        }
        input[type="file"]:hover { border-color: #0066cc; background: #f8f9fa; }
        .button-group { display: flex; gap: 1rem; margin-top: 1rem; }
        .flash { 
            padding: 1rem; 
            background: #d4edda; 
            color: #155724; 
            border-radius: 8px; 
            margin-bottom: 1rem;
            border-left: 4px solid #28a745;
        }
        .back-link { color: #6c757d; text-decoration: none; display: inline-block; margin-bottom: 1rem; }
        .back-link:hover { color: #495057; }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← Back to Dashboard</a>
        
        <div class="card">
            <span class="badge badge-info">Advanced Feature</span>
            <h1>YouTube Cookies</h1>
            <p class="subtitle">Optional authentication for special access requirements</p>
            
            <div class="alert alert-info">
                <strong>⚠️ Most users don't need this!</strong> TLDW works automatically for 99% of videos without cookies.
            </div>

            <h2>When You Might Need Cookies</h2>
            <p style="margin-bottom: 0.75rem; color: #495057;">Upload your YouTube cookies only if you encounter these specific issues:</p>
            <ul>
                <li><strong>Age-restricted videos</strong> that require you to be logged in</li>
                <li><strong>Members-only content</strong> from channels you're subscribed to</li>
                <li><strong>Private or unlisted videos</strong> you have permission to access</li>
                <li><strong>Persistent access errors</strong> that don't resolve automatically</li>
            </ul>

            <div class="alert alert-warning">
                <strong>Privacy Note:</strong> Your cookies are stored encrypted and only used to access YouTube transcripts on your behalf. They are never shared or used for any other purpose.
            </div>

            <h2>How to Export Your Cookies</h2>
            <p class="section-title">Step 1: Install Browser Extension</p>
            <ul>
                <li>In Chrome/Brave/Edge, install <strong>"Get cookies.txt LOCALLY"</strong> extension</li>
                <li>Or use any extension that exports cookies in Netscape format</li>
            </ul>
            
            <p class="section-title">Step 2: Export from YouTube</p>
            <ul>
                <li>Go to <code>youtube.com</code> while logged in to your account</li>
                <li>Click the extension icon and choose <strong>Export</strong></li>
                <li>Save the file (usually named <code>cookies.txt</code>)</li>
            </ul>

            <p class="section-title">Step 3: Upload Below</p>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">
                    {% for m in messages %}<p>{{ m }}</p>{% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <div class="card">
            {% if has_cookie %}
                <span class="badge badge-success">✓ Cookies Configured</span>
                <p style="margin: 1rem 0; color: #495057;">Your YouTube cookies are currently active. Videos requiring authentication should process successfully.</p>
                
                <div class="button-group">
                    <form method="POST" enctype="multipart/form-data" style="flex: 1;">
                        <input type="file" name="cookies_file" accept=".txt" required>
                        <button type="submit" class="btn btn-primary">Update Cookies</button>
                    </form>
                </div>
                
                <div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #dee2e6;">
                    <a href="{{ url_for('cookies_routes.delete_cookies') }}" class="btn btn-danger">Delete Cookies</a>
                </div>
            {% else %}
                <form method="POST" enctype="multipart/form-data">
                    <input type="file" name="cookies_file" accept=".txt" required>
                    <div class="button-group">
                        <button type="submit" class="btn btn-primary">Upload Cookies</button>
                        <a href="/" class="btn btn-outline">Cancel</a>
                    </div>
                </form>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""



@bp_cookies.get("/cookies")
@login_required
def cookies_page():
    has_local = os.path.exists(_local_cookie_path(current_user.id))
    return render_template_string(FORM_HTML, has_cookie=has_local)


@bp_cookies.post("/cookies")
@login_required
def cookies_upload():
    file = request.files.get("cookies_file")
    if not file:
        flash("No file uploaded.")
        return redirect(url_for("cookies_routes.cookies_page"))

    data = file.read(MAX_COOKIE_BYTES + 1)
    if not data or len(data) > MAX_COOKIE_BYTES:
        flash("File too large or empty (limit 256 KB).")
        return redirect(url_for("cookies_routes.cookies_page"))

    # Minimal validation
    head = data[:2048].decode(errors="ignore")
    if not _looks_like_netscape_format(head):
        flash("This doesn't look like a Netscape-format cookies file.")
        return redirect(url_for("cookies_routes.cookies_page"))

    # Store locally
    path = _store_local(current_user.id, data)

    # Optional: push to S3 (preferred in production)
    s3_uri = _store_s3_if_configured(current_user.id, data)
    where = s3_uri or path
    flash("Cookies uploaded successfully.")
    logging.info(f"User {current_user.id} uploaded cookies -> {where}")
    return redirect(url_for("cookies_routes.cookies_page"))


@bp_cookies.get("/cookies/delete")
@login_required
def delete_cookies():
    # delete local
    local = _local_cookie_path(current_user.id)
    if os.path.exists(local):
        try:
            os.unlink(local)
        except Exception:
            pass
    # best-effort delete S3
    bucket = os.getenv("COOKIE_S3_BUCKET")
    if bucket:
        try:
            import boto3
            boto3.client("s3").delete_object(Bucket=bucket, Key=f"cookies/{current_user.id}.txt")
        except Exception as e:
            logging.warning(f"S3 cookie delete failed for user {current_user.id}: {e}")
    flash("Cookies deleted.")
    return redirect(url_for("cookies_routes.cookies_page"))