import { createClient, RedisClientType } from "redis";
import {
  Persistence,
  persistTape,
  reviveTape,
  redactRequestHeaders,
} from "./persistence";
import { TapeRecord } from "./tape";

export class RedisPersistence implements Persistence {
  private client: RedisClientType;

  constructor(
    redisHost: string,
    redisPort: number,
    private readonly redactHeaders: string[],
  ) {
    this.client = createClient({
      url: `redis://${redisHost}:${redisPort}`,
    });
    this.client.connect();
  }

  async saveTape(tapeName: string, tapeRecords: TapeRecord[]): Promise<void> {
    const persistedTapeRecords = tapeRecords
      .map((r) => this.redact(r))
      .map(persistTape);
    await this.client.set(tapeName, JSON.stringify(persistedTapeRecords));
  }

  async loadTape(tapeName: string): Promise<TapeRecord[]> {
    const tape = await this.client.get(tapeName);
    if (!tape) {
      throw new Error(`No tape found with name ${tapeName}`);
    }
    return JSON.parse(tape).map(reviveTape);
  }

  isTapeNameValid(tapeName: string): boolean {
    // For redis, any string is a valid key.
    return !!tapeName;
  }

  private redact(record: TapeRecord): TapeRecord {
    redactRequestHeaders(record, this.redactHeaders);
    return record;
  }
}
