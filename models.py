from app import db
from flask_login import UserMixin
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    google_id = db.Column(db.String(100), unique=True, nullable=False)
    access_token = db.Column(db.Text)  # Store OAuth access token
    refresh_token = db.Column(db.Text)  # Store OAuth refresh token
    selected_playlist_id = db.Column(db.String(100))  # Store user's selected playlist
    
    def __init__(self, username, email, google_id, access_token=None, refresh_token=None):
        self.username = username
        self.email = email
        self.google_id = google_id
        self.access_token = access_token
        self.refresh_token = refresh_token
    
    def __repr__(self):
        return f'<User {self.username}>'

# Simple in-memory storage for user sessions (MVP approach)
user_sessions = {}

def store_user_session(user_id, data):
    """Store user session data in memory"""
    user_sessions[user_id] = data

def get_user_session(user_id):
    """Get user session data from memory"""
    return user_sessions.get(user_id, {})

def update_user_session(user_id, key, value):
    """Update specific key in user session"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    user_sessions[user_id][key] = value
