# Design Document

## Overview

This design adds cookie management accessibility to the main TL;DW dashboard by integrating cookie status indicators and navigation links directly into the authenticated user interface. The solution leverages existing cookie functionality in `cookies_routes.py` while adding visual indicators and easy access points in the main dashboard template.

## Architecture

The design follows the existing Flask blueprint architecture:

- **Frontend Integration**: Modify `templates/index.html` to include cookie status section
- **Backend Support**: Add cookie status helper functions to routes
- **Existing Infrastructure**: Leverage current cookie storage and validation in `cookies_routes.py`

## Components and Interfaces

### 1. Cookie Status Helper Functions

**Location**: `routes.py`

```python
def get_user_cookie_status(user_id: int) -> dict:
    """Get comprehensive cookie status for a user"""
    return {
        'has_cookies': bool,
        'upload_date': Optional[datetime],
        'file_size': Optional[int],
        'is_valid': bool
    }
```

### 2. Dashboard Cookie Section

**Location**: `templates/index.html` (authenticated section)

The cookie management section will be added to the dashboard between the playlist header and playlist selection, featuring:

- **Status Indicator**: Visual badge showing cookie status (active/inactive)
- **Quick Actions**: Upload/manage buttons with appropriate states
- **Information Panel**: Brief explanation of benefits when cookies are not present

### 3. Template Integration Points

**Cookie Status Section Structure**:
```html
<div class="card mb-4" id="cookie-management-section">
    <div class="card-body">
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <h5 class="card-title">
                    <i data-feather="shield"></i> YouTube Cookie Status
                </h5>
                <!-- Status-dependent content -->
            </div>
            <div>
                <!-- Action buttons -->
            </div>
        </div>
    </div>
</div>
```

## Data Models

### Cookie Status Response

```python
{
    'has_cookies': bool,           # Whether user has uploaded cookies
    'upload_date': str,            # ISO format date string (optional)
    'file_size_kb': int,           # File size in KB (optional)
    'is_valid': bool,              # Whether cookie file appears valid
    'status_text': str,            # Human-readable status
    'status_class': str            # CSS class for styling
}
```

## Error Handling

### Cookie File Access Errors
- **Scenario**: File system permission issues
- **Response**: Graceful degradation with generic "unavailable" status
- **User Experience**: Show manage button but indicate potential issues

### Missing Cookie Directory
- **Scenario**: Cookie storage directory doesn't exist
- **Response**: Treat as "no cookies" state
- **User Experience**: Normal upload flow

## Testing Strategy

### Unit Tests
- Cookie status helper function with various file states
- Template rendering with different cookie statuses
- Integration with existing cookie routes

### Integration Tests
- End-to-end cookie upload flow from dashboard
- Status updates after cookie operations
- Navigation between dashboard and cookie management

### User Experience Tests
- Accessibility of cookie management from main interface
- Clear understanding of cookie benefits and status
- Smooth workflow from discovery to upload

## Implementation Details

### Phase 1: Backend Support
1. Add `get_user_cookie_status()` helper function to `routes.py`
2. Modify dashboard route to include cookie status in template context
3. Ensure proper error handling for file system operations

### Phase 2: Frontend Integration
1. Add cookie management section to dashboard template
2. Implement responsive design for different screen sizes
3. Add appropriate icons and styling consistent with existing UI

### Phase 3: User Experience Polish
1. Add informational tooltips or help text
2. Implement smooth transitions and visual feedback
3. Ensure accessibility compliance (ARIA labels, keyboard navigation)

## Security Considerations

- **File Path Validation**: Reuse existing secure path handling from `cookies_routes.py`
- **User Isolation**: Ensure cookie status only shows current user's data
- **Information Disclosure**: Avoid exposing sensitive file system details in status messages

## Performance Considerations

- **File System Calls**: Cache cookie status during request lifecycle
- **Template Rendering**: Minimal impact on dashboard load time
- **Lazy Loading**: Cookie status check only when dashboard is accessed

## Accessibility Features

- **Screen Reader Support**: Proper ARIA labels for status indicators
- **Keyboard Navigation**: All interactive elements accessible via keyboard
- **Visual Indicators**: Color-blind friendly status indicators with icons
- **Clear Language**: Simple, jargon-free explanations of cookie functionality