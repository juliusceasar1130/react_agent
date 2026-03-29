## ADDED Requirements

### Requirement: Default Chat Response Presentation

The system SHALL present only the assistant's final answer content in the default chat history view for ordinary users.

#### Scenario: Final answer only after streaming completes
- **WHEN** a streaming chat request completes successfully
- **THEN** the chat history SHALL show only the assistant's finalized message content in the normal message card
- **AND** intermediate status text, tool calls, and tool results SHALL NOT be rendered in the default message body

#### Scenario: Lightweight progress during generation
- **WHEN** the assistant is still generating a streaming response
- **THEN** the interface SHALL provide lightweight transient status feedback outside the persisted history content
- **AND** the in-progress answer text MAY continue streaming in the assistant message area

#### Scenario: Debug mode reveals process details
- **WHEN** internal debug mode is enabled through frontend configuration
- **THEN** the interface SHALL allow rendering process details such as status text, tool calls, tool results, and error detail blocks
- **AND** disabling debug mode again SHALL restore the default final-answer-only presentation

#### Scenario: Error does not leave residual process card
- **WHEN** a streaming request ends with an error event
- **THEN** the interface SHALL settle the round into a concise assistant failure message
- **AND** temporary process-state cards or partially rendered debug detail blocks SHALL NOT remain in the normal history view
