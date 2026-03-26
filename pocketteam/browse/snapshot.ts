/**
 * snapshot.ts — Accessibility Tree Parser + Ref Assignment
 * Parses ariaSnapshot YAML-like output and assigns @e1, @e2... refs.
 */

import { Page } from "playwright-core";
import { BrowserManager } from "./browser.ts";

// Interactive ARIA roles that agents can interact with
const INTERACTIVE_ROLES = new Set([
  "button",
  "link",
  "textbox",
  "searchbox",
  "checkbox",
  "radio",
  "combobox",
  "listbox",
  "option",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "switch",
  "tab",
  "slider",
  "spinbutton",
  "treeitem",
  "gridcell",
  "columnheader",
  "rowheader",
  "select",
]);

export interface SnapshotOptions {
  interactiveOnly: boolean; // -i flag
  compact: boolean;         // -c flag
  diff: boolean;            // -D flag
}

// Store last snapshot for diff mode
let lastSnapshotText: string | null = null;

export async function takeSnapshot(
  browserManager: BrowserManager,
  options: SnapshotOptions
): Promise<string> {
  const page = browserManager.getPage();

  // Get raw aria snapshot from Playwright
  let rawSnapshot: string;
  try {
    rawSnapshot = await page.locator("body").ariaSnapshot();
  } catch (err: any) {
    throw new Error(`ariaSnapshot failed: ${err.message}`);
  }

  // Clear existing refs before assigning new ones
  browserManager.clearRefs();

  // Parse the YAML-like ariaSnapshot output
  const lines = rawSnapshot.split("\n");
  const outputLines: string[] = [];
  let refCounter = 1;

  for (const line of lines) {
    if (!line.trim()) continue;

    // Parse ariaSnapshot line format:
    // - role "name" [state]
    // - role [state]  (no name)
    // Indentation is preserved for tree structure

    const parsed = parseAriaLine(line);
    if (!parsed) {
      // Non-element lines (document root, etc.) — include verbatim unless compact/interactive filter
      if (!options.interactiveOnly && !options.compact) {
        outputLines.push(line);
      }
      continue;
    }

    const { indent, role, name, attrs } = parsed;

    // Filter interactive-only
    if (options.interactiveOnly && !INTERACTIVE_ROLES.has(role.toLowerCase())) {
      continue;
    }

    // Assign ref
    const ref = `@e${refCounter++}`;

    // Build locator
    const locator = buildLocator(page, role, name, attrs);
    browserManager.storeRef(ref, { locator, role, name: name || "" });

    // Format output line
    const formattedLine = formatLine(ref, indent, role, name, attrs, options.compact);
    outputLines.push(formattedLine);
  }

  const result = outputLines.join("\n");

  // Handle diff mode
  if (options.diff) {
    const diffOutput = computeDiff(lastSnapshotText || "", result);
    lastSnapshotText = result;
    return diffOutput || "(no changes since last snapshot)";
  }

  lastSnapshotText = result;
  return result || "(empty page)";
}

interface ParsedLine {
  indent: string;
  role: string;
  name: string;
  attrs: string;
}

function parseAriaLine(line: string): ParsedLine | null {
  // ariaSnapshot format: "  - role \"name\" [disabled] [selected] ..."
  // or "  - role [disabled]"
  // or "  - role \"name\":"  (container with children)
  const match = line.match(/^(\s*)- (\w[\w-]*)(?: "([^"]*)")?(.*)$/);
  if (!match) return null;

  const indent = match[1] || "";
  const role = match[2];
  const name = match[3] || "";
  const attrs = (match[4] || "").trim();

  // Skip pure structural/text elements that aren't interactive and have no role value
  // document, region, main, article, section, etc. are non-leaf structural roles
  // We still return them so caller can decide

  return { indent, role, name, attrs };
}

function buildLocator(page: Page, role: string, name: string, attrs: string) {
  // Map ariaSnapshot role names to Playwright's getByRole roles
  const roleMap: Record<string, string> = {
    textbox: "textbox",
    searchbox: "searchbox",
    button: "button",
    link: "link",
    checkbox: "checkbox",
    radio: "radio",
    combobox: "combobox",
    listbox: "listbox",
    option: "option",
    menuitem: "menuitem",
    menuitemcheckbox: "menuitemcheckbox",
    menuitemradio: "menuitemradio",
    switch: "switch",
    tab: "tab",
    slider: "slider",
    spinbutton: "spinbutton",
    treeitem: "treeitem",
    gridcell: "gridcell",
    columnheader: "columnheader",
    rowheader: "rowheader",
  };

  const playwrightRole = (roleMap[role.toLowerCase()] || role.toLowerCase()) as any;

  if (name) {
    return page.getByRole(playwrightRole, { name, exact: true });
  }
  return page.getByRole(playwrightRole);
}

function formatLine(
  ref: string,
  indent: string,
  role: string,
  name: string,
  attrs: string,
  compact: boolean
): string {
  const nameStr = name ? ` "${name}"` : "";
  const attrsStr = attrs ? ` ${attrs}` : "";

  if (compact) {
    // One-line compact: @e1 button "Submit"
    return `${ref} ${role}${nameStr}${attrsStr}`;
  }

  // Normal: preserve indentation, prepend ref
  return `${indent}${ref} - ${role}${nameStr}${attrsStr}`;
}

function computeDiff(oldText: string, newText: string): string {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");

  // Simple unified diff implementation
  const removed = oldLines.filter((l) => !newLines.includes(l));
  const added = newLines.filter((l) => !oldLines.includes(l));

  if (removed.length === 0 && added.length === 0) {
    return "";
  }

  const diffLines: string[] = ["--- previous snapshot", "+++ current snapshot", ""];
  for (const line of removed) {
    diffLines.push(`- ${line}`);
  }
  for (const line of added) {
    diffLines.push(`+ ${line}`);
  }

  return diffLines.join("\n");
}

export function resetLastSnapshot(): void {
  lastSnapshotText = null;
}
