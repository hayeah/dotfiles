import { homedir } from "os";
import { mkdirSync, statSync, renameSync, createWriteStream } from "fs";
import { join } from "path";
import { WriteStream } from "fs";

// --- Types ---

type LogLevel = "debug" | "info" | "warn" | "error";

interface LogFields {
  [key: string]: unknown;
}

const LEVEL_ORDER: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40,
};

const LEVEL_COLORS: Record<LogLevel, string> = {
  debug: "\x1b[36m", // cyan
  info: "\x1b[32m",  // green
  warn: "\x1b[33m",  // yellow
  error: "\x1b[31m", // red
};

const RESET = "\x1b[0m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const MAX_BACKUPS = 3;

// --- Rotating File Writer ---

class RotatingFileWriter {
  private stream: WriteStream | null = null;
  private currentSize = 0;
  private filePath: string;

  constructor(filePath: string) {
    this.filePath = filePath;
    this.ensureDir();
    this.openStream();
  }

  private ensureDir() {
    const dir = this.filePath.substring(0, this.filePath.lastIndexOf("/"));
    mkdirSync(dir, { recursive: true });
  }

  private openStream() {
    try {
      const stat = statSync(this.filePath);
      this.currentSize = stat.size;
    } catch {
      this.currentSize = 0;
    }
    this.stream = createWriteStream(this.filePath, { flags: "a" });
  }

  private rotate() {
    if (this.stream) {
      this.stream.end();
      this.stream = null;
    }

    // Shift backups: .3 -> delete, .2 -> .3, .1 -> .2, base -> .1
    for (let i = MAX_BACKUPS; i >= 1; i--) {
      const src = i === 1 ? this.filePath : `${this.filePath}.${i - 1}`;
      const dst = `${this.filePath}.${i}`;
      try {
        if (i === MAX_BACKUPS) {
          // Overwrite the oldest backup
        }
        renameSync(src, dst);
      } catch {
        // File may not exist, that's fine
      }
    }

    this.currentSize = 0;
    this.stream = createWriteStream(this.filePath, { flags: "a" });
  }

  write(line: string) {
    const buf = line + "\n";
    const byteLen = Buffer.byteLength(buf);

    if (this.currentSize + byteLen > MAX_FILE_SIZE) {
      this.rotate();
    }

    this.stream?.write(buf);
    this.currentSize += byteLen;
  }
}

// --- Console Formatter ---

function formatTime(): string {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function formatValue(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return String(v);
  return JSON.stringify(v);
}

function formatConsoleLine(
  level: LogLevel,
  event: string,
  fields: LogFields,
  useColor: boolean
): string {
  const time = formatTime();
  const levelStr = level.padEnd(8);
  const eventStr = event.padEnd(27);

  const fieldParts = Object.entries(fields)
    .map(([k, v]) => `${k}=${formatValue(v)}`)
    .join(" ");

  if (useColor) {
    const color = LEVEL_COLORS[level];
    return `${DIM}${time}${RESET} ${color}[${levelStr}]${RESET} ${BOLD}${eventStr}${RESET} ${fieldParts}`;
  }

  return `${time} [${levelStr}] ${eventStr} ${fieldParts}`;
}

// --- Logger ---

class Logger {
  private name: string;
  private boundFields: LogFields;
  private minLevel: number;
  private fileWriter: RotatingFileWriter;
  private useColor: boolean;

  constructor(
    name: string,
    fileWriter: RotatingFileWriter,
    minLevel: number,
    useColor: boolean,
    boundFields: LogFields = {}
  ) {
    this.name = name;
    this.fileWriter = fileWriter;
    this.minLevel = minLevel;
    this.useColor = useColor;
    this.boundFields = boundFields;
  }

  bind(fields: LogFields): Logger {
    return new Logger(
      this.name,
      this.fileWriter,
      this.minLevel,
      this.useColor,
      { ...this.boundFields, ...fields }
    );
  }

  debug(event: string, fields?: LogFields) {
    this.log("debug", event, fields);
  }

  info(event: string, fields?: LogFields) {
    this.log("info", event, fields);
  }

  warn(event: string, fields?: LogFields) {
    this.log("warn", event, fields);
  }

  error(event: string, fields?: LogFields) {
    this.log("error", event, fields);
  }

  private log(level: LogLevel, event: string, callFields?: LogFields) {
    if (LEVEL_ORDER[level] < this.minLevel) return;

    // Merge: bound fields first, call fields override
    const merged: LogFields = { ...this.boundFields, ...callFields };

    // Console output to stderr
    const consoleLine = formatConsoleLine(level, event, merged, this.useColor);
    process.stderr.write(consoleLine + "\n");

    // JSONL file output
    const jsonRecord: Record<string, unknown> = {
      timestamp: new Date().toISOString(),
      level,
      logger: this.name,
      event,
      ...merged,
    };

    // Capture stack trace for error level
    if (level === "error") {
      const err = callFields?.error;
      if (err instanceof Error && err.stack) {
        jsonRecord.exception = err.stack;
      }
    }

    this.fileWriter.write(JSON.stringify(jsonRecord));
  }
}

// --- Factory ---

const loggerCache = new Map<string, Logger>();
const fileWriterCache = new Map<string, RotatingFileWriter>();

function resolveMinLevel(): number {
  const envLevel = process.env.LOG_LEVEL?.toLowerCase() as LogLevel | undefined;
  if (envLevel && envLevel in LEVEL_ORDER) {
    return LEVEL_ORDER[envLevel];
  }
  return LEVEL_ORDER.info;
}

function getFileWriter(name: string): RotatingFileWriter {
  let writer = fileWriterCache.get(name);
  if (!writer) {
    const logDir = join(homedir(), ".local", "log");
    const filePath = join(logDir, `${name}.jsonl`);
    writer = new RotatingFileWriter(filePath);
    fileWriterCache.set(name, writer);
  }
  return writer;
}

export const logger = {
  new(name: string): Logger {
    let cached = loggerCache.get(name);
    if (cached) return cached;

    const useColor = process.stderr.isTTY ?? false;
    const minLevel = resolveMinLevel();
    const fileWriter = getFileWriter(name);

    cached = new Logger(name, fileWriter, minLevel, useColor);
    loggerCache.set(name, cached);
    return cached;
  },
};

export type { Logger, LogLevel, LogFields };
