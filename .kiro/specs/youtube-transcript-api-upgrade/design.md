# Design Document

## Overview

This document outlines the design for upgrading youtube-transcript-api from version 0.6.2 to 1.2.2. The upgrade involves significant API changes from static methods to instance-based methods, requiring updates across the entire codebase.

## Architecture

### API Version Comparison

**Old API (0.6.2):**
```python
# Static methods
transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
```

**New API (1.2.2):**
```python
# Instance-based methods
api = YouTubeTranscriptApi()
transcript_list = api.list(video_id)
transcript = api.fetch(video_id, transcript_info)
```

### Migration Strategy

1. **Wrapper Pattern**: Create a compatibility layer that abstracts the API differences
2. **Direct Migration**: Update all code to use the new API directly
3. **Hybrid Approach**: Support both APIs with feature detection

**Chosen Approach: Direct Migration** - Clean, maintainable, and leverages new features.

## Components and Interfaces

### Core Components to Update

#### 1. TranscriptService Class
- **Location**: `transcript_service.py`
- **Changes**: Update all YouTubeTranscriptApi usage
- **Methods affected**: 
  - `get_captions_via_api()`
  - `_get_transcript_with_fallback()`
  - Cookie and proxy integration

#### 2. Test Files
- **Files**: `test_api.py`, `simple_test.py`, various test files
- **Changes**: Update API calls and assertions
- **New patterns**: Instance creation, list/fetch workflow

#### 3. Requirements File
- **File**: `requirements.txt`
- **Change**: Update version from 0.6.2 to 1.2.2

### New API Workflow

```python
def get_transcript_new_api(video_id, languages=['en'], cookies=None, proxies=None):
    """Get transcript using youtube-transcript-api 1.2.2"""
    try:
        # Create API instance
        api = YouTubeTranscriptApi()
        
        # List available transcripts
        transcript_list = api.list(video_id)
        
        # Find best transcript
        best_transcript = find_best_transcript(transcript_list, languages)
        
        # Fetch transcript content
        kwargs = {}
        if cookies:
            kwargs['cookies'] = cookies
        if proxies:
            kwargs['proxies'] = proxies
            
        transcript = api.fetch(video_id, best_transcript, **kwargs)
        
        return transcript
        
    except Exception as e:
        # Handle API-specific errors
        raise TranscriptApiError(f"New API error: {e}")
```

## Data Models

### Transcript List Structure (New API)
```python
transcript_info = {
    'language': 'en',
    'language_code': 'en', 
    'is_generated': False,
    'is_translatable': True
}
```

### Transcript Segment Structure (Unchanged)
```python
segment = {
    'text': 'Hello world',
    'start': 0.0,
    'duration': 2.5
}
```

## Error Handling

### New Error Types
- **API Structure Errors**: When old methods are called
- **Instance Creation Errors**: When API instantiation fails
- **List/Fetch Errors**: When new methods fail

### Error Recovery Strategy
1. **Detection**: Identify if error is API-version related
2. **Logging**: Provide clear migration guidance
3. **Fallback**: Graceful degradation where possible

## Testing Strategy

### Unit Tests
- Test new API instance creation
- Test list() method with various video types
- Test fetch() method with different transcript types
- Test cookie and proxy integration

### Integration Tests
- End-to-end transcript fetching
- Error handling scenarios
- Performance comparison with old API

### Migration Tests
- Verify all old API calls are updated
- Ensure no breaking changes in public interfaces
- Validate error messages are helpful

## Implementation Phases

### Phase 1: Core API Update
1. Update requirements.txt
2. Update TranscriptService class
3. Update primary transcript fetching logic

### Phase 2: Test Updates
1. Update test_api.py
2. Update other test files
3. Verify all tests pass

### Phase 3: Documentation and Examples
1. Update code comments
2. Update example files
3. Add migration guide

### Phase 4: Validation
1. Run full test suite
2. Test with real video IDs
3. Verify proxy and cookie functionality