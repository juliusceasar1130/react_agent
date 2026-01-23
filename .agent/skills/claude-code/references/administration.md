# Claude-Code - Administration

**Pages:** 9

---

## Analytics

**URL:** https://code.claude.com/docs/en/analytics

**Contents:**
- Analytics
- ​Access analytics
  - ​Required roles
- ​Available metrics
  - ​Lines of code accepted
  - ​Suggestion accept rate
  - ​Activity
  - ​Spend
  - ​Team insights
- ​Using analytics effectively

View detailed usage insights and productivity metrics for your organization’s Claude Code deployment.

Was this page helpful?

---

## Create and distribute a plugin marketplace

**URL:** https://code.claude.com/docs/en/plugin-marketplaces

**Contents:**
- Create and distribute a plugin marketplace
- ​Overview
- ​Walkthrough: create a local marketplace
- ​Create the marketplace file
- ​Marketplace schema
  - ​Required fields
  - ​Owner fields
  - ​Optional metadata
- ​Plugin entries
  - ​Required fields

Build and host plugin marketplaces to distribute Claude Code extensions across teams and communities.

Create the directory structure

Create the plugin command

Create the plugin manifest

Create the marketplace file

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
mkdir -p my-marketplace/.claude-plugin
mkdir -p my-marketplace/plugins/review-plugin/.claude-plugin
mkdir -p my-marketplace/plugins/review-plugin/commands
```

Example 2 (markdown):
```markdown
Review the code I've selected or the recent changes for:
- Potential bugs or edge cases
- Security concerns
- Performance issues
- Readability improvements

Be concise and actionable.
```

Example 3 (json):
```json
{
  "name": "review-plugin",
  "description": "Adds a /review command for quick code reviews",
  "version": "1.0.0"
}
```

Example 4 (json):
```json
{
  "name": "my-plugins",
  "owner": {
    "name": "Your Name"
  },
  "plugins": [
    {
      "name": "review-plugin",
      "source": "./plugins/review-plugin",
      "description": "Adds a /review command for quick code reviews"
    }
  ]
}
```

---

## Data usage

**URL:** https://code.claude.com/docs/en/data-usage

**Contents:**
- Data usage
- ​Data policies
  - ​Data training policy
  - ​Development Partner Program
  - ​Feedback using the /bug command
  - ​Session quality surveys
  - ​Data retention
- ​Data access
- ​Local Claude Code: Data flow and dependencies
  - ​Cloud execution: Data flow and dependencies

Learn about Anthropic’s data usage policies for Claude

Was this page helpful?

---

## Identity and Access Management

**URL:** https://code.claude.com/docs/en/iam

**Contents:**
- Identity and Access Management
- ​Authentication methods
  - ​Claude for Teams or Enterprise (recommended)
  - ​Claude Console authentication
  - ​Cloud provider authentication
- ​Access control and permissions
  - ​Permission system
  - ​Configuring permissions
    - ​Permission modes
    - ​Working directories

Learn how to configure user authentication, authorization, and access controls for Claude Code in your organization.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
{
  "permissions": {
    "deny": ["Task(Explore)"]
  }
}
```

---

## Manage costs effectively

**URL:** https://code.claude.com/docs/en/costs

**Contents:**
- Manage costs effectively
- ​Track your costs
  - ​Using the /cost command
  - ​Additional tracking options
- ​Managing costs for teams
  - ​Rate limit recommendations
- ​Reduce token usage
- ​Background token usage
- ​Tracking version changes and updates
  - ​Current version information

Learn how to track and optimize token usage and costs when using Claude Code.

Was this page helpful?

**Examples:**

Example 1 (swift):
```swift
Total cost:            $0.55
Total duration (API):  6m 19.7s
Total duration (wall): 6h 33m 10.2s
Total code changes:    0 lines added, 0 lines removed
```

Example 2 (julia):
```julia
# Summary instructions

When you are using compact, please focus on test output and code changes
```

Example 3 (unknown):
```unknown
claude doctor
```

---

## Monitoring

**URL:** https://code.claude.com/docs/en/monitoring-usage

**Contents:**
- Monitoring
- ​Quick start
- ​Administrator configuration
- ​Configuration details
  - ​Common configuration variables
  - ​Metrics cardinality control
  - ​Dynamic headers
    - ​Settings configuration
    - ​Script requirements
    - ​Refresh behavior

Learn how to enable and configure OpenTelemetry for Claude Code.

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# 1. Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# 2. Choose exporters (both are optional - configure only what you need)
export OTEL_METRICS_EXPORTER=otlp       # Options: otlp, prometheus, console
export OTEL_LOGS_EXPORTER=otlp          # Options: otlp, console

# 3. Configure OTLP endpoint (for OTLP exporter)
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# 4. Set authentication (if required)
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer your-token"

# 5. For debugging: reduce export intervals
export OTEL_METRIC_EXPORT_INTERVAL=10000  # 10 seconds (default: 60000ms)
export OTEL_LOGS_EXPORT_INTERVAL=5000     # 5 seconds (default: 5000ms)

# 6. Run Claude Code
claude
```

Example 2 (json):
```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector.company.com:4317",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer company-token"
  }
}
```

Example 3 (json):
```json
{
  "otelHeadersHelper": "/bin/generate_opentelemetry_headers.sh"
}
```

Example 4 (bash):
```bash
#!/bin/bash
# Example: Multiple headers
echo "{\"Authorization\": \"Bearer $(get-token.sh)\", \"X-API-Key\": \"$(get-api-key.sh)\"}"
```

---

## Optimize your terminal setup

**URL:** https://code.claude.com/docs/en/terminal-config

**Contents:**
- Optimize your terminal setup
  - ​Themes and appearance
  - ​Line breaks
  - ​Notification setup
    - ​iTerm 2 system notifications
    - ​Custom notification hooks
  - ​Handling large inputs
  - ​Vim Mode

Claude Code works best when your terminal is properly configured. Follow these guidelines to optimize your experience.

Was this page helpful?

---

## Security

**URL:** https://code.claude.com/docs/en/security

**Contents:**
- Security
- ​How we approach security
  - ​Security foundation
  - ​Permission-based architecture
  - ​Built-in protections
  - ​User responsibility
- ​Protect against prompt injection
  - ​Core protections
  - ​Privacy safeguards
  - ​Additional safeguards

Learn about Claude Code’s security safeguards and best practices for safe usage.

Was this page helpful?

---

## Set up Claude Code

**URL:** https://code.claude.com/docs/en/setup

**Contents:**
- Set up Claude Code
- ​System requirements
  - ​Additional dependencies
- ​Installation
  - ​Authentication
    - ​For individuals
    - ​For teams and organizations
  - ​Install a specific version
  - ​Binary integrity and code signing
- ​NPM installation (deprecated)

Install, authenticate, and start using Claude Code on your development machine.

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
