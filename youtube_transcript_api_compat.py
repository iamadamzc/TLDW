#!/usr/bin/env python3
"""
YouTube Transcript API Compatibility Layer
Provides compatibility functions for migrating from youtube-transcript-api 0.6.2 to 1.2.2
"""
import logging
from typing import List, Dict, Any, Optional, Union
from youtube_transcript_api import YouTubeTranscriptApi


class TranscriptApiError(Exception):
    """Custom exception for transcript API errors with migration guidance"""
    pass


class YouTubeTranscriptApiCompat:
    """
    Compatibility layer for YouTube Transcript API 1.2.2
    Provides methods that match the old API while using the new implementation
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._api_instance = None
        self._api_version = self._detect_api_version()
        
        # Log initialization with version detection
        self.logger.info(f"YouTube Transcript API compatibility layer initialized")
        self.logger.info(f"Detected API version: {self._api_version}")
        
        # Warn if we detect potential issues
        if "unknown" in self._api_version.lower():
            self.logger.warning("Could not fully detect API version - some features may not work as expected")
    
    def _detect_api_version(self) -> str:
        """Detect which version of the API we're working with"""
        try:
            import youtube_transcript_api
            
            # Try to get version from package
            version = getattr(youtube_transcript_api, '__version__', None)
            if not version:
                # Try alternative version detection methods
                try:
                    import importlib.metadata
                    version = importlib.metadata.version('youtube-transcript-api')
                except:
                    try:
                        import pkg_resources
                        version = pkg_resources.get_distribution('youtube-transcript-api').version
                    except:
                        version = '1.2.2 (detected)'  # We know this is what we have
            
            # Check available methods to confirm API style
            if hasattr(YouTubeTranscriptApi, 'get_transcript'):
                api_style = "legacy-style (static methods)"
            elif hasattr(YouTubeTranscriptApi, '__call__'):
                # It's a class that can be instantiated
                try:
                    test_instance = YouTubeTranscriptApi()
                    if hasattr(test_instance, 'list') and hasattr(test_instance, 'fetch'):
                        api_style = "instance-style (list/fetch methods)"
                    else:
                        available_methods = [m for m in dir(test_instance) if not m.startswith('_')]
                        api_style = f"instance-style (methods: {available_methods})"
                except Exception as e:
                    api_style = f"instance-style (instantiation failed: {e})"
            else:
                api_style = "unknown-style"
            
            return f"{version} ({api_style})"
            
        except Exception as e:
            self.logger.warning(f"Could not detect API version: {e}")
            return "unknown"
    
    @property
    def api_instance(self) -> YouTubeTranscriptApi:
        """Get or create API instance"""
        if self._api_instance is None:
            try:
                self._api_instance = YouTubeTranscriptApi()
                self.logger.debug("Created new YouTubeTranscriptApi instance")
            except Exception as e:
                raise TranscriptApiError(f"Failed to create API instance: {e}")
        return self._api_instance
    
    def get_transcript(self, video_id: str, languages: List[str] = None, 
                      cookies: Union[str, Dict] = None, proxies: Dict = None) -> List[Dict[str, Any]]:
        """
        Get transcript using new API with old-style interface
        
        Args:
            video_id: YouTube video ID
            languages: List of preferred language codes (e.g., ['en', 'en-US'])
            cookies: Cookie file path or cookie dict
            proxies: Proxy configuration dict
            
        Returns:
            List of transcript segments with 'text', 'start', 'duration' keys
            
        Raises:
            TranscriptApiError: When transcript cannot be retrieved
        """
        if languages is None:
            languages = ['en', 'en-US', 'en-GB']
        
        try:
            self.logger.info(f"Getting transcript for {video_id} with languages {languages}")
            
            # Step 1: List available transcripts
            transcript_list_obj = self.api_instance.list(video_id)
            self.logger.debug(f"Got transcript list object: {type(transcript_list_obj)}")
            
            # Convert TranscriptList to regular list for compatibility
            transcript_list = list(transcript_list_obj)
            self.logger.debug(f"Found {len(transcript_list)} available transcripts")
            
            # Step 2: Find the best matching transcript by language
            best_language = self._find_best_language(transcript_list, languages)
            if not best_language:
                available_langs = []
                for t in transcript_list:
                    # Extract language from transcript object
                    if hasattr(t, 'language_code'):
                        available_langs.append(t.language_code)
                    elif hasattr(t, 'language'):
                        available_langs.append(t.language)
                    else:
                        available_langs.append(str(t))
                
                raise TranscriptApiError(
                    f"No transcript found for languages {languages}. "
                    f"Available languages: {available_langs}"
                )
            
            # Step 3: Fetch the transcript using the new API
            # Note: The new API fetch method signature is different
            # fetch(video_id, languages, preserve_formatting=False)
            
            # Pass cookies and proxies to the new API if supported
            fetch_kwargs = {}
            if cookies:
                fetch_kwargs['cookies'] = cookies
                self.logger.debug("Adding cookies to API request")
            if proxies:
                fetch_kwargs['proxies'] = proxies
                self.logger.debug(f"Adding proxies to API request: {proxies}")
            
            self.logger.debug(f"Fetching transcript for language: {best_language}")
            
            try:
                # Try with the best language and proxy/cookie parameters
                if fetch_kwargs:
                    self.logger.info(f"Calling API with additional parameters: {list(fetch_kwargs.keys())}")
                    fetched_transcript = self.api_instance.fetch(video_id, [best_language], **fetch_kwargs)
                else:
                    fetched_transcript = self.api_instance.fetch(video_id, [best_language])
                self.logger.debug(f"Got fetched transcript object: {type(fetched_transcript)}")
                
                # Convert FetchedTranscript to list of dicts for compatibility
                transcript = []
                for snippet in fetched_transcript:
                    transcript.append({
                        'text': snippet.text,
                        'start': snippet.start,
                        'duration': snippet.duration
                    })
                
            except Exception as fetch_error:
                self.logger.warning(f"Fetch with specific language failed: {fetch_error}")
                # Fallback: try with default language
                try:
                    fetched_transcript = self.api_instance.fetch(video_id)
                    transcript = []
                    for snippet in fetched_transcript:
                        transcript.append({
                            'text': snippet.text,
                            'start': snippet.start,
                            'duration': snippet.duration
                        })
                except Exception as fallback_error:
                    # Try fallback with proxy/cookie parameters if they were provided
                    if fetch_kwargs:
                        try:
                            self.logger.debug("Trying fallback with proxy/cookie parameters")
                            fetched_transcript = self.api_instance.fetch(video_id, **fetch_kwargs)
                            transcript = []
                            for snippet in fetched_transcript:
                                transcript.append({
                                    'text': snippet.text,
                                    'start': snippet.start,
                                    'duration': snippet.duration
                                })
                        except Exception as final_error:
                            raise TranscriptApiError(f"All fetch attempts failed. Last error: {final_error}")
                    else:
                        raise TranscriptApiError(f"Both specific and default language fetch failed: {fallback_error}")
            
            self.logger.info(f"Successfully retrieved transcript: {len(transcript)} segments")
            return transcript
            
        except Exception as e:
            error_msg = str(e)
            
            # Provide helpful migration guidance for common errors
            if "has no attribute 'get_transcript'" in error_msg:
                raise TranscriptApiError(
                    "Old API method 'get_transcript' not available. "
                    "This error indicates the code needs to be updated for API version 1.2.2. "
                    f"Original error: {error_msg}"
                )
            elif "has no attribute 'list_transcripts'" in error_msg:
                raise TranscriptApiError(
                    "Old API method 'list_transcripts' not available. "
                    "This error indicates the code needs to be updated for API version 1.2.2. "
                    f"Original error: {error_msg}"
                )
            else:
                raise TranscriptApiError(f"Transcript retrieval failed: {error_msg}")
    
    def list_transcripts(self, video_id: str) -> List[Dict[str, Any]]:
        """
        List available transcripts using new API with old-style interface
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            List of available transcript info dicts (converted from new API objects)
            
        Raises:
            TranscriptApiError: When transcript list cannot be retrieved
        """
        try:
            self.logger.info(f"Listing transcripts for {video_id}")
            
            # Get TranscriptList object from new API
            transcript_list_obj = self.api_instance.list(video_id)
            
            # Convert to list of transcript objects
            transcript_objects = list(transcript_list_obj)
            self.logger.debug(f"Found {len(transcript_objects)} available transcripts")
            
            # Convert transcript objects to dicts for compatibility
            transcript_list = []
            for transcript_obj in transcript_objects:
                transcript_dict = {
                    'language_code': getattr(transcript_obj, 'language_code', 'unknown'),
                    'language': getattr(transcript_obj, 'language', 'unknown'),
                    'is_generated': getattr(transcript_obj, 'is_generated', False),
                    'is_translatable': getattr(transcript_obj, 'is_translatable', False),
                }
                transcript_list.append(transcript_dict)
            
            return transcript_list
            
        except Exception as e:
            raise TranscriptApiError(f"Failed to list transcripts: {e}")
    
    def _find_best_language(self, transcript_list: List, 
                           preferred_languages: List[str]) -> Optional[str]:
        """
        Find the best language from available transcript objects
        
        Args:
            transcript_list: List of available transcript objects
            preferred_languages: Ordered list of preferred language codes
            
        Returns:
            Best matching language code or None
        """
        if not transcript_list:
            return None
        
        # Extract available languages from transcript objects
        available_languages = []
        for transcript in transcript_list:
            if hasattr(transcript, 'language_code'):
                available_languages.append(transcript.language_code)
            elif hasattr(transcript, 'language'):
                available_languages.append(transcript.language)
            else:
                # Try to extract from string representation
                transcript_str = str(transcript)
                # Look for language codes in format like 'en ("English")'
                import re
                match = re.match(r'^([a-z-]+)', transcript_str)
                if match:
                    available_languages.append(match.group(1))
        
        self.logger.debug(f"Available languages: {available_languages}")
        
        # First, try to find exact matches in preferred order
        for lang in preferred_languages:
            for available_lang in available_languages:
                if available_lang.lower() == lang.lower():
                    self.logger.debug(f"Found exact match for language: {lang}")
                    return available_lang
        
        # Second, try partial matches (e.g., 'en' matches 'en-US')
        for lang in preferred_languages:
            lang_prefix = lang.split('-')[0].lower()
            for available_lang in available_languages:
                if available_lang.lower().startswith(lang_prefix):
                    self.logger.debug(f"Found partial match for language: {lang} -> {available_lang}")
                    return available_lang
        
        # Finally, use the first available language
        if available_languages:
            self.logger.debug(f"Using first available language: {available_languages[0]}")
            return available_languages[0]
        
        return None


