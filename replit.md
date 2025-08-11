# TL;DW - YouTube Video Summarization Service

## Overview

TL;DW is a web application that generates AI-powered summaries of YouTube videos from user playlists and delivers them via email. The application integrates with Google OAuth for authentication, YouTube API for playlist access, and OpenAI for intelligent summarization. Users can select videos from their YouTube playlists, generate summaries with a single click, and receive formatted email digests containing the summarized content.

## Recent Changes (August 2025)

- **Watch Later Limitation Identified**: YouTube Data API has restricted access to Watch Later playlists, showing 0 videos even when the web interface shows 449 videos. This is an API limitation, not a permissions or timeout issue.
- **Music Playlist Filtering**: Successfully implemented filtering to exclude auto-generated YouTube Music playlists while preserving user-created music playlists.
- **OAuth Scope Enhancement**: Added full YouTube management permissions to enable comprehensive playlist access.
- **Email System**: Fully functional email delivery using Resend API with formatted HTML templates.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
- **Flask-based Architecture**: Uses Flask as the primary web framework with Blueprint-based route organization for modular code structure
- **Authentication System**: Implements Flask-Login with Google OAuth 2.0 for secure user authentication and YouTube API access
- **Database Layer**: SQLAlchemy ORM with SQLite for development (configurable via DATABASE_URL environment variable)

### Frontend Architecture
- **Server-Side Rendering**: Traditional HTML templates with Jinja2 templating engine
- **Bootstrap UI Framework**: Responsive design using Bootstrap 5 with custom CSS for enhanced user experience
- **Progressive Enhancement**: JavaScript handles dynamic interactions like playlist selection and video management
- **Single Page Dashboard**: Main interface shows playlists and videos with real-time updates

### Backend Services Architecture
- **Modular Service Design**: Separate service classes for YouTube API, transcript processing, AI summarization, and email delivery
- **Two-Tier Transcript Strategy**: Primary method uses YouTube's existing transcripts via youtube-transcript-api, fallback uses yt-dlp audio download + Deepgram transcription
- **AI Processing Pipeline**: OpenAI GPT-4o integration with structured prompt engineering for consistent summary formatting
- **Email Service**: Resend API integration for HTML email delivery with formatted video digests

### Data Storage Strategy
- **User Management**: SQLAlchemy models for persistent user data including OAuth tokens and playlist preferences
- **Session Handling**: In-memory session storage for MVP simplicity, avoiding complex state management
- **No Video Caching**: Processes videos on-demand without storing transcript or summary data permanently

### Security and Authentication
- **OAuth 2.0 Flow**: Google OAuth integration with YouTube API scope for playlist access
- **Token Management**: Secure storage of access and refresh tokens in encrypted database fields
- **Environment-Based Configuration**: All API keys and secrets managed through environment variables
- **Proxy-Aware Setup**: ProxyFix middleware for proper request handling in cloud environments

## External Dependencies

### Authentication and APIs
- **Google OAuth 2.0**: User authentication and YouTube API access authorization
- **YouTube Data API v3**: Playlist and video metadata retrieval
- **OpenAI API**: GPT-4o model for video transcript summarization
- **Resend API**: HTML email delivery service for summary digests

### Media Processing Services
- **Deepgram API**: Audio transcription service (fallback when YouTube transcripts unavailable)
- **youtube-transcript-api**: Primary transcript extraction from YouTube's existing captions
- **yt-dlp**: Audio extraction from YouTube videos for transcription fallback

### Development and Deployment
- **Flask Ecosystem**: Flask-SQLAlchemy for database ORM, Flask-Login for session management
- **Python Libraries**: Requests for HTTP calls, OAuthLib for OAuth flow handling, Werkzeug for WSGI utilities
- **Frontend Libraries**: Bootstrap 5 for responsive UI, Feather Icons for iconography

### Database Configuration
- **SQLite**: Default development database (configurable to PostgreSQL or other databases via environment variables)
- **Connection Pooling**: Configured with pool recycling and ping validation for production reliability