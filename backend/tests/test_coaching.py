from app.services.coaching import fallback_message, recommend


def test_recommend_recover_on_low_band():
    assert recommend("LOW", 1.0, []) == "RECOVER"


def test_recommend_recover_on_injury_flag_even_if_high():
    assert recommend("HIGH", 1.6, ["HIGH_INJURY_RISK"]) == "RECOVER"


def test_recommend_push_when_high_and_balanced_load():
    assert recommend("HIGH", 1.1, []) == "PUSH"


def test_recommend_no_push_when_acwr_out_of_range():
    assert recommend("HIGH", 1.4, []) == "MAINTAIN"


def test_recommend_maintain_is_default():
    assert recommend("MODERATE", 1.0, []) == "MAINTAIN"


def test_fallback_message_is_actionable():
    msg = fallback_message("RECOVER", 47, 1.6, ["HIGH_INJURY_RISK"])
    assert "47" in msg
    assert "recovery" in msg.lower()
    assert "1.6" in msg
