## ADDED Requirements

### Requirement: SQL Agent Service Initialization

The system SHALL provide a `SQLAgentService` class that initializes a LangChain Agent with SQL database capabilities.

#### Scenario: Service initialization with MySQL database
- **WHEN** `SQLAgentService` is instantiated
- **THEN** the service SHALL connect to the MySQL database `mds` using `SQLDatabase`
- **THEN** the service SHALL create a `SQLDatabaseToolkit` with appropriate tools
- **THEN** the service SHALL create a LangChain Agent with the SQL system prompt

#### Scenario: Agent uses correct tools
- **WHEN** the SQL Agent is initialized
- **THEN** it SHALL have access to `sql_db_query`, `sql_db_schema`, `sql_db_list_tables`, and `sql_db_query_checker` tools

---

### Requirement: Natural Language to SQL Query

The system SHALL convert natural language questions into syntactically correct SQL queries.

#### Scenario: Simple SELECT query
- **WHEN** user asks "查询所有员工信息"
- **THEN** the agent SHALL generate a valid `SELECT` query
- **THEN** the agent SHALL execute the query and return results

#### Scenario: Query with WHERE clause
- **WHEN** user asks "查询部门为技术部的员工"
- **THEN** the agent SHALL generate a `SELECT` query with appropriate `WHERE` clause
- **THEN** the agent SHALL return filtered results

#### Scenario: Query with ordering and limit
- **WHEN** user asks "查询最近修改的10条记录"
- **THEN** the agent SHALL generate a query with `ORDER BY` and `LIMIT 10`

---

### Requirement: Query Safety Restrictions

The system SHALL prevent execution of DML statements (INSERT, UPDATE, DELETE, DROP).

#### Scenario: DML statement rejected
- **WHEN** user requests to insert/update/delete data
- **THEN** the agent SHALL refuse to execute the query
- **THEN** the agent SHALL return an error message explaining the restriction

#### Scenario: DROP statement rejected
- **WHEN** user requests to drop a table
- **THEN** the agent SHALL refuse to execute the query
- **THEN** the agent SHALL return a security error

---

### Requirement: Non-streaming Query API

The system SHALL provide a non-streaming API endpoint for SQL queries at `/api/chat`.

#### Scenario: Successful non-streaming query
- **WHEN** user sends a POST request to `/api/chat` with message and session_id
- **THEN** the system SHALL return a complete response with query results
- **THEN** the response SHALL include `content` field with the answer

#### Scenario: Query error handling
- **WHEN** user sends an invalid query request
- **THEN** the system SHALL return an error message
- **THEN** the system SHALL log the error for debugging

---

### Requirement: Streaming Query API

The system SHALL provide a streaming API endpoint for real-time SQL query results at `/api/stream`.

#### Scenario: Successful streaming query
- **WHEN** user sends a POST request to `/api/stream` with message and session_id
- **THEN** the system SHALL yield chunks of the response as they are generated
- **THEN** each chunk SHALL include `content` and `is_final` fields
- **THEN** the final chunk SHALL have `is_final: true`

#### Scenario: Streaming with tool execution
- **WHEN** the SQL agent executes tool calls during streaming
- **THEN** the system SHALL yield intermediate results
- **THEN** the final chunk SHALL include tool calls information

---

### Requirement: Session State Persistence

The system SHALL persist SQL Agent session state using PostgresSaver.

#### Scenario: Session state saved
- **WHEN** a SQL query is executed
- **THEN** the conversation history SHALL be saved to PostgreSQL via PostgresSaver
- **THEN** subsequent queries in the same session SHALL have access to conversation history

#### Scenario: Session state restored
- **WHEN** a user continues a previous conversation
- **THEN** the agent SHALL restore the conversation context from PostgresSaver
- **THEN** the agent SHALL be aware of previous queries and results

---

## REMOVED Requirements

### Requirement: Research Agent Service (arXiv)
**Reason**: Replaced by SQL Agent for production data querying
**Migration**: Users should use the new SQL Agent for database queries instead of arXiv paper search

#### Scenario: arXiv tool no longer available
- **WHEN** user requests to search academic papers
- **THEN** the system SHALL indicate the arXiv feature is no longer available
- **AND** the system SHALL suggest using SQL queries instead
