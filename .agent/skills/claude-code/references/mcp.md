# Claude-Code - Mcp

**Pages:** 1

---

## Connect Claude Code to tools via MCP

**URL:** https://code.claude.com/docs/en/mcp

**Contents:**
- Connect Claude Code to tools via MCP
- ​What you can do with MCP
- ​Popular MCP servers
- ​Installing MCP servers
  - ​Option 1: Add a remote HTTP server
  - ​Option 2: Add a remote SSE server
  - ​Option 3: Add a local stdio server
  - ​Managing your servers
  - ​Dynamic tool updates
  - ​Plugin-provided MCP servers

Learn how to connect Claude Code to your tools with the Model Context Protocol.

Add the server that requires authentication

Use the /mcp command within Claude Code

Add an MCP server from JSON

Verify the server was added

Import servers from Claude Desktop

Select which servers to import

Verify the servers were imported

List available resources

Reference a specific resource

Multiple resource references

Discover available prompts

Execute a prompt without arguments

Execute a prompt with arguments

Example: URL-only allowlist

Example: Command-only allowlist

Example: Mixed name and command allowlist

Example: Name-only allowlist

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# Basic syntax
claude mcp add --transport http <name> <url>

# Real example: Connect to Notion
claude mcp add --transport http notion https://mcp.notion.com/mcp

# Example with Bearer token
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"
```

Example 2 (markdown):
```markdown
# Basic syntax
claude mcp add --transport sse <name> <url>

# Real example: Connect to Asana
claude mcp add --transport sse asana https://mcp.asana.com/sse

# Example with authentication header
claude mcp add --transport sse private-api https://api.company.com/sse \
  --header "X-API-Key: your-key-here"
```

Example 3 (markdown):
```markdown
# Basic syntax
claude mcp add [options] <name> -- <command> [args...]

# Real example: Add Airtable server
claude mcp add --transport stdio --env AIRTABLE_API_KEY=YOUR_KEY airtable \
  -- npx -y airtable-mcp-server
```

Example 4 (markdown):
```markdown
# List all configured servers
claude mcp list

# Get details for a specific server
claude mcp get github

# Remove a server
claude mcp remove github

# (within Claude Code) Check server status
/mcp
```

---
