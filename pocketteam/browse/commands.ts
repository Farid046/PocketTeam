/**
 * commands.ts — All Command Handlers
 * Each handler returns { output: string, exitCode: number }
 */

import { existsSync, mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { BrowserManager } from "./browser.ts";
import { takeSnapshot, SnapshotOptions, resetLastSnapshot } from "./snapshot.ts";

export interface CommandResult {
  output: string;
  exitCode: number;
}

const SCREENSHOTS_DIR = join(homedir(), ".pocketteam", "screenshots");
const MAX_TEXT_LENGTH = 8000;

// Ensure screenshots directory exists
function ensureScreenshotsDir(): void {
  if (!existsSync(SCREENSHOTS_DIR)) {
    mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }
}

function ok(output: string): CommandResult {
  return { output, exitCode: 0 };
}

function fail(output: string, exitCode = 1): CommandResult {
  return { output, exitCode };
}

function wrapError(err: unknown, defaultMsg = "Command failed"): CommandResult {
  const e = err as any;
  const exitCode = typeof e.exitCode === "number" ? e.exitCode : 1;
  const message = e.message || defaultMsg;
  return { output: message, exitCode };
}

// ─────────────────────────────────────────────
// Navigation
// ─────────────────────────────────────────────

export async function cmdGoto(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const url = args[0];
  if (!url) return fail("goto: URL argument required");
  try {
    resetLastSnapshot();
    await browser.goto(url);
    return ok(`Navigated to ${url}`);
  } catch (err) {
    return wrapError(err, `goto failed: ${url}`);
  }
}

export async function cmdBack(browser: BrowserManager): Promise<CommandResult> {
  try {
    resetLastSnapshot();
    await browser.back();
    return ok(`Navigated back → ${browser.currentUrl()}`);
  } catch (err) {
    return wrapError(err, "back failed");
  }
}

export async function cmdForward(browser: BrowserManager): Promise<CommandResult> {
  try {
    resetLastSnapshot();
    await browser.forward();
    return ok(`Navigated forward → ${browser.currentUrl()}`);
  } catch (err) {
    return wrapError(err, "forward failed");
  }
}

export async function cmdReload(browser: BrowserManager): Promise<CommandResult> {
  try {
    resetLastSnapshot();
    await browser.reload();
    return ok(`Reloaded ${browser.currentUrl()}`);
  } catch (err) {
    return wrapError(err, "reload failed");
  }
}

// ─────────────────────────────────────────────
// Snapshot
// ─────────────────────────────────────────────

export async function cmdSnapshot(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const options: SnapshotOptions = {
    interactiveOnly: args.includes("-i"),
    compact: args.includes("-c"),
    diff: args.includes("-D"),
  };

  try {
    const result = await takeSnapshot(browser, options);
    return ok(result);
  } catch (err) {
    return wrapError(err, "snapshot failed");
  }
}

// ─────────────────────────────────────────────
// Interaction
// ─────────────────────────────────────────────

export async function cmdClick(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  if (!ref) return fail("click: ref argument required (e.g. @e1)");
  try {
    const locator = browser.resolveRef(ref);
    await locator.click();
    return ok(`Clicked ${ref}`);
  } catch (err) {
    return wrapError(err, `click ${ref} failed`);
  }
}

export async function cmdFill(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  const text = args.slice(1).join(" ");
  if (!ref) return fail("fill: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    await locator.fill(text);
    return ok(`Filled ${ref} with: ${text}`);
  } catch (err) {
    return wrapError(err, `fill ${ref} failed`);
  }
}

export async function cmdType(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  const text = args.slice(1).join(" ");
  if (!ref) return fail("type: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    await locator.pressSequentially(text, { delay: 30 });
    return ok(`Typed into ${ref}: ${text}`);
  } catch (err) {
    return wrapError(err, `type ${ref} failed`);
  }
}

export async function cmdSelect(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  const value = args.slice(1).join(" ");
  if (!ref) return fail("select: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    await locator.selectOption(value);
    return ok(`Selected "${value}" in ${ref}`);
  } catch (err) {
    return wrapError(err, `select ${ref} failed`);
  }
}

export async function cmdKey(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const keyName = args[0];
  if (!keyName) return fail("key: key name argument required (e.g. Enter, Escape, Tab)");
  try {
    const page = browser.getPage();
    await page.keyboard.press(keyName);
    return ok(`Pressed key: ${keyName}`);
  } catch (err) {
    return wrapError(err, `key ${keyName} failed`);
  }
}

export async function cmdHover(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  if (!ref) return fail("hover: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    await locator.hover();
    return ok(`Hovered ${ref}`);
  } catch (err) {
    return wrapError(err, `hover ${ref} failed`);
  }
}

export async function cmdScroll(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  // scroll @e1 down 500
  // scroll @e1 up 300
  const ref = args[0];
  const direction = args[1] || "down";
  const amount = parseInt(args[2] || "300", 10);

  if (!ref) return fail("scroll: ref argument required");

  try {
    const locator = browser.resolveRef(ref);
    const deltaX = 0;
    const deltaY = direction === "up" ? -amount : amount;
    await locator.hover();
    const page = browser.getPage();
    await page.mouse.wheel(deltaX, deltaY);
    return ok(`Scrolled ${direction} ${amount}px at ${ref}`);
  } catch (err) {
    return wrapError(err, `scroll ${ref} failed`);
  }
}

// ─────────────────────────────────────────────
// Wait
// ─────────────────────────────────────────────

export async function cmdWaitText(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const text = args[0];
  const timeout = parseInt(args[1] || "10000", 10);
  if (!text) return fail("wait text: text argument required");
  try {
    const page = browser.getPage();
    await page.getByText(text).first().waitFor({ timeout });
    return ok(`Text found: "${text}"`);
  } catch (err: any) {
    if (err.message?.includes("Timeout")) {
      return fail(`Timeout: text "${text}" not found within ${timeout}ms`, 3);
    }
    return wrapError(err, `wait text failed`);
  }
}

export async function cmdWaitSelector(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const css = args[0];
  const timeout = parseInt(args[1] || "10000", 10);
  if (!css) return fail("wait selector: CSS selector argument required");
  try {
    const page = browser.getPage();
    await page.locator(css).first().waitFor({ timeout });
    return ok(`Selector found: "${css}"`);
  } catch (err: any) {
    if (err.message?.includes("Timeout")) {
      return fail(`Timeout: selector "${css}" not found within ${timeout}ms`, 3);
    }
    return wrapError(err, `wait selector failed`);
  }
}

export async function cmdWaitIdle(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ms = parseInt(args[0] || "2000", 10);
  try {
    const page = browser.getPage();
    await page.waitForLoadState("networkidle", { timeout: ms + 5000 });
    return ok(`Network idle (waited up to ${ms}ms)`);
  } catch (err: any) {
    // networkidle timeout is not fatal
    return ok(`Network idle timeout after ${ms}ms (continuing)`);
  }
}

export async function cmdWaitUrl(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const pattern = args[0];
  const timeout = parseInt(args[1] || "10000", 10);
  if (!pattern) return fail("wait url: pattern argument required");
  try {
    const page = browser.getPage();
    await page.waitForURL(new RegExp(pattern), { timeout });
    return ok(`URL matched pattern: "${pattern}" → ${page.url()}`);
  } catch (err: any) {
    if (err.message?.includes("Timeout")) {
      return fail(
        `Timeout: URL did not match "${pattern}" within ${timeout}ms (current: ${browser.currentUrl()})`,
        3
      );
    }
    return wrapError(err, `wait url failed`);
  }
}

// ─────────────────────────────────────────────
// Assert
// ─────────────────────────────────────────────

export async function cmdAssertText(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const text = args[0];
  if (!text) return fail("assert text: text argument required");
  try {
    const page = browser.getPage();
    const bodyText = await page.innerText("body");
    if (bodyText.includes(text)) {
      return ok(`PASS: page contains "${text}"`);
    }
    return fail(`FAIL: page does not contain "${text}"`, 1);
  } catch (err) {
    return wrapError(err, `assert text failed`);
  }
}

export async function cmdAssertNoText(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const text = args[0];
  if (!text) return fail("assert no-text: text argument required");
  try {
    const page = browser.getPage();
    const bodyText = await page.innerText("body");
    if (!bodyText.includes(text)) {
      return ok(`PASS: page does not contain "${text}"`);
    }
    return fail(`FAIL: page contains "${text}" but should not`, 1);
  } catch (err) {
    return wrapError(err, `assert no-text failed`);
  }
}

export async function cmdAssertVisible(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  if (!ref) return fail("assert visible: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    const isVisible = await locator.isVisible();
    if (isVisible) {
      return ok(`PASS: ${ref} is visible`);
    }
    return fail(`FAIL: ${ref} is not visible`, 1);
  } catch (err) {
    return wrapError(err, `assert visible ${ref} failed`);
  }
}

export async function cmdAssertEnabled(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const ref = args[0];
  if (!ref) return fail("assert enabled: ref argument required");
  try {
    const locator = browser.resolveRef(ref);
    const isEnabled = await locator.isEnabled();
    if (isEnabled) {
      return ok(`PASS: ${ref} is enabled`);
    }
    return fail(`FAIL: ${ref} is disabled`, 1);
  } catch (err) {
    return wrapError(err, `assert enabled ${ref} failed`);
  }
}

export async function cmdAssertUrl(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const pattern = args[0];
  if (!pattern) return fail("assert url: pattern argument required");
  try {
    const currentUrl = browser.currentUrl();
    const regex = new RegExp(pattern);
    if (regex.test(currentUrl)) {
      return ok(`PASS: URL "${currentUrl}" matches "${pattern}"`);
    }
    return fail(`FAIL: URL "${currentUrl}" does not match "${pattern}"`, 1);
  } catch (err) {
    return wrapError(err, `assert url failed`);
  }
}

// ─────────────────────────────────────────────
// Read
// ─────────────────────────────────────────────

export async function cmdText(browser: BrowserManager): Promise<CommandResult> {
  try {
    const page = browser.getPage();
    let text = await page.innerText("body");
    if (text.length > MAX_TEXT_LENGTH) {
      text = text.slice(0, MAX_TEXT_LENGTH) + `\n... [truncated at ${MAX_TEXT_LENGTH} chars]`;
    }
    return ok(text);
  } catch (err) {
    return wrapError(err, "text extraction failed");
  }
}

export async function cmdScreenshot(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  try {
    ensureScreenshotsDir();
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").replace("Z", "");
    const defaultPath = join(SCREENSHOTS_DIR, `${timestamp}.png`);
    const outputPath = args[0] || defaultPath;

    const page = browser.getPage();
    await page.screenshot({ path: outputPath, fullPage: false });
    return ok(`Screenshot saved: ${outputPath}`);
  } catch (err) {
    return wrapError(err, "screenshot failed");
  }
}

export async function cmdConsole(browser: BrowserManager): Promise<CommandResult> {
  const messages = browser.getConsoleMessages();
  if (messages.length === 0) {
    return ok("(no console messages captured)");
  }
  return ok(messages.join("\n"));
}

export async function cmdEvalJs(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  if (process.env.PTBROWSE_ALLOW_EVAL !== "1") {
    return fail(
      "eval is disabled by default. Set PTBROWSE_ALLOW_EVAL=1 to enable.",
      1
    );
  }
  const expr = args.join(" ");
  if (!expr) return fail("eval: JS expression argument required");
  try {
    const page = browser.getPage();
    const result = await page.evaluate(expr);
    const output =
      result === undefined
        ? "(undefined)"
        : typeof result === "object"
        ? JSON.stringify(result, null, 2)
        : String(result);
    return ok(output);
  } catch (err) {
    return wrapError(err, `eval failed: ${expr}`);
  }
}

// ─────────────────────────────────────────────
// Meta
// ─────────────────────────────────────────────

export async function cmdViewport(
  browser: BrowserManager,
  args: string[]
): Promise<CommandResult> {
  const w = parseInt(args[0] || "1280", 10);
  const h = parseInt(args[1] || "720", 10);
  if (isNaN(w) || isNaN(h)) return fail("viewport: width and height must be numbers");
  try {
    const page = browser.getPage();
    await page.setViewportSize({ width: w, height: h });
    return ok(`Viewport set to ${w}x${h}`);
  } catch (err) {
    return wrapError(err, "viewport failed");
  }
}

export function cmdStatus(
  browser: BrowserManager,
  startedAt: string,
  port: number
): CommandResult {
  const uptime = Math.round((Date.now() - new Date(startedAt).getTime()) / 1000);
  const output = [
    `status: running`,
    `port: ${port}`,
    `uptime: ${uptime}s`,
    `url: ${browser.currentUrl()}`,
    `refs: ${browser.refCount()}`,
    `started: ${startedAt}`,
  ].join("\n");
  return ok(output);
}

export async function cmdCloseBrowser(browser: BrowserManager): Promise<CommandResult> {
  try {
    await browser.close();
    return ok("Browser closed. Daemon shutting down.");
  } catch (err) {
    return wrapError(err, "close failed");
  }
}
