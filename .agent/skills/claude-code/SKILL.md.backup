---
name: claude-code
description: Claude Code CLI and development environment. Use for Claude Code features, tools, workflows, MCP integration, plugins, hooks, configuration, deployment, and AI-assisted development.
---

# Claude-Code Skill

Claude Code CLI and development environment comprehensive knowledge base. This skill combines documentation from multiple official sources to provide complete coverage of Claude Code features, tools, workflows, MCP integration, plugins, hooks, configuration, deployment, and AI-assisted development.

## Multi-Source Synthesis

This skill combines knowledge from **11 official documentation sources**:

| Source | Confidence | Pages |
|--------|------------|-------|
| Getting Started | Medium | 4 |
| Building | Medium | 8 |
| CI/CD | Medium | 2 |
| Configuration | Medium | 4 |
| Deployment | Medium | 7 |
| IDE Integrations | Medium | 6 |
| MCP | Medium | 1 |
| Reference | Medium | 5 |
| Administration | Medium | 9 |
| Troubleshooting | Medium | 1 |
| Legal | Medium | 1 |

**Source Agreements:**
- All sources consistently reference the CLI command structure and flag format
- Configuration scopes (global, project, user) are uniformly documented across all sources
- MCP server installation methods are documented consistently

**No significant discrepancies detected** between sources.

## When to Use This Skill

Use this skill when working with Claude Code in any of these scenarios:

### Core CLI and Commands
- Running Claude Code from the terminal
- Using CLI flags (`--model`, `--max-turns`, `--system-prompt`, etc.)
- Understanding command structure and options

### Configuration and Settings
- Setting up `CLAUDE.md` for project-specific instructions
- Configuring settings in `.claude/settings.json`
- Managing permissions and environment variables
- Setting up model configuration

### Extensibility
- Creating and managing **Skills** for specialized tasks
- Building **plugins** with slash commands, agents, hooks, and MCP servers
- Creating **custom subagents** for specific workflows
- Connecting to external tools via **MCP (Model Context Protocol)**

### Deployment and Integration
- Setting up Claude Code on **Amazon Bedrock**, **Google Vertex AI**, or **Microsoft Foundry**
- Configuring enterprise deployment with proxies and network settings
- Setting up **GitHub Actions** and **GitLab CI/CD** integration

### Development Workflows
- Understanding new codebases efficiently
- Fixing bugs and refactoring code
- Using checkpointing to track and rewind changes
- Managing Claude's memory across sessions

### IDE and Platform Integration
- Using Claude Code in **VS Code**, **JetBrains**, or **Slack**
- Setting up Claude Code **desktop** or **web** interfaces
- Connecting to external services and platforms

## Quick Reference

### Installation

```bash
# macOS via Homebrew
brew install --cask claude-code

# Linux/macOS via install script
curl -fsSL https://claude.ai/install.sh | bash

# Windows via PowerShell
irm https://claude.ai/install.ps1 | iex

# Windows via CMD
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

### CLI Commands and Flags

```bash
# Start Claude Code
claude

# Start with specific model
claude --model opus

# Switch model during session
/model anthropic.claude-sonnet-4-5-20250929-v1:0[1m]

# Start with custom system prompt
claude --system-prompt "You are a Python expert who only writes type-annotated code"

# Read system prompt from file
claude -p --system-prompt-file ./prompts/code-review.txt "Review this PR"

# Append to default system prompt
claude --append-system-prompt "Always use TypeScript and include JSDoc comments"

# Start in plan mode (read-only)
claude --permission-mode plan

# Custom agents configuration
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer",
    "prompt": "You are a senior code reviewer.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  }
}'
```

### MCP Server Configuration

```bash
# Add HTTP-based MCP server
claude mcp add --transport http notion https://mcp.notion.com/mcp

# Add HTTP server with authentication
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"

# Add SSE-based MCP server
claude mcp add --transport sse asana https://mcp.asana.com/sse

# Add local stdio-based server
claude mcp add --transport stdio --env AIRTABLE_API_KEY=YOUR_KEY airtable \
  -- npx -y airtable-mcp-server

# List configured servers
claude mcp list

# Get server details
claude mcp get github

# Remove a server
claude mcp remove github
```

### Environment Variables

```bash
# API Configuration
export ANTHROPIC_API_KEY=your-api-key

# Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# Configure OTLP endpoint (for OTLP exporter)
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer your-token"

# Metrics exporter
export OTEL_METRICS_EXPORTER=otlp

# Enable Amazon Bedrock
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-east-1

