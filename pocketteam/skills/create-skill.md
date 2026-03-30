---
name: create-skill
description: "Create a new PocketTeam skill. Generates the skill markdown file and adds it to MANIFEST.json."
---

# /create-skill — Add a New Skill to PocketTeam

Create a new skill that agents can use. Skills are markdown files in `.claude/skills/pocketteam/`.

## Steps

1. **Choose a name** — lowercase, hyphenated (e.g. `deploy-preview`, `api-test`)
2. **Choose an owner agent** — which agent will use this skill? (engineer, qa, security, etc.)
3. **Write the skill file** at `pocketteam/skills/<name>.md`:

```markdown
---
name: <skill-name>
description: "<one-line description for skill discovery>"
---

# /<skill-name> — <Title>

<Instructions for the agent when this skill is invoked>
```

4. **Add to MANIFEST.json** — append the skill name to `package_skills` array in `pocketteam/skills/MANIFEST.json`
5. **Reference in agent prompt** — add the skill to the agent's `.claude/agents/pocketteam/<agent>.md` skills list
6. **Test** — run `pocketteam init` in a test directory to verify the skill gets installed

## Conventions

- Keep skills focused: one task per skill
- Skills are instructions, not code — they tell the agent HOW to do something
- Use checklists for multi-step procedures
- Reference existing patterns: read 2-3 similar skills before writing
- Skills live in `pocketteam/skills/` (source) and get copied to `.claude/skills/pocketteam/` during init
