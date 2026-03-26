export interface AgentRole {
  role: string;
  displayName: string;
  color: string; // CSS hex
}

const ROLE_MAP: Record<string, AgentRole> = {
  planner:       { role: "planner",       displayName: "Planner",      color: "#5B9BD5" },
  engineer:      { role: "engineer",      displayName: "Engineer",     color: "#2F5496" },
  qa:            { role: "qa",            displayName: "QA",           color: "#70AD47" },
  security:      { role: "security",      displayName: "Security",     color: "#FF0000" },
  reviewer:      { role: "reviewer",      displayName: "Reviewer",     color: "#00B0F0" },
  devops:        { role: "devops",        displayName: "DevOps",       color: "#FF00FF" },
  investigator:  { role: "investigator",  displayName: "Investigator", color: "#FFC000" },
  documentation: { role: "documentation", displayName: "Docs",         color: "#A5A5A5" },
  monitor:       { role: "monitor",       displayName: "Monitor",      color: "#92D050" },
  observer:      { role: "observer",      displayName: "Observer",     color: "#BF8F00" },
  product:       { role: "product",       displayName: "Product",      color: "#7030A0" },
  coo:           { role: "coo",           displayName: "COO",          color: "#FFD700" },
  researcher:    { role: "researcher",    displayName: "Researcher",   color: "#00BCD4" },
};

// Map Claude Code built-in agent types to PocketTeam roles
const AGENT_TYPE_MAP: Record<string, string> = {
  "explore":         "researcher",
  "plan":            "planner",
  "planner":         "planner",
  "engineer":        "engineer",
  "reviewer":        "reviewer",
  "qa":              "qa",
  "security":        "security",
  "devops":          "devops",
  "investigator":    "investigator",
  "documentation":   "documentation",
  "monitor":         "monitor",
  "observer":        "observer",
  "product":         "product",
  "coo":             "coo",
};

// Order matters — longer / more specific keywords should come first
// so "critical review" wins over "review" alone.
const KEYWORD_MAP: Array<[string, string]> = [
  ["critical review",  "reviewer"],
  ["root cause",       "investigator"],
  ["planner",          "planner"],
  ["plan",             "planner"],
  ["scaffold",         "engineer"],
  ["implement",        "engineer"],
  ["engineer",         "engineer"],
  ["build",            "engineer"],
  ["code",             "engineer"],
  ["quality",          "qa"],
  ["test",             "qa"],
  ["qa",               "qa"],
  ["owasp",            "security"],
  ["security",         "security"],
  ["audit",            "security"],
  ["reviewer",         "reviewer"],
  ["review",           "reviewer"],
  ["staging",          "devops"],
  ["devops",           "devops"],
  ["deploy",           "devops"],
  ["debug",            "investigator"],
  ["investigate",      "investigator"],
  ["readme",           "documentation"],
  ["document",         "documentation"],
  ["docs",             "documentation"],
  ["monitor",          "monitor"],
  ["health",           "monitor"],
  ["retro",            "observer"],
  ["observe",          "observer"],
  ["learn",            "observer"],
  ["demand",           "product"],
  ["validate",         "product"],
  ["product",          "product"],
  ["coo",              "coo"],
];

export function inferRole(description: string, agentType?: string): AgentRole {
  // 1. agentType is the most reliable source (from .meta.json)
  if (agentType) {
    const mapped = AGENT_TYPE_MAP[agentType.toLowerCase()];
    if (mapped && ROLE_MAP[mapped]) {
      return ROLE_MAP[mapped];
    }
  }

  // 2. Fall back to description keyword matching
  const lower = description.toLowerCase();
  for (const [keyword, role] of KEYWORD_MAP) {
    if (lower.includes(keyword)) {
      return ROLE_MAP[role];
    }
  }

  // 3. Default to generic "agent" instead of "unknown"
  return { role: "agent", displayName: "Agent", color: "#808080" };
}

export function getRoleInfo(role: string): AgentRole {
  return ROLE_MAP[role] ?? { role, displayName: role, color: "#808080" };
}
