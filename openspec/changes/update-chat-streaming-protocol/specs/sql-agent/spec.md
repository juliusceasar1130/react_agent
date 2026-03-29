## MODIFIED Requirements

### Requirement: Streaming Query API

The system SHALL provide a streaming API endpoint for real-time SQL query results at `/api/chat/stream`.

#### Scenario: Structured streaming events
- **WHEN** user sends a POST request to `/api/chat/stream` with `message` and `session_id`
- **THEN** the system SHALL emit structured SSE events containing a `type` field
- **THEN** the event types SHALL include `token`, `status`, `tool_call`, `tool_result`, `final`, and `error`
- **THEN** the transport MAY still emit `[DONE]` as the final SSE marker, but business completion SHALL be determined by `final` or `error`

#### Scenario: Streaming with tool execution
- **WHEN** the SQL agent executes one or more tool calls during streaming
- **THEN** the system SHALL emit `tool_call` events while the call is being assembled or started
- **THEN** the system SHALL emit `tool_result` events when tool output is available
- **THEN** the final event SHALL include aggregated `tool_calls` and `tool_results`

#### Scenario: Streaming persistence on completion or failure
- **WHEN** the stream ends with a `final` event
- **THEN** the system SHALL persist the assistant message together with aggregated `tool_calls` and `tool_results`
- **AND** the final event MAY include persisted message metadata for frontend reconciliation

#### Scenario: Streaming failure visibility
- **WHEN** an exception occurs during stream generation
- **THEN** the system SHALL emit an `error` event before closing the SSE stream
- **THEN** the frontend SHALL be able to display the failure without relying on `[DONE]` as a success signal
