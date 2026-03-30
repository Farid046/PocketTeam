---
name: dependency-scan
description: "Scan dependencies for known CVEs. Use before releases or security audits."
---

# /dependency-scan — Dependency Vulnerability Scan

Run all dependency scanners and triage findings by severity.

## npm (dashboard)

```bash
cd dashboard

# Vulnerability scan
npm audit --json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
vulns = d.get('vulnerabilities', {})
critical = [k for k,v in vulns.items() if v.get('severity') == 'critical']
high = [k for k,v in vulns.items() if v.get('severity') == 'high']
print(f'Critical: {len(critical)}: {critical}')
print(f'High: {len(high)}: {high}')
"

# License check (flag copyleft in commercial project)
npx license-checker --json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
flagged = {k: v['licenses'] for k,v in d.items() if any(l in str(v.get('licenses','')) for l in ['GPL','AGPL','LGPL'])}
print('Copyleft licenses found:' if flagged else 'No copyleft found')
for k,v in flagged.items(): print(f'  {k}: {v}')
"
```

## Python (pocketteam)

```bash
# pip-audit (install if missing: pip install pip-audit)
pip-audit --format=json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
vulns = d.get('dependencies', [])
for dep in vulns:
    for v in dep.get('vulns', []):
        print(f\"{dep['name']} {dep['version']}: {v['id']} ({v.get('fix_versions', ['no fix'])})\")
" || echo "pip-audit not installed — run: pip install pip-audit"
```

## Docker Images

```bash
# trivy (install if missing: brew install trivy)
trivy image pocketteam-dashboard:latest --severity HIGH,CRITICAL --quiet 2>/dev/null || \
  echo "trivy not installed — run: brew install trivy"
```

## Triage Rules

- **Critical** → BLOCKER: must fix or explicitly accept risk before deploy
- **High** → must have a fix plan (scheduled in next sprint)
- **Medium/Low** → document, monitor, not a blocker

## Output Format

```markdown
## Dependency Scan: [Date]

### npm
- Critical: N ([package names])
- High: N
- License issues: [list or none]

### Python
- Critical: N ([package names])
- High: N

### Docker
- Critical: N
- High: N

### Required Actions
1. [package]: upgrade to [version] — fixes [CVE]
```
