# Claude-Code - Getting Started

**Pages:** 4

---

## Claude Code overview

**URL:** https://code.claude.com/docs/en/overview

**Contents:**
- Claude Code overview
- ​Get started in 30 seconds
- ​What Claude Code does for you
- ​Why developers love Claude Code
- ​Next steps
- Quickstart
- Common workflows
- Troubleshooting
- IDE setup
- ​Additional resources

Learn about Claude Code, Anthropic’s agentic coding tool that lives in your terminal and helps you turn ideas into code faster than ever before.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
curl -fsSL https://claude.ai/install.sh | bash
```

Example 2 (unknown):
```unknown
irm https://claude.ai/install.ps1 | iex
```

Example 3 (unknown):
```unknown
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

Example 4 (unknown):
```unknown
brew install --cask claude-code
```

---

## Common workflows

**URL:** https://code.claude.com/docs/en/common-workflows

**Contents:**
- Common workflows
- ​Understand new codebases
  - ​Get a quick codebase overview
  - ​Find relevant code
- ​Fix bugs efficiently
- ​Refactor code
- ​Use specialized subagents
- ​Use Plan Mode for safe code analysis
  - ​When to use Plan Mode
  - ​How to use Plan Mode

Learn about common workflows with Claude Code.

Navigate to the project root directory

Ask for a high-level overview

Dive deeper into specific components

Ask Claude to find relevant files

Get context on how components interact

Understand the execution flow

Share the error with Claude

Ask for fix recommendations

Identify legacy code for refactoring

Get refactoring recommendations

Apply the changes safely

Verify the refactoring

View available subagents

Use subagents automatically

Explicitly request specific subagents

Create custom subagents for your workflow

Identify untested code

Generate test scaffolding

Add meaningful test cases

Summarize your changes

Generate a pull request with Claude

Identify undocumented code

Generate documentation

Add an image to the conversation

Ask Claude to analyze the image

Use images for context

Get code suggestions from visual content

Reference a single file

Reference a directory

Reference MCP resources

Name the current session

Understand Git worktrees

Create a new worktree

Run Claude Code in each worktree

Run Claude in another worktree

Manage your worktrees

Use text format (default)

Use streaming JSON format

Create a commands directory in your project

Create a Markdown file for each command

Use your custom command in Claude Code

Create a command file with the $ARGUMENTS placeholder

Use the command with an issue number

Create a commands directory in your home folder

Create a Markdown file for each command

Use your personal custom command

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
cd /path/to/project
```

Example 2 (unknown):
```unknown
> give me an overview of this codebase
```

Example 3 (unknown):
```unknown
> explain the main architecture patterns used here
```

Example 4 (unknown):
```unknown
> what are the key data models?
```

---

## Enterprise deployment overview

**URL:** https://code.claude.com/docs/en/third-party-integrations

**Contents:**
- Enterprise deployment overview
- ​Compare deployment options
- ​Configure proxies and gateways
  - ​Amazon Bedrock
  - ​Microsoft Foundry
  - ​Google Vertex AI
- ​Best practices for organizations
  - ​Invest in documentation and memory
  - ​Simplify deployment
  - ​Start with guided usage

Learn how Claude Code can integrate with various third-party services and infrastructure to meet enterprise deployment requirements.

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# Enable Bedrock
export CLAUDE_CODE_USE_BEDROCK=1
export AWS_REGION=us-east-1

# Configure corporate proxy
export HTTPS_PROXY='https://proxy.example.com:8080'
```

Example 2 (markdown):
```markdown
# Enable Bedrock
export CLAUDE_CODE_USE_BEDROCK=1

# Configure LLM gateway
export ANTHROPIC_BEDROCK_BASE_URL='https://your-llm-gateway.com/bedrock'
export CLAUDE_CODE_SKIP_BEDROCK_AUTH=1  # If gateway handles AWS auth
```

Example 3 (markdown):
```markdown
# Enable Microsoft Foundry
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_RESOURCE=your-resource
export ANTHROPIC_FOUNDRY_API_KEY=your-api-key  # Or omit for Entra ID auth

# Configure corporate proxy
export HTTPS_PROXY='https://proxy.example.com:8080'
```

Example 4 (markdown):
```markdown
# Enable Microsoft Foundry
export CLAUDE_CODE_USE_FOUNDRY=1

# Configure LLM gateway
export ANTHROPIC_FOUNDRY_BASE_URL='https://your-llm-gateway.com'
export CLAUDE_CODE_SKIP_FOUNDRY_AUTH=1  # If gateway handles Azure auth
```

---

## Quickstart

**URL:** https://code.claude.com/docs/en/quickstart

**Contents:**
- Quickstart
- ​Before you begin
- ​Step 1: Install Claude Code
- ​Step 2: Log in to your account
- ​Step 3: Start your first session
- ​Step 4: Ask your first question
- ​Step 5: Make your first code change
- ​Step 6: Use Git with Claude Code
- ​Step 7: Fix a bug or add a feature
- ​Step 8: Test out other common workflows

Welcome to Claude Code!

Be specific with your requests

Use step-by-step instructions

Let Claude explore first

Save time with shortcuts

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
curl -fsSL https://claude.ai/install.sh | bash
```

Example 2 (unknown):
```unknown
irm https://claude.ai/install.ps1 | iex
```

Example 3 (unknown):
```unknown
curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
```

Example 4 (unknown):
```unknown
brew install --cask claude-code
```

---
