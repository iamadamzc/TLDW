import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import sqlite3
from contextlib import contextmanager

class TranscriptCache:
    """Simple file-based cache for video transcripts with TTL support"""
    
    def __init__(self, cache_dir: str = "transcript_cache", default_ttl_days: int = 7):
        self.cache_dir = cache_dir
        self.default_ttl_days = default_ttl_days
        self.db_path = os.path.join(cache_dir, "transcript_cache.db")
        
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize SQLite database
        self._init_database()
        
        logging.info(f"TranscriptCache initialized with {default_ttl_days} day TTL")
    
    def _init_database(self):
        """Initialize SQLite database for cache metadata"""
        with self._get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transcript_cache (
                    cache_key TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    transcript_length INTEGER NOT NULL,
                    source TEXT NOT NULL
                )
            """)
            
            # Create index for efficient lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_video_lang 
                ON transcript_cache(video_id, language)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at 
                ON transcript_cache(expires_at)
            """)
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _get_cache_key(self, video_id: str, language: str = "en") -> str:
        """Generate cache key for video_id and language combination"""
        key_data = f"{video_id}_{language}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> str:
        """Get file path for cached transcript"""
        return os.path.join(self.cache_dir, f"{cache_key}.txt")
    
    def get(self, video_id: str, language: str = "en") -> Optional[str]:
        """Get cached transcript if available and not expired"""
        cache_key = self._get_cache_key(video_id, language)
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM transcript_cache 
                    WHERE cache_key = ? AND expires_at > ?
                """, (cache_key, datetime.now()))
                
                row = cursor.fetchone()
                if not row:
                    logging.debug(f"No valid cache entry for video {video_id} (lang: {language})")
                    return None
                
                # Read transcript from file
                cache_file_path = self._get_cache_file_path(cache_key)
                if not os.path.exists(cache_file_path):
                    logging.warning(f"Cache file missing for {video_id}, removing database entry")
                    conn.execute("DELETE FROM transcript_cache WHERE cache_key = ?", (cache_key,))
                    return None
                
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    transcript_data = f.read()
                
                # Deserialize JSON if transcript was stored as list
                try:
                    # Try to parse as JSON first (for list format)
                    transcript = json.loads(transcript_data)
                    logging.info(f"Cache hit for video {video_id} (lang: {language}, source: {row['source']})")
                    return transcript
                except json.JSONDecodeError:
                    # If JSON parsing fails, return as plain string (legacy format)
                    logging.info(f"Cache hit for video {video_id} (lang: {language}, source: {row['source']}, legacy format)")
                    return transcript_data
                
        except Exception as e:
            logging.error(f"Error reading from cache for video {video_id}: {e}")
            return None
    
    def set(self, video_id: str, transcript: str, language: str = "en", 
            source: str = "transcript_api", ttl_days: Optional[int] = None) -> bool:
        """Cache transcript with specified TTL"""
        # Handle both list of segments and string formats
        if not transcript:
            logging.warning(f"Attempted to cache empty transcript for video {video_id}")
            return False
        
        # If it's a list, check if it's not empty
        if isinstance(transcript, list):
            if len(transcript) == 0:
                logging.warning(f"Attempted to cache empty transcript list for video {video_id}")
                return False
            # Convert list to JSON string for storage
            transcript = json.dumps(transcript)
        # If it's a string, check if it's not empty/whitespace  
        elif isinstance(transcript, str):
            if not transcript.strip():
                logging.warning(f"Attempted to cache empty transcript for video {video_id}")
                return False
        
        cache_key = self._get_cache_key(video_id, language)
        ttl_days = ttl_days or self.default_ttl_days
        
        try:
            # Calculate expiration time
            created_at = datetime.now()
            expires_at = created_at + timedelta(days=ttl_days)
            
            # Write transcript to file
            cache_file_path = self._get_cache_file_path(cache_key)
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            # Update database
            with self._get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO transcript_cache 
                    (cache_key, video_id, language, created_at, expires_at, transcript_length, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (cache_key, video_id, language, created_at, expires_at, len(transcript), source))
            
            logging.info(f"Cached transcript for video {video_id} (lang: {language}, "
                        f"length: {len(transcript)}, ttl: {ttl_days} days, source: {source})")
            return True
            
        except Exception as e:
            logging.error(f"Error caching transcript for video {video_id}: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries and return count of removed items"""
        removed_count = 0
        
        try:
            with self._get_db_connection() as conn:
                # Get expired entries
                cursor = conn.execute("""
                    SELECT cache_key FROM transcript_cache 
                    WHERE expires_at <= ?
                """, (datetime.now(),))
                
                expired_keys = [row['cache_key'] for row in cursor.fetchall()]
                
                # Remove files and database entries
                for cache_key in expired_keys:
                    cache_file_path = self._get_cache_file_path(cache_key)
                    if os.path.exists(cache_file_path):
                        os.remove(cache_file_path)
                    
                    conn.execute("DELETE FROM transcript_cache WHERE cache_key = ?", (cache_key,))
                    removed_count += 1
                
                if removed_count > 0:
                    logging.info(f"Cleaned up {removed_count} expired cache entries")
                
        except Exception as e:
            logging.error(f"Error during cache cleanup: {e}")
        
        return removed_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with self._get_db_connection() as conn:
                # Total entries
                cursor = conn.execute("SELECT COUNT(*) as total FROM transcript_cache")
                total = cursor.fetchone()['total']
                
                # Valid (non-expired) entries
                cursor = conn.execute("""
                    SELECT COUNT(*) as valid FROM transcript_cache 
                    WHERE expires_at > ?
                """, (datetime.now(),))
                valid = cursor.fetchone()['valid']
                
                # Expired entries
                expired = total - valid
                
                # Source breakdown
                cursor = conn.execute("""
                    SELECT source, COUNT(*) as count FROM transcript_cache 
                    WHERE expires_at > ?
                    GROUP BY source
                """, (datetime.now(),))
                source_breakdown = {row['source']: row['count'] for row in cursor.fetchall()}
                
                # Cache size on disk
                cache_size_bytes = 0
                if os.path.exists(self.cache_dir):
                    for filename in os.listdir(self.cache_dir):
                        if filename.endswith('.txt'):
                            file_path = os.path.join(self.cache_dir, filename)
                            cache_size_bytes += os.path.getsize(file_path)
                
                return {
                    "total_entries": total,
                    "valid_entries": valid,
                    "expired_entries": expired,
                    "cache_size_mb": round(cache_size_bytes / (1024 * 1024), 2),
                    "source_breakdown": source_breakdown,
                    "default_ttl_days": self.default_ttl_days
                }
                
        except Exception as e:
            logging.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    def clear_all(self) -> bool:
        """Clear all cache entries (for testing/maintenance)"""
        try:
            with self._get_db_connection() as conn:
                conn.execute("DELETE FROM transcript_cache")
            
            # Remove all cache files
            if os.path.exists(self.cache_dir):
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.txt'):
                        file_path = os.path.join(self.cache_dir, filename)
                        os.remove(file_path)
            
            logging.info("Cleared all cache entries")
            return True
            
        except Exception as e:
            logging.error(f"Error clearing cache: {e}")
            return False