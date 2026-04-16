## ADDED Requirements

### Requirement: SQL Export Download Artifact
The system SHALL provide a structured download artifact when the SQL agent exports large query results to CSV.

#### Scenario: Export tool returns structured file metadata
- **WHEN** `export_to_csv` successfully exports a CSV file
- **THEN** the tool SHALL return a structured result containing `kind=file_export`
- **AND** the result SHALL include a stable `file_id`
- **AND** the result SHALL NOT expose the server absolute file path to the frontend client

### Requirement: SQL Export File Download Endpoint
The system SHALL provide a backend endpoint for downloading exported SQL result files by `file_id`.

#### Scenario: Download exported CSV by file_id
- **WHEN** the frontend requests `GET /api/chat/files/{file_id}` for a valid unexpired export
- **THEN** the backend SHALL resolve the file from managed export metadata
- **AND** the backend SHALL return the CSV file as a downloadable response

#### Scenario: Reject expired or missing export
- **WHEN** the requested export does not exist or has expired
- **THEN** the backend SHALL return an error response
