# Claude-Code - Reference

**Pages:** 5

---

## Checkpointing

**URL:** https://code.claude.com/docs/en/checkpointing

**Contents:**
- Checkpointing
- ​How checkpoints work
  - ​Automatic tracking
  - ​Rewinding changes
- ​Common use cases
- ​Limitations
  - ​Bash command changes not tracked
  - ​External changes not tracked
  - ​Not a replacement for version control
- ​See also

Automatically track and rewind Claude’s edits to quickly recover from unwanted changes.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
rm file.txt
mv old.txt new.txt
cp source.txt dest.txt
```

---

## CLI reference

**URL:** https://code.claude.com/docs/en/cli-reference

**Contents:**
- CLI reference
- ​CLI commands
- ​CLI flags
  - ​Agents flag format
  - ​System prompt flags
- ​See also

Complete reference for Claude Code command-line interface, including commands and flags.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  },
  "debugger": {
    "description": "Debugging specialist for errors and test failures.",
    "prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
  }
}'
```

Example 2 (unknown):
```unknown
claude --system-prompt "You are a Python expert who only writes type-annotated code"
```

Example 3 (unknown):
```unknown
claude -p --system-prompt-file ./prompts/code-review.txt "Review this PR"
```

Example 4 (unknown):
```unknown
claude --append-system-prompt "Always use TypeScript and include JSDoc comments"
```

---

## Hooks reference

**URL:** https://code.claude.com/docs/en/hooks

**Contents:**
- Hooks reference
- ​Configuration
  - ​Structure
  - ​Project-Specific Hook Scripts
  - ​Plugin hooks
  - ​Hooks in Skills, Agents, and Slash Commands
- ​Prompt-Based Hooks
  - ​How prompt-based hooks work
  - ​Configuration
  - ​Response schema

This page provides reference documentation for implementing hooks in Claude Code.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "ToolPattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command-here"
          }
        ]
      }
    ]
  }
}
```

Example 2 (json):
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/prompt-validator.py"
          }
        ]
      }
    ]
  }
}
```

Example 3 (json):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-style.sh"
          }
        ]
      }
    ]
  }
}
```

Example 4 (json):
```json
{
  "description": "Automatic code formatting",
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

---

## Interactive mode

**URL:** https://code.claude.com/docs/en/interactive-mode

**Contents:**
- Interactive mode
- ​Keyboard shortcuts
  - ​General controls
  - ​Text editing
  - ​Theme and display
  - ​Multiline input
  - ​Quick commands
- ​Vim editor mode
  - ​Mode switching
  - ​Navigation (NORMAL mode)

Complete reference for keyboard shortcuts, input modes, and interactive features in Claude Code sessions.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
! npm test
! git status
! ls -la
```

---

## Slash commands

**URL:** https://code.claude.com/docs/en/slash-commands

**Contents:**
- Slash commands
- ​Built-in slash commands
- ​Custom slash commands
  - ​Syntax
    - ​Parameters
  - ​Command types
    - ​Project commands
    - ​Personal commands
  - ​Features
    - ​Namespacing

Control Claude’s behavior during an interactive session with slash commands.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
/<command-name> [arguments]
```

Example 2 (markdown):
```markdown
# Create a project command
mkdir -p .claude/commands
echo "Analyze this code for performance issues and suggest optimizations:" > .claude/commands/optimize.md
```

Example 3 (markdown):
```markdown
# Create a personal command
mkdir -p ~/.claude/commands
echo "Review this code for security vulnerabilities:" > ~/.claude/commands/security-review.md
```

Example 4 (bash):
```bash
# Command definition
echo 'Fix issue #$ARGUMENTS following our coding standards' > .claude/commands/fix-issue.md

# Usage
> /fix-issue 123 high-priority
# $ARGUMENTS becomes: "123 high-priority"
```

---
