const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-GameDay-Tool-Key",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

export default async function (request: Request): Promise<Response> {
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders });
  }
  if (request.method !== "GET") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const expectedKey = Deno.env.get("GAMEDAY_LYZR_TOOL_SECRET");
  if (!expectedKey || request.headers.get("X-GameDay-Tool-Key") !== expectedKey) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  const userId = new URL(request.url).searchParams.get("user_id")?.trim();
  if (!userId) {
    return jsonResponse({ error: "user_id is required" }, 400);
  }

  const baseUrl = Deno.env.get("INSFORGE_BASE_URL")?.replace(/\/$/, "");
  const apiKey = Deno.env.get("API_KEY");
  if (!baseUrl || !apiKey) {
    return jsonResponse({ error: "Backend connection is not configured" }, 503);
  }

  const headers = { Authorization: `Bearer ${apiKey}`, apikey: apiKey };
  const recordsUrl = (table: string, query: URLSearchParams) =>
    `${baseUrl}/api/database/records/${table}?${query.toString()}`;

  const athleteQuery = new URLSearchParams({
    user_id: `eq.${userId}`,
    select: "id,display_name,sport,primary_goal",
    limit: "1",
  });
  const athleteResponse = await fetch(recordsUrl("athlete_profiles", athleteQuery), { headers });
  if (!athleteResponse.ok) {
    return jsonResponse({ error: "Athlete context lookup failed" }, 502);
  }
  const athletes = await athleteResponse.json();
  if (!Array.isArray(athletes) || !athletes.length) {
    return jsonResponse({ user_id: userId, found: false, recent_sessions: [], recent_movements: [] });
  }

  const athlete = athletes[0];
  const sessionQuery = new URLSearchParams({
    athlete_profile_id: `eq.${athlete.id}`,
    select: "livekit_room_name,status,started_at,completed_at",
    order: "started_at.desc",
    limit: "3",
  });
  const movementQuery = new URLSearchParams({
    athlete_profile_id: `eq.${athlete.id}`,
    select: "movement,reps,score,confidence,feedback,created_at",
    order: "created_at.desc",
    limit: "5",
  });
  const [sessionsResponse, movementsResponse] = await Promise.all([
    fetch(recordsUrl("checkin_sessions", sessionQuery), { headers }),
    fetch(recordsUrl("movement_analyses", movementQuery), { headers }),
  ]);

  return jsonResponse({
    user_id: userId,
    found: true,
    athlete: {
      display_name: athlete.display_name,
      sport: athlete.sport,
      primary_goal: athlete.primary_goal,
    },
    recent_sessions: sessionsResponse.ok ? await sessionsResponse.json() : [],
    recent_movements: movementsResponse.ok ? await movementsResponse.json() : [],
  });
}