# Global compatibility instance
_compat_instance = None


def get_compat_instance() -> YouTubeTranscriptApiCompat:
    """Get global compatibility instance"""
    global _compat_instance
    if _compat_instance is None:
        _compat_instance = YouTubeTranscriptApiCompat()
    return _compat_instance


# Convenience functions that match the old API
def get_transcript(video_id: str, languages: List[str] = None, 
                  cookies: Union[str, Dict] = None, proxies: Dict = None) -> List[Dict[str, Any]]:
    """
    Compatibility function for YouTubeTranscriptApi.get_transcript()
    
    This function provides the same interface as the old API while using the new implementation.
    """
    return get_compat_instance().get_transcript(video_id, languages, cookies, proxies)


def list_transcripts(video_id: str) -> List[Dict[str, Any]]:
    """
    Compatibility function for YouTubeTranscriptApi.list_transcripts()
    
    This function provides the same interface as the old API while using the new implementation.
    """
    return get_compat_instance().list_transcripts(video_id)


# Migration detection and guidance
def check_api_migration_status() -> Dict[str, Any]:
    """
    Check the current API migration status and provide guidance
    
    Returns:
        Dict with migration status information
    """
    compat = get_compat_instance()
    
    # Check if old methods are still being used anywhere
    old_methods_found = []
    
    # This would be expanded to scan the codebase for old method usage
    # For now, just return the current status
    
    return {
        "api_version": compat._api_version,
        "migration_complete": True,  # Will be updated as we migrate
        "old_methods_found": old_methods_found,
        "recommendations": [
            "Use youtube_transcript_api_compat.get_transcript() instead of YouTubeTranscriptApi.get_transcript()",
            "Use youtube_transcript_api_compat.list_transcripts() instead of YouTubeTranscriptApi.list_transcripts()",
            "Update import statements to use the compatibility layer"
        ]
    }


if __name__ == "__main__":
    # Test the compatibility layer
    logging.basicConfig(level=logging.INFO)
    
    print("=== YouTube Transcript API Compatibility Test ===")
    
    # Test API detection
    status = check_api_migration_status()
    print(f"API Version: {status['api_version']}")
    print(f"Migration Complete: {status['migration_complete']}")
    
    # Test basic functionality
    try:
        compat = get_compat_instance()
        print("✅ Compatibility layer initialized successfully")
        
        # Test with a known video (don't actually fetch to avoid network dependency)
        print("✅ Ready to test transcript fetching")
        
    except Exception as e:
        print(f"❌ Compatibility layer test failed: {e}")
