import { ROLE_COLORS } from "../../constants";

export type HairStyle = "flat" | "spiky" | "round" | "long" | "buzz";

export interface AvatarStyle {
  shirtColor: string;
  skinColor: string;
  hairColor: string;
  hairStyle: HairStyle;
}

// Skin tones — diverse palette
const SKIN_COLORS = [
  "#fde2c8", "#f5c5a0", "#d4956b", "#a0714f", "#ffe0bd", "#f5c5a0",
  "#fde2c8", "#d4956b", "#ffe0bd", "#f5c5a0", "#a0714f", "#fde2c8",
];

const ROLE_ORDER = [
  "coo", "planner", "engineer", "qa", "security", "reviewer",
  "devops", "investigator", "documentation", "monitor", "observer", "product",
  "researcher",
];

// Fixed avatar style per PocketTeam role — deterministic, not random
const ROLE_AVATAR_CONFIG: Record<string, { hairColor: string; hairStyle: HairStyle }> = {
  coo:           { hairColor: "#1a0a00", hairStyle: "flat" },
  planner:       { hairColor: "#5a3214", hairStyle: "round" },
  engineer:      { hairColor: "#2c1b0e", hairStyle: "buzz" },
  qa:            { hairColor: "#c2884a", hairStyle: "spiky" },
  security:      { hairColor: "#1a0a00", hairStyle: "flat" },
  reviewer:      { hairColor: "#2c1b0e", hairStyle: "long" },
  devops:        { hairColor: "#5a3214", hairStyle: "buzz" },
  investigator:  { hairColor: "#c2884a", hairStyle: "round" },
  documentation: { hairColor: "#1a0a00", hairStyle: "long" },
  monitor:       { hairColor: "#5a3214", hairStyle: "spiky" },
  observer:      { hairColor: "#2c1b0e", hairStyle: "round" },
  product:       { hairColor: "#c2884a", hairStyle: "flat" },
  researcher:    { hairColor: "#5a3214", hairStyle: "long" },
};

export function generateAvatar(role: string): AvatarStyle {
  const key = role.toLowerCase();
  const idx = ROLE_ORDER.indexOf(key);
  const config = ROLE_AVATAR_CONFIG[key] ?? { hairColor: "#2c1b0e", hairStyle: "flat" as HairStyle };

  return {
    skinColor: SKIN_COLORS[idx >= 0 ? idx : 0],
    hairColor: config.hairColor,
    shirtColor: ROLE_COLORS[key] ?? "#6B7280",
    hairStyle: config.hairStyle,
  };
}

export interface CharacterColors {
  shirtColor: string;
  skinColor: string;
  hairColor: string;
}

/** Returns 3D character colors for the given role — reuses existing avatar config. */
export function getCharacterColors(role: string): CharacterColors {
  const avatar = generateAvatar(role);
  return {
    shirtColor: avatar.shirtColor,
    skinColor: avatar.skinColor,
    hairColor: avatar.hairColor,
  };
}
