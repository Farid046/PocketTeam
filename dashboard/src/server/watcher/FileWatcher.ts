import chokidar, { FSWatcher } from "chokidar";

export interface WatcherEvents {
  onFileChange: (filePath: string) => void;
  onFileAdd: (filePath: string) => void;
  onError: (error: Error) => void;
}

export class FileWatcher {
  private watcher: FSWatcher | null = null;
  private events: WatcherEvents;

  constructor(events: WatcherEvents) {
    this.events = events;
  }

  watch(paths: string[]): void {
    // usePolling: true is required for Docker Desktop on macOS and Linux bind mounts.
    // Native inotify/FSEvents are unreliable across the hypervisor boundary.
    this.watcher = chokidar.watch(paths, {
      usePolling: true,
      interval: 500,
      binaryInterval: 1000,
      ignoreInitial: true,
      persistent: true,
      // Ignore hidden directories (e.g. .git) but NOT hidden files we want to watch
      ignored: (watchedPath: string, stats?: { isDirectory?: () => boolean }) => {
        // Only ignore hidden directories, not hidden files like .pocketteam/KILL
        if (stats && typeof stats.isDirectory === "function" && stats.isDirectory()) {
          const basename = watchedPath.split("/").pop() ?? "";
          return basename.startsWith(".") && basename !== ".pocketteam";
        }
        return false;
      },
    });

    this.watcher
      .on("change", (filePath: string) => this.events.onFileChange(filePath))
      .on("add", (filePath: string) => this.events.onFileAdd(filePath))
      .on("error", (error: unknown) =>
        this.events.onError(error instanceof Error ? error : new Error(String(error)))
      );
  }

  async close(): Promise<void> {
    if (this.watcher) {
      await this.watcher.close();
      this.watcher = null;
    }
  }
}
