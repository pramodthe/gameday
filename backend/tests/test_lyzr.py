from app.services import lyzr_client
from app.services.coaching import generate_message


def test_unavailable_without_key():
    assert lyzr_client.available() is False


def test_extract_reply_handles_shapes():
    assert lyzr_client._extract_reply({"response": "hi"}) == "hi"
    assert lyzr_client._extract_reply({"answer": "yo"}) == "yo"
    assert lyzr_client._extract_reply("plain text") == "plain text"
    assert lyzr_client._extract_reply({"choices": [{"message": {"content": "c"}}]}) == "c"
    assert lyzr_client._extract_reply({"unrelated": 1}) is None


def test_chat_returns_none_without_key():
    assert lyzr_client.chat("hello") is None


def test_coaching_falls_back_to_deterministic_without_lyzr():
    msg = generate_message("RECOVER", 47, 1.6, ["HIGH_INJURY_RISK"], sport="soccer")
    assert "47" in msg
    assert "recovery" in msg.lower()
