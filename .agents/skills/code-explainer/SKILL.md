---
name: code-explainer
description: Explain a codebase's architecture, tech stack, execution flow, module responsibilities, and call chains. This skill should be used when the user wants to understand how code works rather than immediately modify it.
---

# Code Explainer Skill

更新时间：2026-03-27 Asia/Shanghai
主要内容：新增面向代码阅读与讲解的项目级 skill，帮助快速解释框架、技术栈、流程和调用机制。

## Purpose

Provide a stable workflow for reading unfamiliar code and explaining it in a way that is fast to absorb.

## When To Use

Use this skill when the request is primarily about understanding code, for example:

- Explaining project architecture
- Summarizing the tech stack and why each part exists
- Tracing request flow, data flow, or execution flow
- Mapping module responsibilities
- Following a function or service call chain
- Onboarding someone to a new repository

## Workflow

1. Inspect top-level directories and identify the likely entrypoints first.
2. Find the module or files that own orchestration before diving into helpers.
3. Explain from outside in:
   - overall purpose
   - module boundaries
   - runtime flow
   - important implementation details
4. Distinguish clearly between:
   - entrypoint
   - orchestrator
   - domain/service logic
   - utility layer
   - persistence or external integrations
5. When describing a flow, prefer ordered steps over scattered observations.
6. When useful, include a compact ASCII diagram.
7. Call out uncertainty explicitly when a relationship is inferred rather than directly confirmed in code.

## Response Shape

Prefer this answer structure when it fits:

1. One-sentence summary
2. Tech stack or module positioning
3. Step-by-step flow
4. Call chain or dependency chain
5. Key design choices or confusing parts
6. Suggested next files to read

## Guardrails

- Do not rush into code changes when the task is explanatory
- Do not claim a runtime path without code evidence
- Keep explanations concrete and file-anchored when possible
- Default to Chinese if the surrounding project context prefers Chinese
