import os
import logging
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

class EmailService:
    def __init__(self):
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        self.api_url = "https://api.resend.com/emails"
        
        if not self.resend_api_key:
            logging.error("RESEND_API_KEY environment variable is required but not set")
            raise ValueError("RESEND_API_KEY environment variable is required")
        
        logging.info("Email service initialized successfully")

    def send_digest_email(self, user_email, summaries_data):
        """
        Send HTML email digest with video summaries
        summaries_data: list of dicts with video info and summaries
        """
        if not user_email or not user_email.strip():
            logging.error("User email is required for sending digest")
            raise ValueError("User email is required")
        
        if not summaries_data or len(summaries_data) == 0:
            logging.error("No summaries data provided for email digest")
            raise ValueError("Summaries data is required")

        try:
            logging.info(f"Preparing to send digest email to {user_email}")
            logging.debug(f"Number of summaries to include: {len(summaries_data)}")
            html_content = self._generate_email_html(summaries_data)
            
            payload = {
                "from": "TL;DW <noreply@resend.dev>",
                "to": [user_email],
                "subject": "Your TL;DW Video Digest",
                "html": html_content
            }

            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }

            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logging.info(f"Email sent successfully to {user_email}")
                return True
            elif response.status_code == 401:
                logging.error(f"Resend API authentication failed - check API key: {response.text}")
                raise requests.exceptions.HTTPError("Resend API authentication failed. Please check your API key.")
            elif response.status_code == 429:
                logging.error(f"Resend API rate limit exceeded: {response.text}")
                raise requests.exceptions.HTTPError("Resend API rate limit exceeded. Please try again later.")
            else:
                logging.error(f"Failed to send email: {response.status_code} - {response.text}")
                raise requests.exceptions.HTTPError(f"Failed to send email: {response.status_code} - {response.text}")

        except Timeout as e:
            logging.error(f"Timeout while sending email: {e}")
            raise Timeout("Email service timeout. Please try again later.")
        except ConnectionError as e:
            logging.error(f"Connection error while sending email: {e}")
            raise ConnectionError("Unable to connect to email service. Please check your internet connection.")
        except RequestException as e:
            logging.error(f"Request error while sending email: {e}")
            raise RequestException(f"Email service request failed: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error sending email: {e}")
            raise Exception(f"Unexpected error while sending email: {str(e)}")

    def _generate_email_html(self, summaries_data):
        """Generate HTML content for the email digest"""
        
        # Build video cards HTML
        video_cards = []
        for data in summaries_data:
            title = self._escape_html(data['title'])
            channel_title = self._escape_html(data.get('channel_title', ''))
            summary = data['summary']
            video_url = f"https://www.youtube.com/watch?v={data['video_id']}"
            thumbnail = data.get('thumbnail', '')
            
            card_html = f"""
            <div style="background: white; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; border: 1px solid #e1e5e9;">
                <div style="padding: 24px; border-bottom: 2px solid #f0f2f5;">
                    <img src="{thumbnail}" alt="Video thumbnail" style="width: 120px; height: 90px; object-fit: cover; border-radius: 8px; float: left; margin-right: 20px; border: 2px solid #e1e5e9;">
                    <div style="font-size: 1.5em; font-weight: bold; margin-bottom: 12px; line-height: 1.3;">
                        <a href="{video_url}" target="_blank" style="color: #2d3748; text-decoration: none; hover: text-decoration: underline;">{title}</a>
                    </div>
                    <div style="color: #718096; font-size: 1.0em; font-weight: 500;">{channel_title}</div>
                    <div style="clear: both;"></div>
                </div>
                <div style="padding: 24px; font-size: 1.1em; line-height: 1.7; color: #4a5568;">
                    {summary}
                </div>
            </div>
            """
            video_cards.append(card_html)
        
        # Combine all video cards
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
    
    def _escape_html(self, text):
        """Escape HTML special characters"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))
