## ADDED Requirements

### Requirement: Chat Export Download Card
The chat UI SHALL present a visible download entry for successful SQL CSV export results.

#### Scenario: Render download card from export tool result
- **WHEN** an assistant message contains an `export_to_csv` tool result with `kind=file_export`
- **THEN** the UI SHALL render a download card in the message
- **AND** the card SHALL show at least the filename and a download action

#### Scenario: Keep non-export tool results unchanged
- **WHEN** a tool result does not represent a file export artifact
- **THEN** the default chat rendering SHALL remain unchanged
