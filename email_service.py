import os
import re
import logging
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

class EmailService:
    def __init__(self):
        self.resend_api_key = os.environ.get("RESEND_API_KEY")
        self.sender_email = os.environ.get("SENDER_EMAIL", "noreply@resend.dev")
        self.api_url = "https://api.resend.com/emails"

        if not self.resend_api_key:
            logging.error("RESEND_API_KEY environment variable is required but not set")
            raise ValueError("RESEND_API_KEY is required")
        if not self.sender_email:
            logging.error("No sender email available")
            raise ValueError("SENDER_EMAIL missing")

        logging.info("Email service initialized successfully")

    def send_digest_email(self, user_email: str, items: list[dict]) -> bool:
        """
        Send consolidated digest email with flat item structure.
        
        Args:
            user_email: Recipient email address
            items: List of dicts with keys: title, thumbnail_url, video_url, summary
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        # Input validation with fault tolerance
        if not isinstance(user_email, str) or not user_email.strip():
            logging.error("Invalid user email provided")
            return False
        
        if not isinstance(items, list):
            logging.error("Items must be a list")
            return False
        
        # Allow empty items list - send email saying no summaries generated
        if len(items) == 0:
            logging.info("No items provided - sending empty digest email")
            items = []

        # Single attempt email delivery (no retries per NFR)
        try:
            logging.info(f"Preparing to send digest email to {user_email}")
            logging.debug(f"Number of items to include: {len(items)}")
            
            # Generate HTML with fault-tolerant template
            html_content = self._generate_email_html(items)
            
            # Generate dynamic subject line based on content
            subject = self._generate_subject_line(items)
            
            payload = {
                "from": f"TL;DW <{self.sender_email}>",
                "to": [user_email],
                "subject": subject,
                "html": html_content
            }

            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            
            # Check response status (accept any 2xx per NFR)
            if 200 <= response.status_code < 300:
                logging.info(f"Email sent successfully to {user_email} (status: {response.status_code})")
                return True
            else:
                # Log error but don't retry (single attempt per NFR)
                logging.error(f"Email delivery failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            # Single attempt - log error and return False (don't crash pipeline)
            logging.error(f"Email delivery error for {user_email}: {e}")
            return False

    def _generate_email_html(self, items: list[dict]) -> str:
        """
        Generate HTML content for the email digest with fault tolerance.
        
        Expected item structure:
        {
            "title": str,
            "thumbnail_url": str, 
            "video_url": str,
            "summary": str
        }
        """
        video_cards = []
        
        for item in items:
            try:
                # Extract fields with safe defaults (never crash on malformed data)
                title = self._escape_html(self._safe_get(item, "title", "(Untitled)"))
                raw_summary = self._safe_get(item, "summary", "No transcript available.")
                video_url = self._safe_get(item, "video_url", "#")
                thumbnail_url = self._safe_get(item, "thumbnail_url", "")
                
                # Convert markdown summary to formatted HTML
                formatted_summary = self._format_summary_html(raw_summary)
                
                # Build video card HTML
                card_html = f"""
                <div style="background: white; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e1e5e9;">
                    <div style="padding: 24px; border-bottom: 2px solid #f0f2f5;">
                        {self._build_thumbnail_html(thumbnail_url)}
                        <div style="font-size: 1.5em; font-weight: bold; margin-bottom: 12px; line-height: 1.3;">
                            <a href="{video_url}" target="_blank" style="color: #2d3748; text-decoration: none;">{title}</a>
                        </div>
                        <div style="clear: both;"></div>
                    </div>
                    <div style="padding: 24px; font-size: 1em; line-height: 1.7; color: #4a5568;">
                        {formatted_summary}
                    </div>
                </div>
                """
                video_cards.append(card_html)
                
            except Exception as e:
                # Never crash on individual item - log and continue
                logging.warning(f"Failed to process email item: {e}")
                continue
        
        # Handle empty items case
        if not video_cards:
            all_videos_html = """
            <div style="background: white; padding: 40px; border-radius: 12px; text-align: center; border: 1px solid #e1e5e9;">
                <p style="margin: 0; color: #718096; font-size: 1.2em;">No summaries were generated for this request.</p>
                <p style="margin: 16px 0 0 0; color: #a0aec0; font-size: 1em;">This may happen if videos don't have available transcripts.</p>
            </div>
            """
        else:
            all_videos_html = "".join(video_cards)
        
        # Complete email HTML
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>TL;DW Video Digest</title>
        </head>
        <body style="font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; line-height: 1.6; color: #2d3748; max-width: 800px; margin: 0 auto; padding: 32px 24px; background-color: #f7fafc;">
            <div style="text-align: center; margin-bottom: 40px; padding: 32px 24px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 16px; box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);">
                <h1 style="margin: 0 0 8px 0; font-size: 2.5em; font-weight: 700; letter-spacing: -0.5px;">TL;DW</h1>
                <p style="margin: 0; font-size: 1.2em; opacity: 0.9; font-weight: 400;">Your Video Digest</p>
            </div>
            
            <div style="margin-bottom: 40px;">
                {all_videos_html}
            </div>
            
            <div style="text-align: center; margin-top: 48px; padding: 24px; background: white; border-radius: 12px; border: 1px solid #e2e8f0;">
                <p style="margin: 0; color: #718096; font-size: 1em; font-weight: 500;">Generated by TL;DW - Making videos digestible, one summary at a time.</p>
                <p style="margin: 8px 0 0 0; color: #a0aec0; font-size: 0.9em;">Thank you for using our service!</p>
            </div>
        </body>
        </html>
        """
        
        return html_content
    
    def _format_summary_html(self, summary: str) -> str:
        """
        Convert GPT markdown summary to well-formatted HTML for email.
        
        Handles:
        - **bold** → <strong>bold</strong>
        - Bullet lists (- item) → <ul><li>
        - Indented subpoints (  - item) → nested styling
        - Newlines → proper paragraph/line breaks
        - Preserves existing <a href> timestamp links from _add_timestamp_links()
        """
        if not summary or not isinstance(summary, str):
            return "<p>No summary available.</p>"
        
        try:
            # Step 1: Temporarily protect existing HTML <a> tags (timestamp links)
            # These were already inserted by summarizer._add_timestamp_links()
            link_placeholders = {}
            link_counter = [0]
            
            def protect_link(match):
                key = f"__LINK_{link_counter[0]}__"
                link_placeholders[key] = match.group(0)
                link_counter[0] += 1
                return key
            
            # Protect <a href="...">...</a> tags
            text = re.sub(r'<a\s+href="[^"]*"[^>]*>[^<]*</a>', protect_link, summary)
            
            # Step 2: Escape remaining HTML characters (but not our placeholders)
            text = (text.replace('&', '&amp;')
                       .replace('<', '&lt;')
                       .replace('>', '&gt;')
                       .replace('"', '&quot;'))
            
            # Step 3: Convert markdown bold **text** → <strong>text</strong>
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            
            # Step 4: Process lines into structured HTML
            lines = text.split('\n')
            html_parts = []
            in_list = False
            in_sublist = False
            
            for line in lines:
                stripped = line.strip()
                
                # Skip empty lines (add spacing)
                if not stripped:
                    if in_sublist:
                        html_parts.append('</ul>')
                        in_sublist = False
                    if in_list:
                        html_parts.append('</ul>')
                        in_list = False
                    html_parts.append('<div style="height: 8px;"></div>')
                    continue
                
                # Detect indented subpoints (starts with spaces/tab + -)
                is_subpoint = bool(re.match(r'^[\s]{2,}-\s', line)) or line.startswith('\t-')
                # Detect main bullet points (starts with - )
                is_bullet = stripped.startswith('- ') and not is_subpoint
                
                if is_subpoint:
                    content = re.sub(r'^[\s]*-\s*', '', line).strip()
                    if not in_sublist:
                        in_sublist = True
                        html_parts.append('<ul style="margin: 4px 0 4px 20px; padding-left: 16px; list-style-type: circle;">')
                    html_parts.append(
                        f'<li style="margin-bottom: 4px; color: #718096; font-size: 0.95em;">{content}</li>'
                    )
                elif is_bullet:
                    content = stripped[2:]  # Remove "- "
                    if in_sublist:
                        html_parts.append('</ul>')
                        in_sublist = False
                    if not in_list:
                        in_list = True
                        html_parts.append('<ul style="margin: 12px 0; padding-left: 20px; list-style-type: disc;">')
                    html_parts.append(
                        f'<li style="margin-bottom: 8px; color: #4a5568;">{content}</li>'
                    )
                else:
                    # Regular text (headings, paragraphs)
                    if in_sublist:
                        html_parts.append('</ul>')
                        in_sublist = False
                    if in_list:
                        html_parts.append('</ul>')
                        in_list = False
                    
                    # Style section headers differently
                    if stripped.startswith('<strong>') and stripped.endswith('</strong>'):
                        html_parts.append(
                            f'<h3 style="margin: 20px 0 8px 0; font-size: 1.1em; color: #2d3748; '
                            f'border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">{stripped}</h3>'
                        )
                    elif '<strong>' in stripped:
                        html_parts.append(f'<p style="margin: 8px 0; color: #4a5568;">{stripped}</p>')
                    else:
                        html_parts.append(f'<p style="margin: 8px 0; color: #4a5568;">{stripped}</p>')
            
            # Close any open lists
            if in_sublist:
                html_parts.append('</ul>')
            if in_list:
                html_parts.append('</ul>')
            
            result = '\n'.join(html_parts)
            
            # Step 5: Restore protected link placeholders
            for key, original_html in link_placeholders.items():
                result = result.replace(key, original_html)
            
            return result
            
        except Exception as e:
            logging.warning(f"Failed to format summary as HTML: {e}")
            # Fallback: at minimum convert newlines to <br> and escape
            fallback = (summary.replace('&', '&amp;')
                              .replace('<', '&lt;')
                              .replace('>', '&gt;')
                              .replace('\n', '<br>'))
            return fallback
    
    def _safe_get(self, item: dict, key: str, default: str) -> str:
        """Safely get value from item dict with default fallback"""
        try:
            if not isinstance(item, dict):
                return default
            value = item.get(key, default)
            return str(value) if value is not None else default
        except Exception:
            return default
    
    def _build_thumbnail_html(self, thumbnail_url: str) -> str:
        """Build thumbnail HTML with fallback for missing images"""
        if thumbnail_url and thumbnail_url.strip():
            return f"""
            <img src="{thumbnail_url}" alt="Video thumbnail" 
                 style="width: 120px; height: 90px; object-fit: cover; border-radius: 8px; 
                        float: left; margin-right: 20px; border: 2px solid #e1e5e9;"
                 onerror="this.style.display='none';">
            """
        else:
            # Placeholder for missing thumbnail
            return f"""
            <div style="width: 120px; height: 90px; background: #f7fafc; border-radius: 8px; 
                        float: left; margin-right: 20px; border: 2px solid #e1e5e9;
                        display: flex; align-items: center; justify-content: center;">
                <span style="color: #a0aec0; font-size: 0.8em;">No Image</span>
            </div>
            """
    
    
    def _generate_subject_line(self, items):
        """
        Generate dynamic subject line based on video content.
        
        Args:
            items: List of video items (each with 'title' key)
            
        Returns:
            str: Formatted subject line
        """
        if not items or len(items) == 0:
            return "Your TL;DW Video Digest"
        
        if len(items) == 1:
            # Single video: use the video title (truncated if needed)
            title = self._safe_get(items[0], "title", "Video")
            # Truncate long titles to keep subject line reasonable
            max_length = 60
            if len(title) > max_length:
                title = title[:max_length].rsplit(' ', 1)[0] + "..."
            return f"TL;DW: {title}"
        
        # Multiple videos: show count
        return f"TL;DW: Your {len(items)} Video Summaries"
    
    def _escape_html(self, text):
        """Escape HTML special characters (used for titles and other plain text)"""
        if not text:
            return ""
        try:
            return (str(text).replace('&', '&amp;')
                           .replace('<', '&lt;')
                           .replace('>', '&gt;')
                           .replace('"', '&quot;')
                           .replace("'", '&#x27;'))
        except Exception:
            return ""
