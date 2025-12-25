# TL;DW - YouTube Video Summarizer

TL;DW is a backend service that lets users pick one or more YouTube videos (often via playlist), then automatically fetches transcripts, summarizes key points with OpenAI, and emails a clean digest via Resend.

## Goal & Flow

1. User selects YouTube videos/playlist through web interface
2. API call to `/api/summarize` returns 202 immediately (asynchronous processing)
3. Background worker processes each video through transcript pipeline
4. AI summarization generates key points for each video
5. Clean digest email sent to user when processing complete

## Core Features

### Transcript Pipeline (Multi-Step, Resilient)
- **youtube-transcript-api**: Human captions → auto-captions
- **YouTube timedtext endpoints**: json3/xml format extraction
- **YouTubei capture**: Playwright intercepts `/youtubei/v1/get_transcript` XHR calls
- **ASR fallback**: HLS/DASH audio → ffmpeg → Deepgram → text

### Processing & Delivery
- **AI Summarization**: OpenAI GPT with custom prompts/style
- **Email Delivery**: Resend service for clean digest emails
- **Asynchronous Jobs**: Background workers handle heavy processing

### Networking & Access
- **Proxy Support**: Oxylabs residential proxies for improved success rates
- **Cookie Management**: Optional Netscape format cookies for enhanced access
- **Fallback Strategy**: Direct connection first, then proxy rotation

### Observability
- **Structured Logging**: Success/failure breadcrumbs at each pipeline step
- **Health Monitoring**: Multiple health check endpoints
- **Error Handling**: Graceful degradation with user-friendly messages

## Architecture

**Runtime**: Python Flask (WSGI) in Docker containers
**Hosting**: AWS App Runner with ECR container registry
**Browser Automation**: Playwright (Chromium) for web scraping
**Media Processing**: ffmpeg for audio extraction and conversion
**Integrations**: Google OAuth, Deepgram ASR, OpenAI, Resend email