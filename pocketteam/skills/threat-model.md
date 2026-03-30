---
name: threat-model
description: "STRIDE threat modeling for system components. Use during security planning."
---

# /threat-model — STRIDE Threat Model

Apply STRIDE to PocketTeam's key assets. Document threats, current mitigations, and gaps.

## Assets in Scope

| Asset | Description |
|-------|-------------|
| Guardian | Safety hook — decides what agents can do |
| Allowlist | Per-agent tool permissions |
| ptbrowse | Headless browser — runs in agent context |
| Telegram bot | CEO communication channel |
| Event stream | `.pocketteam/events/stream.jsonl` — audit log |
| `.pocketteam/` | State directory — rate limits, KILL switch, artifacts |

## STRIDE Template

For each asset, check all 6 threat categories:

| # | Threat Type | Question |
|---|-------------|----------|
| S | Spoofing | Can an attacker pretend to be a legitimate agent? |
| T | Tampering | Can inputs/outputs be modified in transit or at rest? |
| R | Repudiation | Can actions be denied? Is the audit trail complete? |
| I | Info Disclosure | Can secrets leak (logs, error messages, snapshots)? |
| D | Denial of Service | Can an agent flood resources or block the system? |
| E | Elevation of Privilege | Can an agent exceed its allowed permissions? |

## PocketTeam Specific Threats

```markdown
### Guardian
- E: Agent modifies guardian.py to bypass checks → mitigated by allowlist (agents can't write safety/)
- D: Agent spawns infinite subagents → mitigated by RateLimiter (max spawns/hour)
- T: JSONL input crafted to confuse parser → guardian must fail-closed on malformed input

### ptbrowse
- E: eval command runs arbitrary JS → mitigated by --allow-eval flag requirement
- I: Screenshot captures sensitive data → screenshots go to .pocketteam/screenshots/ (local only)
- T: eval injection via page content → page content must not be passed directly to eval

### Telegram Bot
- S: Attacker sends messages from unauthorized user → allowlist in access.json
- I: Agent leaks internal state via Telegram reply → agents should not send unsolicited messages

### Event Stream
- T: Agent writes false events to cover its tracks → stream is append-only (no delete allowed)
- I: Stream contains secrets in tool args → guardian must redact sensitive fields before logging
```

## Output Format

```markdown
## Threat Model: [Date / Feature]

### New Threats Identified
| Asset | STRIDE | Threat | Severity | Mitigation | Status |
|-------|--------|--------|----------|------------|--------|

### Existing Mitigations: Still Effective? [yes/no + rationale]

### Residual Risk Accepted
- [threat]: accepted because [reason]
```
