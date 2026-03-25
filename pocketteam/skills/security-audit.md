---
name: security-audit
description: |
  Trigger when user asks for security review, vulnerability scan, or OWASP audit.
  Checks OWASP Top 10, scans dependencies for CVEs, reviews code for security issues.

  <example>
  user: "/security-audit"
  assistant: Uses the security-audit skill to perform a comprehensive security review
  </example>

  <example>
  user: "Check this code for security vulnerabilities"
  assistant: Uses the security-audit skill to audit the code
  </example>
---

# Security Audit

You are performing a comprehensive security audit. Be thorough but avoid false positives.

## Step 1: Dependency Scan

```bash
# Python
pip-audit 2>/dev/null || echo "pip-audit not installed"
# Check requirements for known bad versions
cat requirements.txt 2>/dev/null

# Node
npm audit 2>/dev/null || echo "npm not available"
```

## Step 2: OWASP Top 10 Checklist

Check the codebase for:

1. **Injection**: SQL parameterized? No eval() with user input? Shell commands sanitized?
2. **Broken Auth**: Passwords hashed (bcrypt/argon2)? Rate limiting? Token expiry?
3. **Data Exposure**: Secrets in env vars? PII encrypted? HTTPS enforced?
4. **Broken Access Control**: Auth checks on every endpoint? No IDOR?
5. **Misconfiguration**: Debug off in prod? CORS not `*`? Security headers?
6. **XSS**: Input escaped? CSP header? No innerHTML with user data?
7. **Insecure Deserialization**: No pickle.loads() with user data?
8. **Vulnerable Dependencies**: npm audit / pip-audit clean?
9. **Insufficient Logging**: Auth events logged? No sensitive data in logs?

## Step 3: STRIDE Threat Model (for new features)

For each new surface area:
- **S**poofing: Can identity be forged?
- **T**ampering: Can data be modified?
- **R**epudiation: Can actions be denied?
- **I**nformation Disclosure: What's exposed?
- **D**enial of Service: Abuse potential?
- **E**levation of Privilege: Can lower gain higher?

## Step 4: Report

```markdown
## Security Audit

### Critical (block deploy)
- **[File:Line]**: [Vulnerability] — CVSS: [score] — Fix: [how]

### High (fix before next release)
- **[File:Line]**: [Issue]

### Dependencies
- [Package@version]: [CVE / clean]

### Verdict
- CLEAN — proceed
- ISSUES FOUND — fix critical items first
```
