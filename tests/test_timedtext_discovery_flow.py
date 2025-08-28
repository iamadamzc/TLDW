import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from timedtext_service import timedtext_attempt

class TestTimedtextDiscoveryFlow(unittest.TestCase):

    @patch('timedtext_service._create_timedtext_session')
    def test_successful_flow_official_track(self, mock_create_session):
        """
        Verify the ideal flow:
        1. Fetches track list.
        2. Picks the official 'en' track.
        3. Fetches the JSON3 transcript successfully.
        """
        # --- Mock API responses ---
        mock_session = MagicMock()
        
        # Response for the track list
        track_list_xml = """
        <transcript_list>
            <track id="0" name="" lang_code="en" lang_original="English" kind="asr"/>
            <track id="1" name="English" lang_code="en" lang_original="English"/>
        </transcript_list>
        """
        mock_list_response = MagicMock()
        mock_list_response.ok = True
        mock_list_response.text = track_list_xml
        mock_list_response.headers = {'content-type': 'application/xml'}
        
        # Response for the transcript fetch
        transcript_json = """
        {"events": [{"segs": [{"utf8": "Hello world"}]}]}
        """
        mock_transcript_response = MagicMock()
        mock_transcript_response.ok = True
        mock_transcript_response.text = transcript_json
        mock_transcript_response.headers = {'content-type': 'application/json'}

        # Configure session mock to return the responses
        mock_session.get.side_effect = [
            mock_list_response,  # For youtube.com/api/timedtext?type=list
            mock_transcript_response # For youtube.com/api/timedtext?type=track
        ]
        mock_create_session.return_value = mock_session

        # --- Execute ---
        video_id = "test_video_ok"
        result = timedtext_attempt(video_id)

        # --- Assert ---
        self.assertEqual(result, "Hello world")
        
        # Verify calls
        self.assertEqual(mock_session.get.call_count, 2)
        list_call = mock_session.get.call_args_list[0]
        track_call = mock_session.get.call_args_list[1]

        self.assertIn("type=list", list_call.args[0])
        self.assertIn(f"v={video_id}", list_call.args[0])
        
        self.assertIn("type=track", track_call.args[0])
        self.assertIn("id=1", track_call.args[0]) # Should pick official track
        self.assertIn("fmt=json3", track_call.args[0])

    @patch('timedtext_service._create_timedtext_session')
    def test_no_tracks_found(self, mock_create_session):
        """
        Verify it returns None when the track list is empty or invalid.
        """
        mock_session = MagicMock()
        
        # Empty/invalid responses for both list endpoints
        mock_empty_response = MagicMock()
        mock_empty_response.ok = True
        mock_empty_response.text = ""
        mock_empty_response.headers = {'content-type': 'text/plain'}

        mock_session.get.return_value = mock_empty_response
        mock_create_session.return_value = mock_session

        result = timedtext_attempt("test_video_no_tracks")

        self.assertIsNone(result)
        # Called twice: once for youtube, once for video.google
        self.assertEqual(mock_session.get.call_count, 2)

    @patch('timedtext_service._create_timedtext_session')
    def test_html_response_fails_validation(self, mock_create_session):
        """
        Verify that an HTML response is rejected by the validator.
        """
        mock_session = MagicMock()
        
        mock_html_response = MagicMock()
        mock_html_response.ok = True
        mock_html_response.text = "<!DOCTYPE html><html><body>Consent page</body></html>"
        mock_html_response.headers = {'content-type': 'text/html'}

        mock_session.get.return_value = mock_html_response
        mock_create_session.return_value = mock_session

        result = timedtext_attempt("test_video_html")

        self.assertIsNone(result)

    @patch('timedtext_service._create_timedtext_session')
    def test_fallback_to_asr(self, mock_create_session):
        """
        Verify it picks the ASR track if no official track is available.
        """
        mock_session = MagicMock()
        
        track_list_xml = """
        <transcript_list>
            <track id="0" name="" lang_code="en" lang_original="English" kind="asr"/>
            <track id="2" name="" lang_code="de" lang_original="German"/>
        </transcript_list>
        """
        mock_list_response = MagicMock()
        mock_list_response.ok = True
        mock_list_response.text = track_list_xml
        mock_list_response.headers = {'content-type': 'application/xml'}
        
        transcript_json = """
        {"events": [{"segs": [{"utf8": "This is ASR"}]}]}
        """
        mock_transcript_response = MagicMock()
        mock_transcript_response.ok = True
        mock_transcript_response.text = transcript_json
        mock_transcript_response.headers = {'content-type': 'application/json'}

        mock_session.get.side_effect = [mock_list_response, mock_transcript_response]
        mock_create_session.return_value = mock_session

        result = timedtext_attempt("test_video_asr")

        self.assertEqual(result, "This is ASR")
        
        track_call = mock_session.get.call_args_list[1]
        self.assertIn("id=0", track_call.args[0])
        self.assertIn("kind=asr", track_call.args[0])

    @patch('timedtext_service._create_timedtext_session')
    def test_json_fails_xml_fallback_succeeds(self, mock_create_session):
        """
        Verify it tries XML if the JSON3 fetch fails validation.
        """
        mock_session = MagicMock()
        
        track_list_xml = """
        <transcript_list>
            <track id="1" name="English" lang_code="en" lang_original="English"/>
        </transcript_list>
        """
        mock_list_response = MagicMock()
        mock_list_response.ok = True
        mock_list_response.text = track_list_xml
        mock_list_response.headers = {'content-type': 'application/xml'}
        
        # Invalid JSON response
        mock_invalid_json_response = MagicMock()
        mock_invalid_json_response.ok = False
        mock_invalid_json_response.status_code = 404
        mock_invalid_json_response.text = "Not Found"
        mock_invalid_json_response.headers = {'content-type': 'text/plain'}
        
        # Valid XML transcript response
        transcript_xml = """
        <transcript>
            <text start="0.1" dur="1.0">Hello from XML</text>
        </transcript>
        """
        mock_xml_transcript_response = MagicMock()
        mock_xml_transcript_response.ok = True
        mock_xml_transcript_response.text = transcript_xml
        mock_xml_transcript_response.headers = {'content-type': 'application/xml'}

        mock_session.get.side_effect = [
            mock_list_response,
            mock_invalid_json_response,
            mock_xml_transcript_response
        ]
        mock_create_session.return_value = mock_session

        result = timedtext_attempt("test_video_xml_fallback")

        self.assertEqual(result, "Hello from XML")
        
        self.assertEqual(mock_session.get.call_count, 3)
        json_fetch_call = mock_session.get.call_args_list[1]
        xml_fetch_call = mock_session.get.call_args_list[2]

        self.assertIn("fmt=json3", json_fetch_call.args[0])
        self.assertIn("fmt=xml", xml_fetch_call.args[0])

if __name__ == '__main__':
    unittest.main()
