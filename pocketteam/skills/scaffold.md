---
name: scaffold
description: "Generate project structure and boilerplate. Use when starting a new module or service."
---

# /scaffold — New Component or Service

When creating a new agent, service, reader, hook, or UI component from scratch, follow this checklist to avoid missing pieces.

## Before Writing Anything

1. Read 2-3 existing files of the same type to match patterns exactly
2. Check what imports/utilities already exist (don't reinvent)
3. Confirm the naming convention (snake_case, camelCase, PascalCase per layer)

## Scaffold Checklist

### For a new Python module/service
- [ ] `__init__.py` updated if needed
- [ ] Type annotations on all functions
- [ ] Docstring on the class/module (one line, what it does)
- [ ] Error handling with specific exceptions (not bare `except`)
- [ ] Logging with `logger = logging.getLogger(__name__)`
- [ ] Test file: `tests/test_[name].py` with at least happy path + one error case

### For a new TypeScript module/component
- [ ] Types defined (no implicit `any`)
- [ ] Props interface for React components
- [ ] Error boundary or try/catch for async
- [ ] Test file: `[name].test.ts` with at least 2 cases
- [ ] Export added to barrel `index.ts` if one exists

### For a new agent (`.claude/agents/pocketteam/`)
- [ ] Frontmatter: name, description, model, tools
- [ ] Role description (one paragraph)
- [ ] Clear output format defined
- [ ] Added to COO's routing table in `CLAUDE.md` if new

## Commit Order

1. Core implementation file
2. Test file
3. Config/index updates
4. Document the addition in one sentence in commit message
