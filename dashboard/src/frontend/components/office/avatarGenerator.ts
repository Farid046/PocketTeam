import { ROLE_COLORS } from "../../constants";

export type HairStyle = "short" | "spiky" | "side" | "curly" | "buzz";

export interface AvatarData {
  faceColor: string;
  hairColor: string;
  shirtColor: string;
  hairStyle: HairStyle;
}

// Fixed avatar configs per PocketTeam role — deterministic, not random
const ROLE_AVATAR_CONFIG: Record<string, { hairColor: string; hairStyle: HairStyle }> = {
  coo:           { hairColor: "#1a0a00", hairStyle: "side" },
  planner:       { hairColor: "#5a3214", hairStyle: "short" },
  engineer:      { hairColor: "#2c1b0e", hairStyle: "buzz" },
  qa:            { hairColor: "#c2884a", hairStyle: "spiky" },
  security:      { hairColor: "#1a0a00", hairStyle: "short" },
  reviewer:      { hairColor: "#2c1b0e", hairStyle: "side" },
  devops:        { hairColor: "#5a3214", hairStyle: "buzz" },
  investigator:  { hairColor: "#c2884a", hairStyle: "short" },
  documentation: { hairColor: "#1a0a00", hairStyle: "curly" },
  monitor:       { hairColor: "#5a3214", hairStyle: "spiky" },
  observer:      { hairColor: "#2c1b0e", hairStyle: "curly" },
  product:       { hairColor: "#c2884a", hairStyle: "side" },
};

// Skin tones cycle through a fixed palette, keyed by role order
const SKIN_COLORS = [
  "#fde2c8", "#f5c5a0", "#d4956b", "#a0714f", "#ffe0bd", "#f5c5a0",
  "#fde2c8", "#d4956b", "#ffe0bd", "#f5c5a0", "#a0714f", "#fde2c8",
];

const ROLE_ORDER = [
  "coo", "planner", "engineer", "qa", "security", "reviewer",
  "devops", "investigator", "documentation", "monitor", "observer", "product",
];

export function generateAvatar(role: string): AvatarData {
  const key = role.toLowerCase();
  const idx = ROLE_ORDER.indexOf(key);
  const config = ROLE_AVATAR_CONFIG[key] ?? { hairColor: "#2c1b0e", hairStyle: "short" as HairStyle };

  return {
    faceColor: SKIN_COLORS[idx >= 0 ? idx : 0],
    hairColor: config.hairColor,
    shirtColor: ROLE_COLORS[key] ?? "#6B7280",
    hairStyle: config.hairStyle,
  };
}
