import * as fs from "fs";
import * as path from "path";

export interface SessionStatus {
  contextUsedPct: number | null;
  contextRemainingPct: number | null;
  rateLimits: {
    fiveHour: number | null;
    fiveHourResetAt: string | null;
    sevenDay: number | null;
    sevenDayResetAt: string | null;
  };
  cost: number | null;
  model: string | null;
  sessionId: string | null;
  updatedAt: string;
}

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
