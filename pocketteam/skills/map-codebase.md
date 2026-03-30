---
name: map-codebase
description: "Analyze existing codebase with parallel agents. Use for brownfield project onboarding."
---

# Codebase Mapping

Use before planning on brownfield projects or any codebase you haven't worked with before.
Three parallel Explore agents analyze the project from different angles and their findings
are merged into `.pocketteam/CODEBASE.md` — a persistent reference that all agents can read.

## When to Use

- First task on an existing project (not greenfield)
- Handed a repository without documentation
- After a long break — validate that your mental model is still accurate
- Before writing a plan that touches core architecture

## Execution: 3 Parallel Explore Agents

Spawn all three agents simultaneously. Each has a focused mandate:

---

### Agent 1 — Stack Analyzer

**Mandate:** Identify every technology in use.

```
Read: package.json / requirements.txt / Gemfile / go.mod / Cargo.toml / pom.xml
      Dockerfile, docker-compose.yml, .env.example
      Any config files (webpack, vite, tsconfig, jest.config, etc.)

Report:
- Language(s) and runtime versions
- Framework(s) (web, ORM, test runner, etc.)
- Key dependencies (list top 10 by importance, not size)
- Build tooling
- Infrastructure / cloud provider (from Dockerfile, CI config, IaC)
- Any surprising or unusual dependencies
```

---

### Agent 2 — Architecture Mapper

**Mandate:** Understand how the system is structured and how data flows.

```
Read: Top-level directory structure
      Main entry points (main.py, index.ts, app.rb, etc.)
      Router/controller definitions
      Database models or schema files
      API contracts (OpenAPI, GraphQL schema, proto files if present)

Report:
- Architectural pattern (MVC, hexagonal, microservices, monorepo, etc.)
- Module/service boundaries
- Data flow: request → handler → service → DB → response
- External integrations (third-party APIs, queues, caches)
- File structure diagram (2 levels deep)
```

---

### Agent 3 — Conventions Detector

**Mandate:** Learn the project's coding and operational conventions.

```
Read: .editorconfig, .eslintrc, .prettierrc, pyproject.toml, .rubocop.yml
      A sample of 3–5 source files across different modules
      Existing tests (look at naming, structure, assertion style)
      Git log (last 20 commits) — note commit message style
      Any CONTRIBUTING.md or DEVELOPMENT.md

Report:
- Naming conventions (files, functions, classes, variables)
- Test structure and assertion style
- Commit message format
- Linting/formatting rules in force
- Any team-specific patterns or anti-patterns observed
```

---

## Merge Results into CODEBASE.md

After all three agents complete, write `.pocketteam/CODEBASE.md`:

```markdown
# Codebase Map
_Generated: [YYYY-MM-DD] — [project name]_

## Stack
- Language: [...]
- Framework: [...]
- Database: [...]
- Key dependencies: [...]
- Build: [...]
- Infrastructure: [...]

## Architecture
- Pattern: [...]
- Entry points: [...]
- Module structure: [...]
- Data flow: [...]
- External integrations: [...]

### File Structure (2 levels)
[tree output]

## Conventions
- File naming: [...]
- Function/class naming: [...]
- Test style: [...]
- Commit format: [...]
- Linting: [...]

## Concerns
_Observations that may affect planning:_
- [Any tech debt, unusual patterns, missing tests, deprecated dependencies, etc.]

## Context Pointers
- Decisions: `.pocketteam/CONTEXT.md`
- State: `.pocketteam/STATE.md`
```

## After Mapping

1. Present a one-paragraph summary to the CEO.
2. Highlight any **Concerns** that need a decision before planning.
3. Reference CODEBASE.md in all subsequent plans so agents don't re-analyze.

## Stale CODEBASE.md

If CODEBASE.md is older than 30 days or the CEO says major changes happened,
re-run the mapping. Otherwise agents should trust the existing file.
