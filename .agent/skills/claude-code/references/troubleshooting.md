# Claude-Code - Troubleshooting

**Pages:** 1

---

## Troubleshooting

**URL:** https://code.claude.com/docs/en/troubleshooting

**Contents:**
- Troubleshooting
- ​Common installation issues
  - ​Windows installation issues: errors in WSL
  - ​Linux and Mac installation issues: permission or command not found errors
    - ​Recommended solution: Native Claude Code installation
  - ​Windows: “Claude Code on Windows requires git-bash”
  - ​Windows: “installMethod is native, but claude command not found”
- ​Permissions and authentication
  - ​Repeated permission prompts
  - ​Authentication issues

Discover solutions to common issues with Claude Code installation and usage.

Open Environment Variables

Restart your terminal

Was this page helpful?

**Examples:**

Example 1 (json):
```json
# Load nvm if it exists
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
```

Example 2 (unknown):
```unknown
source ~/.nvm/nvm.sh
```

Example 3 (bash):
```bash
export PATH="$HOME/.nvm/versions/node/$(node -v)/bin:$PATH"
```

Example 4 (markdown):
```markdown
# Install stable version (default)
curl -fsSL https://claude.ai/install.sh | bash

# Install latest version
curl -fsSL https://claude.ai/install.sh | bash -s latest

# Install specific version number
curl -fsSL https://claude.ai/install.sh | bash -s 1.0.58
```

---
