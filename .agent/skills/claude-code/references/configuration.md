# Claude-Code - Configuration

**Pages:** 4

---

## Claude Code settings

**URL:** https://code.claude.com/docs/en/settings

**Contents:**
- Claude Code settings
- ​Configuration scopes
  - ​Available scopes
  - ​When to use each scope
  - ​How scopes interact
  - ​What uses scopes
- ​Settings files
  - ​Available settings
  - ​Permission settings
  - ​Sandbox settings

Configure Claude Code with global and project-level settings, and environment variables.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
{
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test:*)",
      "Read(~/.zshrc)"
    ],
    "deny": [
      "Bash(curl:*)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)"
    ]
  },
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp"
  },
  "companyAnnouncements": [
    "Welcome to Acme Corp! Review our code guidelines at docs.acme.com",
    "Reminder: Code reviews required for all PRs",
    "New security policy in effect"
  ]
}
```

Example 2 (json):
```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true,
    "excludedCommands": ["docker"],
    "network": {
      "allowUnixSockets": [
        "/var/run/docker.sock"
      ],
      "allowLocalBinding": true
    }
  },
  "permissions": {
    "deny": [
      "Read(.envrc)",
      "Read(~/.aws/**)"
    ]
  }
}
```

Example 3 (markdown):
```markdown
🤖 Generated with [Claude Code](https://claude.com/claude-code)

   Co-Authored-By: Claude Sonnet 4.5 <[email protected]>
```

Example 4 (markdown):
```markdown
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

---

## Manage Claude's memory

**URL:** https://code.claude.com/docs/en/memory

**Contents:**
- Manage Claude's memory
- ​Determine memory type
- ​CLAUDE.md imports
- ​How Claude looks up memories
- ​Directly edit memories with /memory
- ​Set up project memory
- ​Modular rules with .claude/rules/
  - ​Basic structure
  - ​Path-specific rules
  - ​Glob patterns

Learn how to manage Claude Code’s memory across sessions with different memory locations and best practices.

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
See @README for project overview and @package.json for available npm commands for this project.

# Additional Instructions
- git workflow @docs/git-instructions.md
```

Example 2 (markdown):
```markdown
# Individual Preferences
- @~/.claude/my-project-instructions.md
```

Example 3 (typescript):
```typescript
This code span will not be treated as an import: `@anthropic-ai/claude-code`
```

Example 4 (unknown):
```unknown
your-project/
├── .claude/
│   ├── CLAUDE.md           # Main project instructions
│   └── rules/
│       ├── code-style.md   # Code style guidelines
│       ├── testing.md      # Testing conventions
│       └── security.md     # Security requirements
```

---

## Model configuration

**URL:** https://code.claude.com/docs/en/model-config

**Contents:**
- Model configuration
- ​Available models
  - ​Model aliases
  - ​Setting your model
- ​Special model behavior
  - ​default model setting
  - ​opusplan model setting
  - ​Extended context with [1m]
- ​Checking your current model
- ​Environment variables

Learn about the Claude Code model configuration, including model aliases like opusplan

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# Start with Opus
claude --model opus

# Switch to Sonnet during session
/model sonnet
```

Example 2 (json):
```json
{
    "permissions": {
        ...
    },
    "model": "opus"
}
```

Example 3 (julia):
```julia
# Example of using a full model name with the [1m] suffix
/model anthropic.claude-sonnet-4-5-20250929-v1:0[1m]
```

---

## Status line configuration

**URL:** https://code.claude.com/docs/en/statusline

**Contents:**
- Status line configuration
- ​Create a custom status line
- ​How it Works
- ​JSON Input Structure
- ​Example Scripts
  - ​Simple Status Line
  - ​Git-Aware Status Line
  - ​Python Example
  - ​Node.js Example
  - ​Helper Function Approach

Create a custom status line for Claude Code to display contextual information

Was this page helpful?

**Examples:**

Example 1 (json):
```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0 // Optional: set to 0 to let status line go to edge
  }
}
```

Example 2 (json):
```json
{
  "hook_event_name": "Status",
  "session_id": "abc123...",
  "transcript_path": "/path/to/transcript.json",
  "cwd": "/current/working/directory",
  "model": {
    "id": "claude-opus-4-1",
    "display_name": "Opus"
  },
  "workspace": {
    "current_dir": "/current/working/directory",
    "project_dir": "/original/project/directory"
  },
  "version": "1.0.80",
  "output_style": {
    "name": "default"
  },
  "cost": {
    "total_cost_usd": 0.01234,
    "total_duration_ms": 45000,
    "total_api_duration_ms": 2300,
    "total_lines_added": 156,
    "total_lines_removed": 23
  },
  "context_window": {
    "total_input_tokens": 15234,
    "total_output_tokens": 4521,
    "context_window_size": 200000,
    "used_percentage": 42.5,
    "remaining_percentage": 57.5,
    "current_usage": {
      "input_tokens": 8500,
      "output_tokens": 1200,
      "cache_creation_input_tokens": 5000,
      "cache_read_input_tokens": 2000
    }
  }
}
```

Example 3 (bash):
```bash
#!/bin/bash
# Read JSON input from stdin
input=$(cat)

# Extract values using jq
MODEL_DISPLAY=$(echo "$input" | jq -r '.model.display_name')
CURRENT_DIR=$(echo "$input" | jq -r '.workspace.current_dir')

echo "[$MODEL_DISPLAY] 📁 ${CURRENT_DIR##*/}"
```

Example 4 (bash):
```bash
#!/bin/bash
# Read JSON input from stdin
input=$(cat)

# Extract values using jq
MODEL_DISPLAY=$(echo "$input" | jq -r '.model.display_name')
CURRENT_DIR=$(echo "$input" | jq -r '.workspace.current_dir')

# Show git branch if in a git repo
GIT_BRANCH=""
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    if [ -n "$BRANCH" ]; then
        GIT_BRANCH=" | 🌿 $BRANCH"
    fi
fi

echo "[$MODEL_DISPLAY] 📁 ${CURRENT_DIR##*/}$GIT_BRANCH"
```

---
