export interface Session {
  id: string;
  userId: string;
  expiresAt: number;
}

const sessions = new Map<string, Session>();

export function create(userId: string, ttlMs: number): Session {
  const session = { id: crypto.randomUUID(), userId, expiresAt: Date.now() + ttlMs };
  sessions.set(session.id, session);
  return session;
}

export function get(id: string): Session | undefined {
  const session = sessions.get(id);
  if (session && session.expiresAt < Date.now()) {
    sessions.delete(id);
    return undefined;
  }
  return session;
}

export function touch(id: string, ttlMs: number): void {
  const session = sessions.get(id);
  if (session) {
    session.expiresAt = Date.now() + ttlMs;
  }
}
