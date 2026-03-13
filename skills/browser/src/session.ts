import { mkdirSync, readFileSync, writeFileSync, unlinkSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import type { ContextSpec } from "./context-spec.js";

const SESSIONS_DIR = join(homedir(), ".cache", "browser-tools", "sessions");

export interface SessionFile {
	key: string;
	pid: number;
	targetId: string;
	windowId: number;
	spec: ContextSpec;
	createdAt: string;
}

function ensureDir() {
	mkdirSync(SESSIONS_DIR, { recursive: true });
}

function sessionPath(key: string): string {
	return join(SESSIONS_DIR, `${key}.json`);
}

function isProcessAlive(pid: number): boolean {
	try {
		process.kill(pid, 0);
		return true;
	} catch {
		return false;
	}
}

export function generateSessionKey(): string {
	ensureDir();
	const existing = new Set<string>();
	try {
		for (const f of readdirSync(SESSIONS_DIR)) {
			if (f.endsWith(".json")) existing.add(f.replace(".json", ""));
		}
	} catch {}

	for (let i = 0; i < 100; i++) {
		const key = randomBytes(2).toString("hex");
		if (!existing.has(key)) return key;
	}
	// Fallback to longer key
	return randomBytes(4).toString("hex");
}

export function writeSession(session: SessionFile): void {
	ensureDir();
	writeFileSync(sessionPath(session.key), JSON.stringify(session, null, 2));
}

export function readSession(key: string): SessionFile | null {
	try {
		const data = readFileSync(sessionPath(key), "utf-8");
		const session = JSON.parse(data) as SessionFile;
		if (!isProcessAlive(session.pid)) {
			// Stale session — clean up
			try { unlinkSync(sessionPath(key)); } catch {}
			return null;
		}
		return session;
	} catch {
		return null;
	}
}

export function deleteSession(key: string): void {
	try { unlinkSync(sessionPath(key)); } catch {}
}

export function listSessions(): SessionFile[] {
	ensureDir();
	const sessions: SessionFile[] = [];
	try {
		for (const f of readdirSync(SESSIONS_DIR)) {
			if (!f.endsWith(".json")) continue;
			const key = f.replace(".json", "");
			const session = readSession(key);
			if (session) sessions.push(session);
		}
	} catch {}
	return sessions;
}
