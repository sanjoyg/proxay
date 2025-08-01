import yaml from "js-yaml";
import { createClient, RedisClientType } from "redis";
import {
  IPersistence,
  persistTape,
  reviveTape,
  redactRequestHeaders,
} from "./persistence";
import { PersistedTapeRecord, TapeRecord } from "./tape";

export class RedisPersistence implements IPersistence {
  private client: RedisClientType;

  constructor(
    private readonly redactHeaders: string[],
    redisHost: string,
    redisPort: number,
  ) {
    this.client = createClient({
      socket: {
        host: redisHost,
        port: redisPort,
      },
    });
    this.client.connect();
  }

  private redact(record: TapeRecord): TapeRecord {
    redactRequestHeaders(record, this.redactHeaders);
    return record;
  }

  async saveTape(tapeName: string, tapeRecords: TapeRecord[]): Promise<void> {
    const persistedTapeRecords = tapeRecords
      .map(this.redact, this)
      .map(persistTape);

    const yamlData = yaml.dump({
      http_interactions: persistedTapeRecords,
    });

    await this.client.set(tapeName, yamlData);
  }

  async loadTape(tapeName: string): Promise<TapeRecord[]> {
    const yamlData = await this.client.get(tapeName);

    if (!yamlData) {
      throw new Error(`No tape found with name ${tapeName}`);
    }

    const persistedTapeRecords = (yaml.load(yamlData) as Record<string, any>)
      .http_interactions as PersistedTapeRecord[];
    return persistedTapeRecords.map(reviveTape);
  }

  isTapeNameValid(_tapeName: string): boolean {
    // For Redis, any string is a valid key.
    return true;
  }
}
