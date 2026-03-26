import * as fs from "fs";
import * as path from "path";
import { SessionStatus } from "./types.js";

export type { SessionStatus };

export class SessionStatusReader {
  private filePath: string;
  private lastStatus: SessionStatus | null = null;

  constructor(pocketteamDir: string) {
    this.filePath = path.join(pocketteamDir, "session-status.json");
  }

  getFilePath(): string {
    return this.filePath;
  }

  read(): SessionStatus | null {
    if (!fs.existsSync(this.filePath)) return this.lastStatus;

    try {
      const raw = fs.readFileSync(this.filePath, "utf-8");
      const parsed = JSON.parse(raw);
      this.lastStatus = parsed as SessionStatus;
      return this.lastStatus;
    } catch {
      return this.lastStatus;
    }
  }

  getCurrent(): SessionStatus | null {
    return this.lastStatus;
  }
}
