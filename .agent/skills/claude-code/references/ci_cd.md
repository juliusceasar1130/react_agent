# Claude-Code - Ci Cd

**Pages:** 2

---

## Claude Code GitHub Actions

**URL:** https://code.claude.com/docs/en/github-actions

**Contents:**
- Claude Code GitHub Actions
- ​Why use Claude Code GitHub Actions?
- ​What can Claude do?
  - ​Claude Code Action
- ​Setup
- ​Quick setup
- ​Manual setup
- ​Upgrading from Beta
  - ​Essential changes
  - ​Breaking Changes Reference

Learn about integrating Claude Code into your development workflow with Claude Code GitHub Actions

Create a custom GitHub App (Recommended for 3P Providers)

Configure cloud provider authentication

Create workflow files

Google Vertex AI workflow

Was this page helpful?

**Examples:**

Example 1 (python):
```python
- uses: anthropics/claude-code-action@beta
  with:
    mode: "tag"
    direct_prompt: "Review this PR for security issues"
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    custom_instructions: "Follow our coding standards"
    max_turns: "10"
    model: "claude-sonnet-4-5-20250929"
```

Example 2 (python):
```python
- uses: anthropics/claude-code-action@v1
  with:
    prompt: "Review this PR for security issues"
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    claude_args: |
      --system-prompt "Follow our coding standards"
      --max-turns 10
      --model claude-sonnet-4-5-20250929
```

Example 3 (yaml):
```yaml
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
jobs:
  claude:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          # Responds to @claude mentions in comments
```

Example 4 (yaml):
```yaml
name: Code Review
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

---

## Claude Code GitLab CI/CD

**URL:** https://code.claude.com/docs/en/gitlab-ci-cd

**Contents:**
- Claude Code GitLab CI/CD
- ​Why use Claude Code with GitLab?
- ​How it works
- ​What can Claude do?
- ​Setup
  - ​Quick setup
  - ​Manual setup (recommended for production)
- ​Example use cases
  - ​Turn issues into MRs
  - ​Get implementation help

Learn about integrating Claude Code into your development workflow with GitLab CI/CD

Was this page helpful?

**Examples:**

Example 1 (yaml):
```yaml
stages:
  - ai

claude:
  stage: ai
  image: node:24-alpine3.21
  # Adjust rules to fit how you want to trigger the job:
  # - manual runs
  # - merge request events
  # - web/API triggers when a comment contains '@claude'
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
    # Optional: start a GitLab MCP server if your setup provides one
    - /bin/gitlab-mcp-server || true
    # Use AI_FLOW_* variables when invoking via web/API triggers with context payloads
    - echo "$AI_FLOW_INPUT for $AI_FLOW_CONTEXT on $AI_FLOW_EVENT"
    - >
      claude
      -p "${AI_FLOW_INPUT:-'Review this MR and implement the requested changes'}"
      --permission-mode acceptEdits
      --allowedTools "Bash(*) Read(*) Edit(*) Write(*) mcp__gitlab"
      --debug
```

Example 2 (python):
```python
@claude implement this feature based on the issue description
```

Example 3 (python):
```python
@claude suggest a concrete approach to cache the results of this API call
```

Example 4 (python):
```python
@claude fix the TypeError in the user dashboard component
```

---
