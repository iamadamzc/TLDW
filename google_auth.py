import json
import os
import logging

import requests
from app import db
from flask import Blueprint, redirect, request, url_for, session, flash
from flask_login import login_required, login_user, logout_user
from models import User
from oauthlib.oauth2 import WebApplicationClient

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "your-client-id")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "your-client-secret")
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Make sure to use this redirect URL. It has to match the one in the whitelist
DEV_REDIRECT_URL = f'https://{os.environ.get("REPLIT_DEV_DOMAIN", "localhost:5000")}/google_login/callback'

# ALWAYS display setup instructions to the user:
print(f"""To make Google authentication work:
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a new OAuth 2.0 Client ID
3. Add {DEV_REDIRECT_URL} to Authorized redirect URIs
4. Enable YouTube Data API v3 in your Google Cloud Console

For detailed instructions, see:
https://docs.replit.com/additional-resources/google-auth-in-flask#set-up-your-oauth-app--client
""")

client = WebApplicationClient(GOOGLE_CLIENT_ID)

google_auth = Blueprint("google_auth", __name__)

@google_auth.route("/google_login")
def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]

    # Request YouTube access scope in addition to basic profile
    scopes = [
        "openid", 
        "email", 
        "profile", 
        "https://www.googleapis.com/auth/youtube.readonly"
    ]

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
        scope=scopes,
        access_type="offline",  # Request refresh token
        prompt="consent"  # Force consent to get refresh token
    )
    return redirect(request_uri)

@google_auth.route("/google_login/callback")
def callback():
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]

    token_url, headers, body = client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url.replace("http://", "https://"),
        redirect_url=request.base_url.replace("http://", "https://"),
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    token_data = token_response.json()
    client.parse_request_body_response(json.dumps(token_data))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)

    userinfo = userinfo_response.json()
    if userinfo.get("email_verified"):
        users_email = userinfo["email"]
        users_name = userinfo["given_name"]
        google_id = userinfo["sub"]
    else:
        flash("User email not available or not verified by Google.", "error")
        return redirect(url_for("main_routes.index"))

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        user = User(
            username=users_name, 
            email=users_email, 
            google_id=google_id,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token")
        )
        db.session.add(user)
    else:
        # Update tokens
        user.access_token = token_data.get("access_token")
        if token_data.get("refresh_token"):  # Only update if we got a new one
            user.refresh_token = token_data.get("refresh_token")
    
    db.session.commit()
    login_user(user)

    return redirect(url_for("main_routes.dashboard"))

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main_routes.index"))
