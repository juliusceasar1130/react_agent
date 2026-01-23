# Claude-Code - Deployment

**Pages:** 7

---

## Claude Code on Amazon Bedrock

**URL:** https://code.claude.com/docs/en/amazon-bedrock

**Contents:**
- Claude Code on Amazon Bedrock
- ​Prerequisites
- ​Setup
  - ​1. Submit use case details
  - ​2. Configure AWS credentials
    - ​Advanced credential configuration
      - Example configuration
      - Configuration settings explained
  - ​3. Configure Claude Code
  - ​4. Model configuration

Learn about configuring Claude Code through Amazon Bedrock, including setup, IAM configuration, and troubleshooting.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
aws configure
```

Example 2 (unknown):
```unknown
export AWS_ACCESS_KEY_ID=your-access-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-access-key
export AWS_SESSION_TOKEN=your-session-token
```

Example 3 (unknown):
```unknown
aws sso login --profile=<your-profile-name>

export AWS_PROFILE=your-profile-name
```

Example 4 (unknown):
```unknown
export AWS_BEARER_TOKEN_BEDROCK=your-bedrock-api-key
```

---

## Claude Code on Google Vertex AI

**URL:** https://code.claude.com/docs/en/google-vertex-ai

**Contents:**
- Claude Code on Google Vertex AI
- ​Prerequisites
- ​Region Configuration
- ​Setup
  - ​1. Enable Vertex AI API
  - ​2. Request model access
  - ​3. Configure GCP credentials
  - ​4. Configure Claude Code
  - ​5. Model configuration
- ​IAM configuration

Learn about configuring Claude Code through Google Vertex AI, including setup, IAM configuration, and troubleshooting.

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# Set your project ID
gcloud config set project YOUR-PROJECT-ID

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

Example 2 (markdown):
```markdown
# Enable Vertex AI integration
export CLAUDE_CODE_USE_VERTEX=1
export CLOUD_ML_REGION=global
export ANTHROPIC_VERTEX_PROJECT_ID=YOUR-PROJECT-ID

# Optional: Disable prompt caching if needed
export DISABLE_PROMPT_CACHING=1

# When CLOUD_ML_REGION=global, override region for unsupported models
export VERTEX_REGION_CLAUDE_3_5_HAIKU=us-east5

# Optional: Override regions for other specific models
export VERTEX_REGION_CLAUDE_3_5_SONNET=us-east5
export VERTEX_REGION_CLAUDE_3_7_SONNET=us-east5
export VERTEX_REGION_CLAUDE_4_0_OPUS=europe-west1
export VERTEX_REGION_CLAUDE_4_0_SONNET=us-east5
export VERTEX_REGION_CLAUDE_4_1_OPUS=europe-west1
```

Example 3 (python):
```python
export ANTHROPIC_MODEL='claude-opus-4-1@20250805'
export ANTHROPIC_SMALL_FAST_MODEL='claude-haiku-4-5@20251001'
```

---

## Claude Code on Microsoft Foundry

**URL:** https://code.claude.com/docs/en/microsoft-foundry

**Contents:**
- Claude Code on Microsoft Foundry
- ​Prerequisites
- ​Setup
  - ​1. Provision Microsoft Foundry resource
  - ​2. Configure Azure credentials
  - ​3. Configure Claude Code
- ​Azure RBAC configuration
- ​Troubleshooting
- ​Additional resources

Learn about configuring Claude Code through Microsoft Foundry, including setup, configuration, and troubleshooting.

Was this page helpful?

**Examples:**

Example 1 (unknown):
```unknown
export ANTHROPIC_FOUNDRY_API_KEY=your-azure-api-key
```

Example 2 (markdown):
```markdown
# Enable Microsoft Foundry integration
export CLAUDE_CODE_USE_FOUNDRY=1

# Azure resource name (replace {resource} with your resource name)
export ANTHROPIC_FOUNDRY_RESOURCE={resource}
# Or provide the full base URL:
# export ANTHROPIC_FOUNDRY_BASE_URL=https://{resource}.services.ai.azure.com

