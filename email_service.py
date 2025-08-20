import os
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
            
            payload = {
                "from": f"TL;DW <{self.sender_email}>",
                "to": [user_email],
                "subject": "Your TL;DW Video Digest",
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
                summary = self._escape_html(self._safe_get(item, "summary", "No transcript available."))
                video_url = self._safe_get(item, "video_url", "#")
                thumbnail_url = self._safe_get(item, "thumbnail_url", "")
                
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
                    <div style="padding: 24px; font-size: 1.1em; line-height: 1.7; color: #4a5568;">
                        {summary}
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
    
    def _escape_html(self, text):
        """Escape HTML special characters"""
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
