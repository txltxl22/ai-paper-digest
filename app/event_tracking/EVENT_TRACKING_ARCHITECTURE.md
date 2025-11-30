# Event Tracking System Architecture

## Overview

The event tracking system has been decoupled from the main application to provide better separation of concerns, maintainability, and extensibility. This document describes the architecture and implementation details.

## Architecture Components

### 1. Backend Event Tracking System (`app/event_tracking/`)

#### Core Modules

- **`event_types.py`**: Defines all allowed event types as an enum for type safety
- **`models.py`**: Data models for events and payloads with validation
- **`event_tracker.py`**: Main event tracking logic and storage operations
- **`routes.py`**: Flask routes for event tracking endpoints

#### Key Features

- **Type Safety**: All event types are defined as enums with validation
- **Data Validation**: Payload validation ensures data integrity
- **Timezone Handling**: Proper client timestamp parsing and timezone conversion
- **Backward Compatibility**: Maintains compatibility with existing user data format
- **Extensible**: Easy to add new event types and tracking capabilities

### 2. Frontend Event Tracking System (`ui/js/event-tracker.js`)

#### Centralized Event Tracking

- **Global Event Tracker**: Single `EventTracker` class manages all frontend events
- **Automatic Tracking**: Global event listeners for common actions
- **Consistent API**: Standardized methods for tracking different event types
- **Error Handling**: Graceful fallback when events fail to send

#### Event Types Supported

- **Article Events**: `mark_read`, `unmark_read`, `open_pdf`
- **Session Events**: `login`, `logout`, `reset`
- **Navigation Events**: `read_list`

## Implementation Details

### Backend Implementation

#### Event Type Definition

```python
class EventType(Enum):
    MARK_READ = "mark_read"
    UNMARK_READ = "unmark_read"
    OPEN_PDF = "open_pdf"
    LOGIN = "login"
    LOGOUT = "logout"
    RESET = "reset"
    READ_LIST = "read_list"
```

#### Event Data Models

```python
@dataclass
class EventPayload:
    type: str
    arxiv_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    ts: Optional[str] = None
    tz_offset_min: Optional[int] = None

@dataclass
class Event:
    ts: str
    type: str
    arxiv_id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    ua: Optional[str] = None
```

#### Main Event Tracker

The `EventTracker` class provides:
- Event validation and processing
- User data management
- Timestamp parsing and timezone conversion
- Event statistics and querying

### Frontend Implementation

#### Centralized Event Tracker

```javascript
class EventTracker {
  constructor() {
    this.endpoint = '/event';
    this.initialized = false;
  }

  track(type, arxivId = null, meta = {}) {
    const payload = {
      type: type,
      arxiv_id: arxivId,
      meta: meta,
      ts: new Date().toISOString(),
      tz_offset_min: new Date().getTimezoneOffset()
    };
    
    navigator.sendBeacon(this.endpoint, JSON.stringify(payload));
  }
}
```

#### Integration with Existing Code

The existing JS files have been updated to use the centralized tracker:

- **`article-actions.js`**: Uses `window.eventTracker.trackMarkRead()`, etc.
- **`user-actions.js`**: Uses `window.eventTracker.trackLogout()`, etc.
- **`detail.html`**: Uses `window.eventTracker.track()` for PDF clicks

## API Endpoints

### POST `/event`
Ingests events from the frontend.

**Request Body:**
```json
{
  "type": "mark_read",
  "arxiv_id": "1234.5678",
  "meta": {"test": "data"},
  "ts": "2025-01-01T00:00:00Z",
  "tz_offset_min": 480
}
```

**Response:**
```json
{
  "status": "ok"
}
```

### GET `/events`
Retrieves events for the current user (debugging/admin).

**Query Parameters:**
- `limit`: Optional limit on number of events

**Response:**
```json
{
  "status": "ok",
  "events": [...]
}
```

### GET `/events/stats`
Gets event statistics for the current user.

**Response:**
```json
{
  "status": "ok",
  "stats": {
    "mark_read": 5,
    "login": 2,
    "open_pdf": 3
  }
}
```

## Data Storage

Events are stored in user JSON files alongside existing user data:

```json
{
  "read": {"1234.5678": "2025-01-01T08:00:00+08:00"},
  "events": [
    {
      "ts": "2025-01-01T08:00:00+08:00",
      "type": "mark_read",
      "arxiv_id": "1234.5678",
      "meta": {},
      "path": "/",
      "ua": "Mozilla/5.0..."
    }
  ]
}
```

## Benefits of Decoupling

### 1. Separation of Concerns
- Event tracking logic is isolated from main application logic
- Clear boundaries between different system components
- Easier to maintain and modify event tracking independently

### 2. Type Safety
- Event types are defined as enums with validation
- Prevents invalid event types from being tracked
- Better IDE support and error detection

### 3. Extensibility
- Easy to add new event types
- Simple to extend tracking capabilities
- Modular design allows for future enhancements

### 4. Testing
- Comprehensive test coverage for event tracking system
- Isolated testing of event tracking functionality
- Better test organization and maintainability

### 5. Frontend Consistency
- Centralized event tracking API
- Consistent event payload structure
- Reduced code duplication across JS files

## Migration from Old System

The decoupled system maintains backward compatibility:

1. **Existing user data format**: No changes required to user data files
2. **Event endpoint**: Same `/event` endpoint with enhanced validation
3. **Frontend integration**: Gradual migration with backward compatibility

### Backward Compatibility Layer

The old `append_event()` function is maintained as a wrapper:

```python
def append_event(uid: str, event_type: str, arxiv_id: str | None = None, meta: dict | None = None, ts: str | None = None):
    """Append a single analytics event for the user (backward compatibility)."""
    from .event_tracking.event_tracker import EventTracker
    tracker = EventTracker(USER_DATA_DIR)
    tracker.track_event(uid, event_type, arxiv_id, meta, ts)
```

## Testing

The event tracking system includes comprehensive tests:

- **Event type validation**: Tests for valid/invalid event types
- **Data model validation**: Tests for payload and event serialization
- **Event tracking**: Tests for tracking valid/invalid events
- **Timestamp parsing**: Tests for timezone conversion
- **Statistics**: Tests for event statistics generation

Run tests with:
```bash
uv run python -m pytest tests/test_event_tracking.py -v
```

## Future Enhancements

Potential improvements for the event tracking system:

1. **Event Analytics**: Add analytics dashboard for event data
2. **Event Filtering**: Add filtering and search capabilities
3. **Event Export**: Add export functionality for event data
4. **Real-time Tracking**: Add real-time event streaming
5. **Event Aggregation**: Add event aggregation and reporting
6. **Privacy Controls**: Add user privacy controls for event tracking