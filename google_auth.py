import json
import os
import logging

import requests
from app import db
from flask import Blueprint, redirect, request, url_for, session, flash
from flask_login import login_required, login_user, logout_user
from models import User
from oauthlib.oauth2 import WebApplicationClient

# Standardized Google OAuth environment variable names
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "your-client-id")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "your-client-secret")
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
    scope_string = "openid email profile https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube"

    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url.replace("http://", "https://") + "/callback",
        scope=scope_string,
        access_type="offline",  # Request refresh token
        prompt="consent",  # Force consent to get refresh token
        include_granted_scopes="true"  # Include previously granted scopes
    )
    return redirect(request_uri)

@google_auth.route("/google_login/callback")
def callback():
    try:
        # Check for OAuth error parameters
        error = request.args.get("error")
        if error:
            error_description = request.args.get("error_description", "Unknown OAuth error")
            logging.error(f"OAuth error in callback: {error} - {error_description}")
            flash(f"Authentication failed: {error_description}", "error")
            return redirect(url_for("main_routes.index"))
        
        code = request.args.get("code")
        if not code:
            logging.error("No authorization code received in OAuth callback")
            flash("Authentication failed: No authorization code received", "error")
            return redirect(url_for("main_routes.index"))
        
        logging.info("Processing OAuth callback with authorization code")
        
        # Get Google provider configuration
        try:
            google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
            token_endpoint = google_provider_cfg["token_endpoint"]
        except Exception as e:
            logging.error(f"Failed to get Google provider configuration: {e}")
            flash("Authentication failed: Unable to connect to Google services", "error")
            return redirect(url_for("main_routes.index"))

        # Prepare and make token request
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url.replace("http://", "https://"),
            redirect_url=request.base_url.replace("http://", "https://"),
            code=code,
        )
        
        try:
            token_response = requests.post(
                token_url,
                headers=headers,
                data=body,
                auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
            )
            token_response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Token request failed: {e}")
            flash("Authentication failed: Unable to exchange authorization code for tokens", "error")
            return redirect(url_for("main_routes.index"))

        token_data = token_response.json()
        
        # Validate token response
        if "access_token" not in token_data:
            logging.error(f"No access token in response: {token_data}")
            flash("Authentication failed: Invalid token response from Google", "error")
            return redirect(url_for("main_routes.index"))
        
        # Log token acquisition details
        has_refresh_token = "refresh_token" in token_data
        logging.info(f"Token acquisition successful - Access token: ✓, Refresh token: {'✓' if has_refresh_token else '✗'}")
        
        if not has_refresh_token:
            logging.warning("No refresh token received - user may need to re-authenticate more frequently")
        
        client.parse_request_body_response(json.dumps(token_data))

        # Get user info
        try:
            userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
            uri, headers, body = client.add_token(userinfo_endpoint)
            userinfo_response = requests.get(uri, headers=headers, data=body)
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
        except Exception as e:
            logging.error(f"Failed to get user info: {e}")
            flash("Authentication failed: Unable to get user information from Google", "error")
            return redirect(url_for("main_routes.index"))

        # Validate user info
        if not userinfo.get("email_verified"):
            logging.error("User email not verified by Google")
            flash("User email not available or not verified by Google.", "error")
            return redirect(url_for("main_routes.index"))

        users_email = userinfo["email"]
        users_name = userinfo["given_name"]
        google_id = userinfo["sub"]
        
        logging.info(f"Processing authentication for user: {users_email} (Google ID: {google_id})")

        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        
        if not user:
            logging.info(f"Creating new user: {users_name} ({users_email})")
            
            # Check if username already exists and make it unique if needed
            existing_username = User.query.filter_by(username=users_name).first()
            if existing_username:
                users_name = f"{users_name}_{google_id[-4:]}"  # Add last 4 digits of google_id
                logging.info(f"Username conflict resolved, using: {users_name}")
            
            user = User(
                username=users_name, 
                email=users_email, 
                google_id=google_id,
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token")
            )
            db.session.add(user)
        else:
            logging.info(f"Updating tokens for existing user: {users_email}")
            
            # Update tokens for existing user
            user.access_token = token_data.get("access_token")
            if token_data.get("refresh_token"):  # Only update if we got a new one
                user.refresh_token = token_data.get("refresh_token")
                logging.info("Updated refresh token for existing user")
            else:
                logging.info("No new refresh token received, keeping existing one")
        
        # Validate that we have the required tokens
        if not user.access_token:
            logging.error("No access token available for user after OAuth flow")
            flash("Authentication failed: No access token received", "error")
            return redirect(url_for("main_routes.index"))
        
        if not user.refresh_token:
            logging.warning(f"No refresh token available for user {user.email} - may need frequent re-authentication")
        
        try:
            db.session.commit()
            login_user(user)
            logging.info(f"Successfully authenticated user: {users_email}")
            return redirect(url_for("main_routes.dashboard"))
        except Exception as e:
            logging.error(f"Database error during user authentication: {e}")
            db.session.rollback()
            flash("Authentication failed: Database error", "error")
            return redirect(url_for("main_routes.index"))
            
    except Exception as e:
        logging.error(f"Unexpected error in OAuth callback: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        flash("Authentication failed: An unexpected error occurred", "error")
        return redirect(url_for("main_routes.index"))

@google_auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main_routes.index"))
