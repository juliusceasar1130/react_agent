# Claude-Code - Ide Integrations

**Pages:** 6

---

## Claude Code in Slack

**URL:** https://code.claude.com/docs/en/slack

**Contents:**
- Claude Code in Slack
- ​Use cases
- ​Prerequisites
- ​Setting up Claude Code in Slack
- ​How it works
  - ​Automatic detection
  - ​Context gathering
  - ​Session flow
- ​User interface elements
  - ​App Home

Delegate coding tasks directly from your Slack workspace

Install the Claude App in Slack

Connect your Claude account

Configure Claude Code on the web

Choose your routing mode

Was this page helpful?

---

## Claude Code on desktop

**URL:** https://code.claude.com/docs/en/desktop

**Contents:**
- Claude Code on desktop
- ​Claude Code on desktop (Preview)
- ​Installation
- macOS
- Windows
- ​Features
- ​Using Git worktrees
  - ​Copying files ignored with .gitignore
  - ​Launch Claude Code on the web
- ​Bundled Claude Code version

Run Claude Code tasks locally or on secure cloud infrastructure with the Claude desktop app

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
.env
.env.local
.env.*
**/.claude/settings.local.json
```

Example 2 (markdown):
```markdown
API_KEY=your_api_key
DEBUG=true

# Multiline values - wrap in quotes
CERT="-----BEGIN CERT-----
MIIE...
-----END CERT-----"
```

---

## Claude Code on the web

**URL:** https://code.claude.com/docs/en/claude-code-on-the-web

**Contents:**
- Claude Code on the web
- ​What is Claude Code on the web?
- ​Who can use Claude Code on the web?
- ​Getting started
- ​How it works
- ​Moving tasks between web and terminal
  - ​From terminal to web
    - ​Tips for background tasks
  - ​From web to terminal
    - ​Requirements for teleporting

Run Claude Code tasks asynchronously on secure cloud infrastructure

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
& Fix the authentication bug in src/auth/login.ts
```

Example 2 (unknown):
```unknown
claude --remote "Fix the authentication bug in src/auth/login.ts"
```

Example 3 (unknown):
```unknown
claude --permission-mode plan
```

Example 4 (unknown):
```unknown
& Execute the migration plan we discussed
```

---

## JetBrains IDEs

**URL:** https://code.claude.com/docs/en/jetbrains

**Contents:**
- JetBrains IDEs
- ​Supported IDEs
- ​Features
- ​Installation
  - ​Marketplace Installation
- ​Usage
  - ​From Your IDE
  - ​From External Terminals
- ​Configuration
  - ​Claude Code Settings

Use Claude Code with JetBrains IDEs including IntelliJ, PyCharm, WebStorm, and more

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
claude
> /ide
```

---

## Use Claude Code in VS Code

**URL:** https://code.claude.com/docs/en/vs-code

**Contents:**
- Use Claude Code in VS Code
- ​Prerequisites
- ​Install the extension
- ​Get started
- ​Customize your workflow
  - ​Change the layout
  - ​Switch to terminal mode
- ​VS Code commands and shortcuts
- ​Configure settings
- ​Use third-party providers

Install and configure the Claude Code extension for VS Code. Get AI coding assistance with inline diffs, @-mentions, plan review, and keyboard shortcuts.

Open the Claude Code panel

Configure your provider

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
rm -rf ~/.vscode/globalStorage/anthropic.claude-code
```

---

## Use Claude Code with Chrome (beta)

**URL:** https://code.claude.com/docs/en/chrome

**Contents:**
- Use Claude Code with Chrome (beta)
- ​What the integration enables
- ​Prerequisites
- ​How the integration works
- ​Set up the integration
- ​Try it out
- ​Example workflows
  - ​Test a local web application
  - ​Debug with console logs
  - ​Automate form filling

Connect Claude Code to your browser to test web apps, debug with console logs, and automate browser tasks.

Start Claude Code with Chrome enabled

Verify the connection

Was this page helpful?

**Examples:**

Example 1 (sql):
```sql
claude update
```

Example 2 (unknown):
```unknown
claude --chrome
```

Example 3 (unknown):
```unknown
Go to code.claude.com/docs, click on the search box,
type "hooks", and tell me what results appear
```

Example 4 (json):
```json
I just updated the login form validation. Can you open localhost:3000,
try submitting the form with invalid data, and check if the error
messages appear correctly?
```

---
