import * as fs from "fs";
import * as path from "path";
import chokidar, { FSWatcher } from "chokidar";

// Watches for existence of .pocketteam/KILL
// The presence of this file means all agent activity must stop.
//
// We use chokidar directly here (not FileWatcher) because we need the
// "unlink" event which FileWatcher's WatcherEvents interface does not expose.

export class KillSwitchReader {
  private killPath: string;
  private pocketteamDir: string;
  private active: boolean = false;
  private watcher: FSWatcher | null = null;
  private onChange: (active: boolean) => void;

  constructor(
    pocketteamDir: string,
    onChange: (active: boolean) => void = () => {}
  ) {
    this.pocketteamDir = pocketteamDir;
    this.killPath = path.resolve(path.join(pocketteamDir, "KILL"));
    this.onChange = onChange;
  }

  // Check initial state and start watching.
  // Returns true if kill switch is currently active.
  init(): boolean {
    this.active = fs.existsSync(this.killPath);

    // usePolling for Docker Desktop / bind mount compatibility
    this.watcher = chokidar.watch(this.pocketteamDir, {
      usePolling: true,
      interval: 500,
      ignoreInitial: true,
      persistent: true,
      depth: 0, // Only watch direct children of pocketteamDir
    });

    this.watcher
      .on("add", (filePath: string) => {
        if (this.isKillPath(filePath)) {
          this.setActive(true);
        }
      })
      .on("unlink", (filePath: string) => {
        if (this.isKillPath(filePath)) {
          this.setActive(false);
        }
      })
      .on("error", (error: unknown) => {
        const msg = error instanceof Error ? error.message : String(error);
        console.error("[KillSwitchReader] watcher error:", msg);
      });

    return this.active;
  }

  isActive(): boolean {
    return this.active;
  }

  // Re-check the kill file on demand (useful for polling fallback)
  check(): boolean {
    this.active = fs.existsSync(this.killPath);
    return this.active;
  }

  async close(): Promise<void> {
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = null;
    }
  }

  private isKillPath(filePath: string): boolean {
    return path.resolve(filePath) === this.killPath;
  }

  private setActive(value: boolean): void {
    if (value !== this.active) {
      this.active = value;
      this.onChange(value);
    }
  }
}
