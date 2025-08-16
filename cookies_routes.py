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


INSTRUCTIONS_HTML = """
<h2 class="text-xl font-semibold mb-2">Export your YouTube cookies</h2>
<ol class="list-decimal ml-6 space-y-2">
  <li>In Chrome (or Brave/Edge), install <em>Get cookies.txt</em> (or any extension that exports cookies in Netscape format).</li>
  <li>Go to <code>youtube.com</code> while logged in, open the extension, and click <strong>Export</strong>.</li>
  <li>Save the file (usually named <code>cookies.txt</code>).</li>
</ol>
<p class="mt-3">Upload that file here. We store it encrypted at rest (if S3 is configured) and only use it to fetch audio for videos you ask us to summarize. You can delete it any time.</p>
"""

FORM_HTML = """
<!doctype html>
<title>Upload YouTube Cookies</title>
<div style="max-width:720px;margin:2rem auto;font-family:ui-sans-serif,system-ui">
  <h1 class="text-2xl font-bold mb-3">Boost reliability with your YouTube cookies</h1>
  {{ instructions|safe }}
  <form method="POST" enctype="multipart/form-data" class="mt-6 space-y-3">
    <input type="file" name="cookies_file" accept=".txt" required />
    <div>
      <button type="submit">Upload</button>
      {% if has_cookie %}
        <a href="{{ url_for('cookies_routes.delete_cookies') }}" style="margin-left: 1rem; color:#b00">Delete existing cookies</a>
      {% endif %}
    </div>
  </form>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul style="margin-top:1rem;color:#064">
        {% for m in messages %}<li>{{ m }}</li>{% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
</div>
"""


@bp_cookies.get("/cookies")
@login_required
def cookies_page():
    has_local = os.path.exists(_local_cookie_path(current_user.id))
    return render_template_string(FORM_HTML, instructions=INSTRUCTIONS_HTML, has_cookie=has_local)


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