import * as path from "path";
import { PocketTeamEvent } from "./types.js";
import { TailReader } from "../watcher/TailReader.js";

// Reads .pocketteam/events/stream.jsonl
// Initial load: last 1000 events via efficient tail-seek.
// Streaming: new entries pushed to callback on each file-change notification.

export class EventStreamReader {
  private streamPath: string;
  private tailReader: TailReader;
  private events: PocketTeamEvent[] = [];
  private onNew: (event: PocketTeamEvent) => void;

  constructor(pocketteamDir: string, onNew: (event: PocketTeamEvent) => void = () => {}) {
    this.streamPath = path.join(pocketteamDir, "events", "stream.jsonl");
    this.onNew = onNew;
    this.tailReader = new TailReader(
      this.streamPath,
      (raw) => this.handleEntry(raw),
      (msg) => console.warn("[EventStreamReader]", msg)
    );
  }

  // Load last 1000 events. Call once at startup.
  loadInitial(n: number = 1000): PocketTeamEvent[] {
    this.events = [];
    this.tailReader.readLastLines(n);
    return [...this.events];
  }

  // Call this when the file-watcher fires a change event for the stream file.
  onFileChange(): void {
    this.tailReader.readNew();
  }

  // Return current in-memory snapshot (last N loaded + any streamed since)
  getEvents(): PocketTeamEvent[] {
    return [...this.events];
  }

  getStreamPath(): string {
    return this.streamPath;
  }

  private handleEntry(raw: unknown): void {
    if (typeof raw !== "object" || raw === null) return;

    const entry = raw as Record<string, unknown>;

    // Validate required fields
    const ts = entry["ts"] ?? entry["timestamp"];
    if (typeof ts !== "string") return;

    const event: PocketTeamEvent = {
      ts: ts,
      agent: typeof entry["agent"] === "string" ? entry["agent"] : "unknown",
      type: typeof entry["type"] === "string" ? entry["type"] : "",
      tool: typeof entry["tool"] === "string" ? entry["tool"] : "",
      status: typeof entry["status"] === "string" ? entry["status"] : "",
      action: typeof entry["action"] === "string" ? entry["action"] : "",
    };

    this.events.push(event);
    // Keep memory bounded — keep last 1000 in memory
    if (this.events.length > 1000) {
      this.events.shift();
    }

    this.onNew(event);
  }
}