# Enable Google Vertex AI
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID=YOUR-PROJECT-ID

# Enable Microsoft Foundry
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_RESOURCE={resource}
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-4-5'

# Corporate proxy
export HTTPS_PROXY='https://proxy.example.com:8080'
```

### Settings Configuration

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
  "sandbox": {
    "enabled": true
  }
}
```

### Slash Commands

```bash
# Create a project command
mkdir -p .claude/commands
echo "Analyze this code for performance issues and suggest optimizations:" > .claude/commands/optimize.md

# Create a personal command
mkdir -p ~/.claude/commands
echo "Review this code for security vulnerabilities:" > ~/.claude/commands/security-review.md

# Command with arguments ($ARGUMENTS placeholder)
echo 'Fix issue #$ARGUMENTS following our coding standards' > .claude/commands/fix-issue.md
# Usage: /fix-issue "123 high-priority" -> "Fix issue #123 high-priority"
```

### GitHub Actions Integration

```yaml
name: Claude Code
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/review"
          claude_args: "--max-turns 5"
```

### GitLab CI/CD Integration

```yaml
stages:
  - ai

claude:
  stage: ai
  image: node:24-alpine3.21
  rules:
    - if: '$CI_PIPELINE_SOURCE == "web"'
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  variables:
    GIT_STRATEGY: fetch
  before_script:
    - apk update
    - apk add --no-cache git curl bash
    - curl -fsSL https://claude.ai/install.sh | bash
  script:
    - claude -p "${AI_FLOW_INPUT:-'Review this MR and implement the requested changes'}" --permission-mode acceptEdits --allowedTools "Bash(*) Read(*) Edit(*) Write(*) mcp__gitlab" --debug
```

### Skill Creation

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

Keep explanations conversational. For multiple analogies.
```

### Checkpointing Commands

```bash
# File operations are automatically tracked
rm file.txt
mv old.txt new.txt
cp source.txt dest.txt

