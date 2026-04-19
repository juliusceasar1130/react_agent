---
name: development-guide-synthesizer
description: Create reusable development guides, troubleshooting manuals, implementation handbooks, and delivery playbooks from coding work, debugging sessions, architecture discussions, and changelog-style context. This skill should be used when the user wants to distill development and discussion content into a structured guide with templates, examples, key points, pitfalls, and reuse checklists.
---

# Development Guide Synthesizer Skill

更新时间：2026-04-19 Asia/Shanghai
主要内容：新增面向“开发经验沉淀”的项目级 skill，帮助把开发过程、讨论结论、代码实现、踩坑记录和验证结果提炼为结构清晰、可复用的开发指南手册。
- 新增要求：当输出为中长篇开发指南时，默认在正文前增加可跳转目录（Table of Contents），提升长文档的可扫描性与导航效率。

## Purpose

Provide a repeatable workflow for turning scattered development context into a reusable handbook.

The goal is not only to summarize what changed, but to preserve:

- why the work was needed
- how the solution is structured
- what design decisions were made
- what pitfalls were discovered
- how the pattern can be reused next time

## When To Use

Use this skill when the user wants to produce a structured development guide or handbook from real work, for example:

- Summarizing one completed feature into a reusable development guide
- Turning a debugging or refactoring session into a troubleshooting handbook
- Distilling multi-turn discussions into a technical playbook
- Writing a “how we built this” implementation manual for teammates
- Extracting best practices, key decisions, and common mistakes from a project change
- Converting code changes, changelog notes, review comments, and design discussion into documentation

Typical trigger phrases include:

- “总结这次开发经验并形成手册”
- “沉淀为开发指南”
- “提炼成复用文档”
- “把这次实现整理成 playbook”
- “根据开发和讨论内容写一个指南”
- “整理为团队后续复用的手册”

## Inputs To Gather

Before writing, gather as much of the following as is relevant:

1. Source code changes
2. Related design or implementation discussions
3. Changelog or commit summary
4. Runtime behavior or call chain
5. Validation results
6. Risks, trade-offs, and unresolved questions

If some parts are missing:

- infer conservatively
- mark the uncertain parts clearly
- avoid inventing runtime behavior without evidence

## Workflow

1. Identify the document type.
   Common types:
   - development guide
   - troubleshooting guide
   - implementation handbook
   - migration guide
   - pattern playbook

2. Identify the audience.
   Common audiences:
   - current repo contributors
   - future maintainers
   - onboarding developers
   - adjacent teams reusing the pattern

3. Define the documentation scope.
   Decide whether the guide is about:
   - one feature
   - one bugfix theme
   - one architecture pattern
   - one end-to-end workflow

4. Reconstruct the actual development story.
   Extract and order:
   - background
   - problem
   - goals
   - solution structure
   - important files
   - call chain
   - validation
   - lessons learned

5. Separate fact from conclusion.
   Distinguish clearly between:
   - confirmed code behavior
   - inferred design intent
   - recommended reuse guidance

6. Capture reusable knowledge, not just history.
   Always include:
   - key decisions
   - why this approach was chosen
   - what to watch out for next time
   - what can be copied directly
   - what still needs adaptation

7. Add operational value.
   Prefer adding:
   - template structure
   - checklists
   - examples
   - anti-patterns
   - extension ideas

8. End with a compact summary sentence.
   The closing should make the core reuse principle easy to remember.

## Output Shape

Prefer this structure unless the user requests another format:

1. Title
2. Metadata
   - modification time
   - main updates
3. Table of contents
   - include for medium/long guides by default
4. Background
5. What problem this solves
6. Overall design
7. Call chain or execution flow
8. Layered responsibilities
9. Key design decisions
10. Pitfalls and lessons learned
11. Reuse checklist
12. Optional future improvements
13. One-sentence takeaway

## Template

Use the main template in:

- `references/guide-template.md`

When the user explicitly wants a prompt-like reusable skeleton, use:

- `references/examples.md`

## Quality Bar

A good development guide should be:

- grounded in actual implementation
- reusable beyond the single incident
- explicit about trade-offs
- clear about what is fixed versus what is still contextual
- easy to skim
- easy to extend later
- easy to navigate in long-form documentation

## Key Points To Preserve

Always try to preserve these dimensions:

- business or technical background
- design intent
- implementation layering
- file/module responsibilities
- important data or control flow
- validation evidence
- pitfalls
- operational checklist
- future reuse strategy

## Common Mistakes

Avoid these mistakes:

- Writing only a timeline of what changed, without reusable conclusions
- Writing only abstract principles, without file-level or flow-level grounding
- Mixing verified facts and guesses without labeling uncertainty
- Explaining the final result but omitting the failed attempts and pitfalls
- Producing a changelog instead of a handbook
- Listing files mechanically instead of explaining their role in the workflow
- Forgetting to include examples, templates, or checklists when the guide is meant to be reused

## Recommended Style

- Default to Chinese when the surrounding project context prefers Chinese
- Use short section titles
- Prefer ordered steps for workflows and call chains
- Prefer compact bullet lists for checklists and pitfalls
- Keep examples concrete and close to the actual code or discussion
- For medium/long guides, add a table of contents near the top unless the user explicitly asks not to

## Guardrails

- Do not claim a call chain without code or discussion evidence
- Do not over-generalize one incident into a universal rule without qualification
- Do not drop the “why” behind a design decision
- Do not omit validation status; say what was and was not verified
- Do not write a handoff document that only the original author can understand
