---
name: sibyl
description:
  Graph-RAG knowledge system with CLI interface. Use when you need persistent memory, semantic
  search, task coordination, or project context across coding sessions.
allowed-tools: Bash(sibyl:*)
---

# Sibyl

This installed skill is a discovery stub. The full workflow guidance is shipped by the installed
`sibyl` CLI so it always matches the version on this machine.

Before using Sibyl in a session, load the current core skill content:

```bash
sibyl skill get core
```

Useful follow-ups:

```bash
sibyl skill list
sibyl skill get workflows
sibyl skill get examples
```

Hooks are separate from skills. Install or update hooks only when the user explicitly wants
automatic prompt/session integration.
