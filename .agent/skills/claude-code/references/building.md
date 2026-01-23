# Claude-Code - Building

**Pages:** 8

---

## Agent Skills

**URL:** https://code.claude.com/docs/en/skills

**Contents:**
- Agent Skills
- ​Create your first Skill
- ​How Skills work
  - ​Where Skills live
    - ​Automatic discovery from nested directories
  - ​When to use Skills versus other options
- ​Configure Skills
  - ​Write SKILL.md
    - ​Available metadata fields
    - ​Available string substitutions

Create, manage, and share Skills to extend Claude’s capabilities in Claude Code.

Check available Skills

Create the Skill directory

Load and verify the Skill

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
What Skills are available?
```

Example 2 (unknown):
```unknown
mkdir -p ~/.claude/skills/explaining-code
```

Example 3 (yaml):
```yaml
---
name: explaining-code
description: Explains code with visual diagrams and analogies. Use when explaining how code works, teaching about a codebase, or when the user asks "how does this work?"
---

When explaining code, always include:

1. **Start with an analogy**: Compare the code to something from everyday life
2. **Draw a diagram**: Use ASCII art to show the flow, structure, or relationships
3. **Walk through the code**: Explain step-by-step what happens
4. **Highlight a gotcha**: What's a common mistake or misconception?

Keep explanations conversational. For complex concepts, use multiple analogies.
```

Example 4 (unknown):
```unknown
What Skills are available?
```

---

## Create custom subagents

**URL:** https://code.claude.com/docs/en/sub-agents

**Contents:**
- Create custom subagents
- ​Built-in subagents
- ​Quickstart: create your first subagent
- ​Configure subagents
  - ​Use the /agents command
  - ​Choose the subagent scope
  - ​Write subagent files
    - ​Supported frontmatter fields
  - ​Choose a model
  - ​Control subagent capabilities

Create and use specialized AI subagents in Claude Code for task-specific workflows and improved context management.

Open the subagents interface

Create a new user-level agent

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
A code improvement agent that scans files and suggests improvements
for readability, performance, and best practices. It should explain
each issue, show the current code, and provide an improved version.
```

Example 2 (unknown):
```unknown
Use the code-improver agent to suggest improvements in this project
```

Example 3 (json):
```json
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

Example 4 (yaml):
```yaml
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

---

## Create plugins

**URL:** https://code.claude.com/docs/en/plugins

**Contents:**
- Create plugins
- ​When to use plugins vs standalone configuration
- ​Quickstart
  - ​Prerequisites
  - ​Create your first plugin
- ​Plugin structure overview
- ​Develop more complex plugins
  - ​Add Skills to your plugin
  - ​Add LSP servers to your plugin
  - ​Organize complex plugins

Create custom plugins to extend Claude Code with slash commands, agents, hooks, Skills, and MCP servers.

Create the plugin directory

Create the plugin manifest

Add slash command arguments

Create the plugin structure

Copy your existing files

Test your migrated plugin

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
mkdir my-first-plugin
```

Example 2 (unknown):
```unknown
mkdir my-first-plugin/.claude-plugin
```

Example 3 (json):
```json
{
"name": "my-first-plugin",
"description": "A greeting plugin to learn the basics",
"version": "1.0.0",
"author": {
"name": "Your Name"
}
}
```

Example 4 (unknown):
```unknown
mkdir my-first-plugin/commands
```

---

## Discover and install prebuilt plugins through marketplaces

**URL:** https://code.claude.com/docs/en/discover-plugins

**Contents:**
- Discover and install prebuilt plugins through marketplaces
- ​How marketplaces work
- ​Official Anthropic marketplace
  - ​Code intelligence
  - ​External integrations
  - ​Development workflows
  - ​Output styles
- ​Try it: add the demo marketplace
- ​Add marketplaces
  - ​Add from GitHub

Find and install plugins from marketplaces to extend Claude Code with new commands, agents, and capabilities.

Install individual plugins

Browse available plugins

Was this page helpful?

**Examples:**

Example 1 (python):
```python
/plugin install plugin-name@claude-plugins-official
```

Example 2 (unknown):
```unknown
/plugin marketplace add anthropics/claude-code
```

Example 3 (python):
```python
/plugin install commit-commands@anthropics-claude-code
```

Example 4 (unknown):
```unknown
/commit-commands:commit
```

---

## Get started with Claude Code hooks

**URL:** https://code.claude.com/docs/en/hooks-guide

**Contents:**
- Get started with Claude Code hooks
- ​Hook Events Overview
- ​Quickstart
  - ​Prerequisites
  - ​Step 1: Open hooks configuration
  - ​Step 2: Add a matcher
  - ​Step 3: Add the hook
  - ​Step 4: Save your configuration
  - ​Step 5: Verify your hook
  - ​Step 6: Test your hook

Learn how to customize and extend Claude Code’s behavior by registering shell commands

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
jq -r '"\(.tool_input.command) - \(.tool_input.description // "No description")"' >> ~/.claude/bash-command-log.txt
```

