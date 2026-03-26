/**
 * browser.ts — Chromium Manager
 * Manages a single BrowserContext + active Page via playwright-core.
 */

import { chromium, Browser, BrowserContext, Page, Locator } from "playwright-core";

export interface RefEntry {
  locator: Locator;
  role: string;
  name: string;
}

export class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private refMap: Map<string, RefEntry> = new Map();
  private consoleMessages: string[] = [];
  private onDisconnect: () => void;

  constructor(onDisconnect: () => void) {
    this.onDisconnect = onDisconnect;
  }

  async launch(headed: boolean = false): Promise<void> {
    // Use the system-installed Chrome/Chromium if playwright's own binary isn't available.
    // headed = true: visible browser window (for user to watch QA work)
    // headed = false: headless (default, no window)
    this.browser = await chromium.launch({
      headless: !headed,
      channel: "chrome",
      args: [
        "--enable-webgl",
        "--enable-webgl2-compute-context",
        "--use-gl=angle",
        "--use-angle=metal",
        "--enable-gpu-rasterization",
        "--ignore-gpu-blocklist",
      ],
    });

    this.browser.on("disconnected", () => {
      console.error("[browser] Chromium disconnected unexpectedly");
      this.onDisconnect();
    });

    this.context = await this.browser.newContext();
    this.page = await this.context.newPage();
    this._attachPageListeners(this.page);
  }

  private _attachPageListeners(page: Page): void {
    // Capture console messages
    page.on("console", (msg) => {
      const entry = `[${msg.type()}] ${msg.text()}`;
      this.consoleMessages.push(entry);
      // Keep last 200 messages
      if (this.consoleMessages.length > 200) {
        this.consoleMessages.shift();
      }
    });

    // Clear refs on navigation (framenavigated fires for main frame)
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) {
        this.clearRefs();
      }
    });
  }

  clearRefs(): void {
    this.refMap.clear();
  }

  storeRef(ref: string, entry: RefEntry): void {
    this.refMap.set(ref, entry);
  }

  resolveRef(ref: string): Locator {
    const entry = this.refMap.get(ref);
    if (!entry) {
      // Exit code 2 for stale/missing ref
      const err = new Error(`Ref ${ref} is stale or unknown — run 'snapshot' for fresh refs`);
      (err as any).exitCode = 2;
      throw err;
    }
    return entry.locator;
  }

  getRefMap(): Map<string, RefEntry> {
    return this.refMap;
  }

  getConsoleMessages(): string[] {
    return [...this.consoleMessages];
  }

  clearConsoleMessages(): void {
    this.consoleMessages = [];
  }

  getPage(): Page {
    if (!this.page) {
      throw new Error("No active page — browser not launched");
    }
    return this.page;
  }

  async goto(url: string): Promise<void> {
    const page = this.getPage();
    await page.goto(url, { waitUntil: "load" });
  }

  async back(): Promise<void> {
    await this.getPage().goBack({ waitUntil: "load" });
  }

  async forward(): Promise<void> {
    await this.getPage().goForward({ waitUntil: "load" });
  }

  async reload(): Promise<void> {
    await this.getPage().reload({ waitUntil: "load" });
  }

  async close(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
      this.context = null;
      this.page = null;
    }
  }

  isLaunched(): boolean {
    return this.browser !== null && this.page !== null;
  }

  currentUrl(): string {
    if (!this.page) return "(no page)";
    return this.page.url();
  }

  refCount(): number {
    return this.refMap.size;
  }
}
