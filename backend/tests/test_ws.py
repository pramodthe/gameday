from fastapi.testclient import TestClient

from app.main import app
from app.session.demo import DEMO_ANSWERS


def test_full_checkin_over_websocket_and_board():
    with TestClient(app) as client:  # `with` runs lifespan -> seeds demo data
        assert client.get("/health").json()["status"] == "ok"

        # Pre-demo board: roster populated, Alex not checked in today.
        board = client.get("/api/coach/coach-1/board").json()
        recs = {a["name"]: a["recommendation"] for a in board["athletes"]}
        assert recs["Maria Gomez"] == "RECOVER"
        assert recs["Sam Chen"] == "PUSH"
        assert recs["Jordan Lee"] == "MAINTAIN"
        alex = next(a for a in board["athletes"] if a["name"] == "Alex Rivera")
        assert alex["checked_in_today"] is False
        # At-risk athlete surfaced first.
        assert board["athletes"][0]["recommendation"] == "RECOVER"

        # Run Alex's full check-in over the WebSocket via text answers.
        sid = client.post("/api/sessions", json={"athlete_id": "a-alex"}).json()["session_id"]
        result = None
        with client.websocket_connect(f"/ws/checkin/{sid}") as ws:
            for answer in DEMO_ANSWERS:
                ws.send_json({"type": "text_answer", "text": answer})
            for _ in range(80):
                event = ws.receive_json()
                if event.get("type") == "result":
                    result = event
                    break

        assert result is not None
        assert result["readiness"] == 47
        assert result["recommendation"] == "RECOVER"
        assert result["acwr"] == 1.6
        assert "HIGH_INJURY_RISK" in result["flags"]
        assert result["streak"] == 1

        # Readiness endpoint reflects the completed check-in.
        readiness = client.get("/api/athletes/a-alex/readiness").json()
        assert readiness["result"]["score"] == 47

        # Board now shows Alex checked in today and flagged.
        board2 = client.get("/api/coach/coach-1/board").json()
        alex2 = next(a for a in board2["athletes"] if a["name"] == "Alex Rivera")
        assert alex2["checked_in_today"] is True
        assert alex2["recommendation"] == "RECOVER"

        assert client.get("/api/athletes/a-alex/streak").json()["current"] == 1


def test_ws_demo_run_control():
    with TestClient(app) as client:
        sid = client.post("/api/sessions", json={"athlete_id": "a-alex", "demo": True}).json()["session_id"]
        result = None
        with client.websocket_connect(f"/ws/checkin/{sid}") as ws:
            ws.send_json({"type": "demo_run"})
            for _ in range(80):
                event = ws.receive_json()
                if event.get("type") == "result":
                    result = event
                    break
        assert result is not None
        assert result["readiness"] == 47
        assert result["recommendation"] == "RECOVER"
