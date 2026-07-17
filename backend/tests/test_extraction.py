from app.services import extraction as ex


def r(field, text):
    return ex.extract(field, text, use_llm=False)


def test_sleep_numeric_and_fuzzy():
    assert r("sleep", "about five, pretty restless")["sleep_hours"] == 5
    assert r("sleep", "I got seven and a half hours")["sleep_hours"] == 7.5


def test_load_words_and_bare_rpe():
    v = r("load", "two hour match yesterday, legs cooked, like an 8")
    assert v["duration_min"] == 120
    assert v["session_rpe"] == 8


def test_load_minutes_and_qualitative():
    v = r("load", "90 minutes, pretty hard")
    assert v["duration_min"] == 90
    assert v["session_rpe"] == 8


def test_soreness_positive_with_side():
    v = r("soreness", "right hamstring is a bit tight")
    assert v["areas"] == ["right hamstring"]
    assert v["_ok"] is True


def test_soreness_negative():
    v = r("soreness", "nothing really, feeling good")
    assert v["areas"] == []
    assert v["_ok"] is True


def test_nutrition_skip_and_ate():
    assert r("nutrition", "I skipped breakfast")["fueled"] is False
    assert r("nutrition", "yeah I ate, had some eggs")["fueled"] is True


def test_mood_number_and_word():
    assert r("mood", "feeling flat, like a two")["mood"] == 2
    assert r("mood", "pretty good, a 4")["mood"] == 4


def test_uninterpretable_marks_not_ok():
    assert r("sleep", "hello there")["_ok"] is False
    assert r("mood", "no idea honestly")["_ok"] is False
