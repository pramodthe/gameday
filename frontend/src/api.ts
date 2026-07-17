import { API_BASE } from "./config";
import type { BoardRow } from "./types";

export async function createSession(athleteId: string, demo = false): Promise<{ session_id: string }> {
  const r = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ athlete_id: athleteId, demo }),
  });
  if (!r.ok) throw new Error(`session failed: ${r.status}`);
  return r.json();
}

export async function getBoard(coachId: string): Promise<{ date: string; athletes: BoardRow[] }> {
  const r = await fetch(`${API_BASE}/api/coach/${coachId}/board`);
  if (!r.ok) throw new Error(`board failed: ${r.status}`);
  return r.json();
}

export async function getStreak(athleteId: string): Promise<{ current: number }> {
  const r = await fetch(`${API_BASE}/api/athletes/${athleteId}/streak`);
  if (!r.ok) throw new Error(`streak failed: ${r.status}`);
  return r.json();
}