# Rewind unwanted changes
# See checkpoint reference in references/reference.md for details
```

### Plugin Marketplace Creation

```bash
# Create directory structure
mkdir -p my-marketplace/.claude-plugin
mkdir -p my-marketplace/plugins/review-plugin/.claude-plugin
mkdir -p my-marketplace/plugins/review-plugin/commands
```

## Reference Files

This skill includes comprehensive documentation extracted from official Claude Code documentation. Each reference file covers a specific domain:

### getting_started.md (4 pages, Medium confidence)
- Claude Code overview and quickstart
- Common workflows (understanding codebases, fixing bugs, refactoring)
- Enterprise deployment overview
- Basic installation and configuration

### building.md (8 pages, Medium confidence)
- **Agent Skills** - Creating, configuring, and sharing Skills
- **Custom Subagents** - Building specialized AI agents
- **Plugins** - Creating plugins with slash commands, hooks, and MCP servers
- **Output Styles** - Customizing Claude's output behavior

### ci_cd.md (2 pages, Medium confidence)
- **GitHub Actions** - CI/CD integration with Claude Code
- **GitLab CI/CD** - GitLab pipeline integration

### configuration.md (4 pages, Medium confidence)
- **Settings** - Configuration scopes (global, project, user)
- **Memory Management** - CLAUDE.md, .claude/rules/, project memory
- **Model Configuration** - Selecting and configuring models
- **Status Line** - Customizing the CLI status display

### deployment.md (7 pages, Medium confidence)
- **Amazon Bedrock** - AWS deployment configuration
- **Google Vertex AI** - GCP deployment configuration
- **Microsoft Foundry** - Azure deployment configuration
- **Dev Containers** - Development container setup
- **Network Configuration** - Proxy and enterprise network setup

### ide_integrations.md (6 pages, Medium confidence)
- **VS Code** - VS Code extension usage
- **JetBrains** - JetBrains IDE integration
- **Desktop App** - Desktop installation and features
- **Web Interface** - Claude Code on the web
- **Slack** - Using Claude Code in Slack workspace
- **Chrome** - Chrome browser integration (beta)

### mcp.md (1 page, Medium confidence)
- **MCP Servers** - Installing and managing MCP servers
- HTTP, SSE, and stdio transport methods
- Server management commands

### reference.md (5 pages, Medium confidence)
- **CLI Reference** - Complete CLI command documentation
- **Checkpointing** - Automatic tracking and rewinding changes
- **Hooks** - Event-driven automation
- **Interactive Mode** - Interactive features
- **Slash Commands** - Creating custom slash commands

### administration.md (9 pages, Medium confidence)
- **Analytics** - Usage metrics and insights
- **Plugin Marketplaces** - Creating and distributing plugins
- **Data Usage** - Data policies and compliance
- **Identity & Access** - Authentication and authorization
- **Cost Management** - Tracking and optimizing costs
- **Monitoring** - Telemetry and usage monitoring

### troubleshooting.md (1 page, Medium confidence)
- Common issues and solutions
- Debugging tips and error resolution

### legal.md (1 page, Medium confidence)
- Legal and compliance documentation

## Working with This Skill

### For Beginners
1. Start with `references/getting_started.md` for foundational concepts
2. Review the Quick Reference section above for common commands
3. Try basic CLI usage: `claude` to start an interactive session
4. Explore `references/configuration.md` to understand settings

### For Intermediate Users
1. Skip to `references/building.md` to learn about Skills and plugins
2. Review `references/mcp.md` to connect external tools
3. Check `references/ci_cd.md` for CI/CD integration patterns
4. Explore `references/deployment.md` for enterprise deployment options

### For Advanced Users
1. Deep dive into `references/administration.md` for enterprise features
2. Review `references/reference.md` for complete CLI documentation
3. Explore `references/ide_integrations.md` for IDE integrations
4. Check plugin and marketplace creation in `references/building.md`

### Navigating Multi-Source References
- Use `view references/<filename>.md` to read specific documentation
- Each reference file has a table of contents at the start
- Examples include language annotations for syntax highlighting
- Cross-references link between related topics

### Resolving Questions
1. **CLI questions**: Check `references/reference.md`
2. **Configuration questions**: Check `references/configuration.md`
3. **Extensibility questions**: Check `references/building.md`
4. **Deployment questions**: Check `references/deployment.md`
5. **Integration questions**: Check `references/ide_integrations.md`

## Key Concepts

### Skills
Skills are reusable knowledge packages that extend Claude's capabilities. They contain specialized knowledge, behaviors, and instructions. Skills are discovered from:
- `~/.claude/skills/` (user-level)
- Project `.claude/skills/` (project-level)
- Plugin-provided skills

### Agents (Subagents)
Custom subagents are specialized AI assistants configured for specific tasks. They help with:
- Improved context management
- Task-specific instructions
- Controlled tool access
- Model selection per task

### Plugins
Plugins package together multiple extensions:
- Slash commands
- Custom agents
- Hooks
- Skills
- MCP servers

### MCP (Model Context Protocol)
A standardized protocol for connecting Claude to external tools and services. Supports three transport types:
- **HTTP**: Simple request-response
- **SSE (Server-Sent Events)**: Streaming connections
- **Stdio**: Local process communication

### Checkpointing
Automatic tracking of file changes made by Claude, enabling:
- Change history viewing
- Selective rewinding
- Recovery from unwanted modifications

### Configuration Scopes
Settings can be configured at three levels:
- **Global**: `~/.claude/settings.json`
- **Project**: `.claude/settings.json`
- **User**: `~/.claude/user/settings.json`

### Memory Management
Claude's memory spans multiple locations:
- **CLAUDE.md**: Project-level instructions (imported at session start)
- **~/.claude/memory/**: User-level memories
- **.claude/rules/**: Path-specific rules with glob patterns

## Known Discrepancies

**Source Confidence**: All sources are from official documentation with medium confidence. No significant discrepancies were found between sources.

**Documentation URLs**: All reference files include original documentation URLs from `https://code.claude.com/docs/en/` for verification.

**Version Considerations**: Documentation reflects the latest Claude Code features. Some advanced features may require specific versions.

## Resources

### references/
Comprehensive documentation extracted from official Claude Code sources:
- Detailed explanations with full context
- Code examples with proper language annotations
- Original documentation links
- Table of contents for quick navigation

### scripts/
Add helper scripts here for common automation tasks:
- MCP server setup scripts
- Configuration backup/restore
- Plugin scaffolding tools

### assets/
Add templates and examples:
- Plugin manifest templates
- Slash command examples
- Settings configuration examples
- Hook configuration templates

## Updating This Skill

To refresh with the latest documentation:
1. Re-run the documentation scraper with the same configuration
2. Review updated reference files for changes
3. Test CLI commands and examples for accuracy
4. Update this SKILL.md to reflect major changes

## Additional Resources

- **Official Documentation**: https://code.claude.com/docs/en/
- **GitHub Repository**: https://github.com/anthropics/claude-code
- **Issue Reporting**: Use `/bug` command within Claude Code
- **Feedback**: Use session quality surveys when prompted
