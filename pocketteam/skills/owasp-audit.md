---
name: owasp-audit
description: "Full OWASP Top 10 security audit. Use before production releases."
---

# /owasp-audit — OWASP Top 10 Audit

Systematic check against OWASP Top 10. Run each grep, read the matches, classify the risk.

## A01: Broken Access Control

```bash
grep -rn "req\.user\|is_admin\|role" dashboard/src/server/ pocketteam/
# Check: are role checks consistent? Is any endpoint missing auth?
grep -rn "@app\.route\|router\.\(get\|post\|put\|delete\)" dashboard/src/server/
# Verify: every route has auth middleware
```

## A02: Cryptographic Failures

```bash
grep -rn "MD5\|SHA1\|base64\|password\s*=" --include="*.py" --include="*.ts" .
# Check: no plaintext passwords, no weak hashes
grep -rn "http://" --include="*.py" --include="*.ts" . | grep -v "localhost\|127.0.0.1\|test"
# Check: no cleartext HTTP to external services
```

## A03: Injection

```bash
grep -rn "f\"\|\.format(\|%s" --include="*.py" . | grep -i "sql\|query\|exec"
# Check: no string-formatted SQL queries
grep -rn "eval\|exec\|subprocess\.call\|os\.system" --include="*.py" .
grep -rn "eval(\|innerHTML\|dangerouslySetInnerHTML" --include="*.ts" --include="*.tsx" .
# Check: eval only with --allow-eval flag (ptbrowse)
```

## A05: Security Misconfiguration

```bash
grep -rn "DEBUG\s*=\s*True\|debug=True" --include="*.py" .
grep -rn "CORS.*\*\|Access-Control-Allow-Origin.*\*" dashboard/src/server/
grep -rn "0\.0\.0\.0\|host.*0\.0\.0\.0" --include="*.py" --include="*.ts" .
```

## A07: Auth Failures

```bash
grep -rn "jwt\|token\|secret\|api.key" --include="*.py" --include="*.ts" . -i | grep -v test | grep -v "#"
# Check: no hardcoded secrets, tokens loaded from env only
```

## A09: Logging Failures

```bash
grep -rn "except:\|except Exception:" --include="*.py" . | grep -v "# ok"
# Check: no silent bare except swallowing errors
grep -rn "console\.log\|print(" --include="*.ts" . | grep -i "password\|secret\|token"
# Check: no secrets logged
```

## Output Format

```markdown
## OWASP Audit: [Date]

### Findings

| Category | Severity | File:Line | Issue | Status |
|----------|----------|-----------|-------|--------|
| A03 Injection | HIGH | guardian.py:42 | eval without flag | OPEN |

### Summary
- Critical: N
- High: N
- Passed clean: [categories]
```