Example 2 (json):
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "jq -r '\"\\(.tool_input.command) - \\(.tool_input.description // \"No description\")\"' >> ~/.claude/bash-command-log.txt"
          }
        ]
      }
    ]
  }
}
```

Example 3 (unknown):
```unknown
cat ~/.claude/bash-command-log.txt
```

Example 4 (unknown):
```unknown
ls - Lists files and directories
```

---

## Output styles

**URL:** https://code.claude.com/docs/en/output-styles

**Contents:**
- Output styles
- ​Built-in output styles
- ​How output styles work
- ​Change your output style
- ​Create a custom output style
  - ​Frontmatter
- ​Comparisons to related features
  - ​Output Styles vs. CLAUDE.md vs. —append-system-prompt
  - ​Output Styles vs. Agents
  - ​Output Styles vs. Custom Slash Commands

Adapt Claude Code for uses beyond software engineering

Was this page helpful?

**Examples:**

Example 1 (yaml):
```yaml
---
name: My Custom Style
description:
  A brief description of what this style does, to be displayed to the user
---

# Custom Style Instructions

You are an interactive CLI tool that helps users with software engineering
tasks. [Your custom instructions here...]

## Specific Behaviors

[Define how the assistant should behave in this style...]
```

---

## Plugins reference

**URL:** https://code.claude.com/docs/en/plugins-reference

**Contents:**
- Plugins reference
- ​Plugin components reference
  - ​Commands
  - ​Agents
  - ​Skills
  - ​Hooks
  - ​MCP servers
  - ​LSP servers
- ​Plugin installation scopes
- ​Plugin manifest schema

Complete technical reference for Claude Code plugin system, including schemas, CLI commands, and component specifications.

Was this page helpful?

**Examples:**

Example 1 (yaml):
```yaml
---
description: What this agent specializes in
capabilities: ["task1", "task2", "task3"]
---

# Agent Name

Detailed description of the agent's role, expertise, and when Claude should invoke it.

## Capabilities
- Specific task the agent excels at
- Another specialized capability
- When to use this agent vs others

## Context and examples
Provide examples of when this agent should be used and what kinds of problems it solves.
```

Example 2 (unknown):
```unknown
skills/
├── pdf-processor/
│   ├── SKILL.md
│   ├── reference.md (optional)
│   └── scripts/ (optional)
└── code-reviewer/
    └── SKILL.md
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
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format-code.sh"
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
  "mcpServers": {
    "plugin-database": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
      "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
      "env": {
        "DB_PATH": "${CLAUDE_PLUGIN_ROOT}/data"
      }
    },
    "plugin-api-client": {
      "command": "npx",
      "args": ["@company/mcp-server", "--plugin-mode"],
      "cwd": "${CLAUDE_PLUGIN_ROOT}"
    }
  }
}
```

---

## Run Claude Code programmatically

**URL:** https://code.claude.com/docs/en/headless

**Contents:**
- Run Claude Code programmatically
- ​Basic usage
- ​Examples
  - ​Get structured output
  - ​Auto-approve tools
  - ​Create a commit
  - ​Customize the system prompt
  - ​Continue conversations
- ​Next steps
- Agent SDK quickstart

Use the Agent SDK to run Claude Code programmatically from the CLI, Python, or TypeScript.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
claude -p "Find and fix the bug in auth.py" --allowedTools "Read,Edit,Bash"
```

Example 2 (julia):
```julia
claude -p "What does the auth module do?"
```

Example 3 (unknown):
```unknown
claude -p "Summarize this project" --output-format json
```

Example 4 (json):
```json
claude -p "Extract the main function names from auth.py" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}'
```

---