# Set models to your resource's deployment names
export ANTHROPIC_DEFAULT_SONNET_MODEL='claude-sonnet-4-5'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='claude-haiku-4-5'
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-1'
```

Example 3 (json):
```json
{
  "permissions": [
    {
      "dataActions": [
        "Microsoft.CognitiveServices/accounts/providers/*"
      ]
    }
  ]
}
```

---

## Development containers

**URL:** https://code.claude.com/docs/en/devcontainer

**Contents:**
- Development containers
- ​Key features
- ​Getting started in 4 steps
- ​Configuration breakdown
- ​Security features
- ​Customization options
- ​Example use cases
  - ​Secure client work
  - ​Team onboarding
  - ​Consistent CI/CD environments

Learn about the Claude Code development container for teams that need consistent, secure environments.

Was this page helpful?

---

## Enterprise network configuration

**URL:** https://code.claude.com/docs/en/network-config

**Contents:**
- Enterprise network configuration
- ​Proxy configuration
  - ​Environment variables
  - ​Basic authentication
- ​Custom CA certificates
- ​mTLS authentication
- ​Network access requirements
- ​Additional resources

Configure Claude Code for enterprise environments with proxy servers, custom Certificate Authorities (CA), and mutual Transport Layer Security (mTLS) authentication.

Was this page helpful?

**Examples:**

Example 1 (markdown):
```markdown
# HTTPS proxy (recommended)
export HTTPS_PROXY=https://proxy.example.com:8080

# HTTP proxy (if HTTPS not available)
export HTTP_PROXY=http://proxy.example.com:8080

# Bypass proxy for specific requests - space-separated format
export NO_PROXY="localhost 192.168.1.1 example.com .example.com"
# Bypass proxy for specific requests - comma-separated format
export NO_PROXY="localhost,192.168.1.1,example.com,.example.com"
# Bypass proxy for all requests
export NO_PROXY="*"
```

Example 2 (python):
```python
export HTTPS_PROXY=http://username:password@proxy.example.com:8080
```

Example 3 (unknown):
```unknown
export NODE_EXTRA_CA_CERTS=/path/to/ca-cert.pem
```

Example 4 (markdown):
```markdown
# Client certificate for authentication
export CLAUDE_CODE_CLIENT_CERT=/path/to/client-cert.pem

# Client private key
export CLAUDE_CODE_CLIENT_KEY=/path/to/client-key.pem

# Optional: Passphrase for encrypted private key
export CLAUDE_CODE_CLIENT_KEY_PASSPHRASE="your-passphrase"
```

---

## LLM gateway configuration

**URL:** https://code.claude.com/docs/en/llm-gateway

**Contents:**
- LLM gateway configuration
- ​Gateway requirements
- ​Configuration
  - ​Model selection
- ​LiteLLM configuration
  - ​Prerequisites
  - ​Basic LiteLLM setup
    - ​Authentication methods
      - Static API key
      - Dynamic API key with helper

Learn how to configure Claude Code to work with LLM gateway solutions. Covers gateway requirements, authentication configuration, model selection, and provider-specific endpoint setup.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
# Set in environment
export ANTHROPIC_AUTH_TOKEN=sk-litellm-static-key

# Or in Claude Code settings
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-litellm-static-key"
  }
}
```

Example 2 (bash):
```bash
#!/bin/bash
# ~/bin/get-litellm-key.sh

# Example: Fetch key from vault
vault kv get -field=api_key secret/litellm/claude-code

# Example: Generate JWT token
jwt encode \
  --secret="${JWT_SECRET}" \
  --exp="+1h" \
  '{"user":"'${USER}'","team":"engineering"}'
```

Example 3 (json):
```json
{
  "apiKeyHelper": "~/bin/get-litellm-key.sh"
}
```

Example 4 (markdown):
```markdown
# Refresh every hour (3600000 ms)
export CLAUDE_CODE_API_KEY_HELPER_TTL_MS=3600000
```

---

## Sandboxing

**URL:** https://code.claude.com/docs/en/sandboxing

**Contents:**
- Sandboxing
- ​Overview
- ​Why sandboxing matters
- ​How it works
  - ​Filesystem isolation
  - ​Network isolation
  - ​OS-level enforcement
- ​Getting started
  - ​Enable sandboxing
  - ​Sandbox modes

Learn how Claude Code’s sandboxed bash tool provides filesystem and network isolation for safer, more autonomous agent execution.

Was this page helpful?

**Examples:**

Example 1 (json):
```json
{
  "sandbox": {
    "network": {
      "httpProxyPort": 8080,
      "socksProxyPort": 8081
    }
  }
}
```

Example 2 (python):
```python
npx @anthropic-ai/sandbox-runtime <command-to-sandbox>
```

---
