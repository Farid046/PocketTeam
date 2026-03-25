import * as fs from "fs";

export class TailReader {
  private filePath: string;
  private offset: number = 0;
  private onEntry: (entry: unknown) => void;
  private onError: (msg: string) => void;

  constructor(
    filePath: string,
    onEntry: (entry: unknown) => void,
    onError?: (msg: string) => void
  ) {
    this.filePath = filePath;
    this.onEntry = onEntry;
    this.onError = onError || (() => {});
  }

  // Read last N lines efficiently by seeking from end — critical for 100MB+ files.
  // Allocates ~500 bytes per requested line, reads only that tail chunk.
  readLastLines(n: number = 1000): void {
    if (!fs.existsSync(this.filePath)) return;

    const stats = fs.statSync(this.filePath);
    const fileSize = stats.size;
    if (fileSize === 0) {
      this.offset = 0;
      return;
    }

    // Estimate 500 bytes per line; clamp to actual file size
    const bufSize = Math.min(fileSize, n * 500);
    const buf = Buffer.alloc(bufSize);
    const fd = fs.openSync(this.filePath, "r");
    const startPos = Math.max(0, fileSize - bufSize);
    fs.readSync(fd, buf, 0, bufSize, startPos);
    fs.closeSync(fd);

    const text = buf.toString("utf-8");
    const lines = text.split("\n").filter((l) => l.trim().length > 0);
    // When startPos > 0 we may have started in the middle of a line — discard it
    const validLines = startPos > 0 ? lines.slice(1) : lines;
    const lastN = validLines.slice(-n);

    for (const line of lastN) {
      this.parseLine(line);
    }

    this.offset = fileSize;
  }

  // Read only bytes written since last call — called on each file-change event
  readNew(): void {
    if (!fs.existsSync(this.filePath)) return;

    const stats = fs.statSync(this.filePath);

    if (stats.size < this.offset) {
      // File was truncated (e.g. log rotation) — re-read from start
      this.offset = 0;
    }

    if (stats.size === this.offset) return;

    const length = stats.size - this.offset;
    const buf = Buffer.alloc(length);
    const fd = fs.openSync(this.filePath, "r");
    fs.readSync(fd, buf, 0, length, this.offset);
    fs.closeSync(fd);

    this.offset = stats.size;

    const lines = buf.toString("utf-8").split("\n").filter((l) => l.trim().length > 0);
    for (const line of lines) {
      this.parseLine(line);
    }
  }

  // Current byte offset — useful for external inspection / testing
  getOffset(): number {
    return this.offset;
  }

  private parseLine(line: string): void {
    try {
      const parsed = JSON.parse(line);
      this.onEntry(parsed);
    } catch {
      // Partial write or corrupt line — skip silently, log preview
      const preview = line.slice(0, 80);
      this.onError(`Skipped malformed JSONL: ${preview}`);
    }
  }
}
