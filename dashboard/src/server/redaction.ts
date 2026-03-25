// 3-Layer Secret Protection (S4)
//
// Layer 1: Strip tool_result content entirely and summarize tool_use inputs.
//          This eliminates the entire class of credential leaks with zero false negatives.
//          Tool outputs are NEVER sent to the browser.
//
// Layer 2: Comprehensive regex redaction on remaining text fields.
//          30+ patterns covering cloud keys, payment APIs, DB URIs, JWTs, etc.
//          Applied by redactPayload() — a deep-walk over any object.
//
// Layer 3 (v0.2): Replace regex with secretlint for edge cases (base64, Unicode escapes).
//
// Usage:
//   import { redactPayload, stripSensitiveContent } from "./redaction.js";
//
//   // WebSocket / REST gate — apply both layers:
//   const safe = redactPayload(stripSensitiveContent(payload));

// === Layer 2: Regex patterns ===
// One pattern per secret family. Order is intentional: more specific before generic.

const REDACT_PATTERNS: RegExp[] = [
  // --- Cloud Provider Keys ---
  /\bsk-ant-api[^\s",'}\]]+/g,                           // Anthropic API key
  /\bsk-proj-[A-Za-z0-9_-]{48,}/g,                       // OpenAI project key (before generic sk-)
  /\bsk-[A-Za-z0-9]{20,}/g,                              // OpenAI legacy key
  /\b(?:AKIA|ASIA)[A-Z0-9]{16}/g,                        // AWS Access Key ID + STS session key
  /\baws_secret_access_key\s*[=:]\s*\S+/gi,              // AWS Secret Access Key (context-anchored)
  /\bAIza[A-Za-z0-9_-]{35}/g,                            // GCP API key

  // --- Payment / SaaS ---
  /\bsk_(?:live|test)_[A-Za-z0-9]{24,}/g,                // Stripe secret key
  /\brk_live_[A-Za-z0-9]{24,}/g,                         // Stripe restricted key
  /\bwhsec_[A-Za-z0-9+/=]{32,}/g,                        // Stripe webhook secret
  /\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}/g,        // SendGrid API key
  /\bSK[a-f0-9]{32}\b/g,                                 // Twilio API key (SID format)
  /\bkey-[a-f0-9]{32}\b/g,                               // Mailgun API key

  // --- Git Providers ---
  /\bgh[pousr]_[A-Za-z0-9]{36}/g,                        // GitHub tokens (ghp_, gho_, ghu_, ghs_, ghr_)
  /\bgithub_pat_[A-Za-z0-9_]{82}/g,                      // GitHub fine-grained PAT
  /\bglpat-[A-Za-z0-9_-]{20,}/g,                         // GitLab personal access token
  /\bgldt-[A-Za-z0-9_-]{20,}/g,                          // GitLab deploy token
  /\bATATT[A-Za-z0-9+/=]{30,}/g,                         // Atlassian PAT

  // --- Database Connection Strings (with inline credentials) ---
  /\bpostgres(?:ql)?:\/\/[^:\s]+:[^@\s]+@[^\s"']+/gi,
  /\bmysql:\/\/[^:\s]+:[^@\s]+@[^\s"']+/gi,
  /\bmongodb(?:\+srv)?:\/\/[^:\s]+:[^@\s]+@[^\s"']+/gi,
  /\bredis:\/\/(?:[^:\s]+:[^@\s]+@)?[^\s"']+/gi,
  /\bamqps?:\/\/[^:\s]+:[^@\s]+@[^\s"']+/gi,

  // --- Webhooks ---
  /https:\/\/hooks\.slack\.com\/services\/T[A-Z0-9]+\/B[A-Z0-9]+\/[A-Za-z0-9]+/g,
  /https:\/\/discord(?:app)?\.com\/api\/webhooks\/\d+\/[A-Za-z0-9_-]+/g,

  // --- Tokens & Auth ---
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g,  // JWT (3-segment base64url)
  /\bnpm_[A-Za-z0-9]{36}/g,                              // npm access token
  /\bpypi-[A-Za-z0-9_-]{20,}/g,                          // PyPI API token
  /\b\d{8,12}:AA[A-Za-z0-9_-]{33}/g,                     // Telegram bot token
  /\bhvs\.[A-Za-z0-9_-]{90,}/g,                          // HashiCorp Vault service token

  // --- PEM Private Keys (header line — body stripped by Layer 1) ---
  /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g,

  // --- Azure ---
  /\bDefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+/gi,

  // --- Generic key=value patterns (quoted and unquoted values) ---
  // Covers: password=, api_key=, token=, secret=, etc. with = or : separator
  /\b(?:password|passwd|api_key|apikey|secret|token|bearer|credentials|auth|private_key|signing_key|encryption_key|client_secret|app_secret|session_secret|db_pass|db_password|database_url|redis_url|sentry_dsn|access_key|secret_key)\s*[=:]\s*(?:"[^"]*"|'[^']*'|\S+)/gi,
];

const MAX_TEXT_LENGTH = 65_536; // 64KB — prevents regex DoS on pathological inputs

// Layer 2: Apply all regex patterns to a single string.
// Truncates before redaction to prevent catastrophic backtracking on huge blobs.
export function redact(text: string): string {
  if (!text || typeof text !== "string") return text;

  const safe =
    text.length > MAX_TEXT_LENGTH
      ? text.slice(0, MAX_TEXT_LENGTH) + "[truncated]"
      : text;

  return REDACT_PATTERNS.reduce((t, pattern) => {
    // Reset lastIndex since we're reusing compiled regexes with /g flag
    pattern.lastIndex = 0;
    return t.replace(pattern, "[REDACTED]");
  }, safe);
}

// Layer 1: Strip tool_result content and summarize tool_use inputs.
// Operates on Claude JSONL message entries.
// Returns a new object — does NOT mutate the original.
export function stripSensitiveContent(entry: unknown): unknown {
  if (entry === null || typeof entry !== "object") return entry;

  const e = entry as Record<string, unknown>;

  // Only process entries that have message.content arrays
  const message = e["message"];
  if (!message || typeof message !== "object") return entry;

  const msg = message as Record<string, unknown>;
  const content = msg["content"];
  if (!Array.isArray(content)) return entry;

  const strippedContent = content.map((block: unknown) => {
    if (block === null || typeof block !== "object") return block;

    const b = block as Record<string, unknown>;
    const blockType = b["type"];

    if (blockType === "tool_result") {
      // Strip content entirely — tool outputs can contain .env, API keys, PEM keys, etc.
      return {
        ...b,
        content: "[content stripped — use Claude Code directly to inspect]",
      };
    }

    if (blockType === "tool_use") {
      // Show tool name and structure, never values
      return {
        type: "tool_use",
        name: b["name"],
        id: b["id"],
        input: summarizeInput(b["input"]),
      };
    }

    if (blockType === "text") {
      // Apply Layer 2 redaction to text blocks
      const textVal = b["text"];
      return {
        ...b,
        text: typeof textVal === "string" ? redact(textVal) : textVal,
      };
    }

    return block;
  });

  return {
    ...e,
    message: {
      ...msg,
      content: strippedContent,
    },
  };
}

// Summarize tool input: show key names and short values, never large strings.
// Values > 100 chars are replaced with length indicator. Strings are redacted.
function summarizeInput(input: unknown): unknown {
  if (input === null || input === undefined) return input;

  if (typeof input === "string") {
    if (input.length > 200) return "[truncated]";
    return redact(input);
  }

  if (typeof input === "object" && !Array.isArray(input)) {
    const summary: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(input as Record<string, unknown>)) {
      if (typeof v === "string" && v.length > 100) {
        summary[k] = `[${v.length} chars]`;
      } else if (typeof v === "string") {
        summary[k] = redact(v);
      } else {
        summary[k] = v;
      }
    }
    return summary;
  }

  return input;
}

// Layer 2: Deep-walk any object and redact all string values.
// Numbers, booleans, null stay untouched. Arrays and objects are recursed.
export function redactPayload(obj: unknown): unknown {
  if (typeof obj === "string") return redact(obj);
  if (Array.isArray(obj)) return obj.map(redactPayload);
  if (obj !== null && typeof obj === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      result[k] = redactPayload(v);
    }
    return result;
  }
  return obj;
}

// Combined gate: apply Layer 1 (strip) then Layer 2 (regex redact).
// This is the single function that ALL data must pass through before
// reaching a WebSocket client or REST response body.
export function redactPayloadFull(obj: unknown): unknown {
  return redactPayload(stripSensitiveContent(obj));
}
