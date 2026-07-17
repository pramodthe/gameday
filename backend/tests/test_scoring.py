from app.services import scoring


def test_sleep_sub_anchors():
    assert scoring.sleep_sub(8) == 100
    assert scoring.sleep_sub(7) == 90
    assert scoring.sleep_sub(6) == 70
    assert scoring.sleep_sub(5) == 50
    assert scoring.sleep_sub(3) == 20  # < 4 hours
    assert scoring.sleep_sub(9) == 100  # clamps above 8
    assert scoring.sleep_sub(None) is None


def test_sleep_sub_interpolates():
    assert scoring.sleep_sub(6.5) == 80  # midway between 70 and 90


def test_fatigue_sub_range():
    assert scoring.fatigue_sub(1) == 100
    assert scoring.fatigue_sub(10) == 20
    assert scoring.fatigue_sub(None) is None


def test_soreness_and_nutrition_and_mood_subs():
    assert scoring.soreness_sub([]) == 100
    assert scoring.soreness_sub(["hamstring"]) == 75
    assert scoring.soreness_sub(["hamstring", "calf"]) == 50
    assert scoring.soreness_sub(None) is None
    assert scoring.nutrition_sub(True) == 100
    assert scoring.nutrition_sub(False) == 40
    assert scoring.nutrition_sub(None) == 70  # neutral, never dropped
    assert scoring.mood_sub(1) == 20
    assert scoring.mood_sub(5) == 100


def test_band_boundaries():
    assert scoring.band_for(49) == "LOW"
    assert scoring.band_for(50) == "MODERATE"
    assert scoring.band_for(74) == "MODERATE"
    assert scoring.band_for(75) == "HIGH"


def test_readiness_good_day_is_high():
    r = scoring.readiness(sleep_hours=8, session_rpe=3, soreness_areas=[], fueled=True, mood=5)
    assert r.band == "HIGH"
    assert r.missing == []


def test_readiness_demo_vector_is_low():
    # The on-stage demo: 5h sleep, hard session yesterday, tight hamstring, skipped breakfast, flat mood.
    r = scoring.readiness(
        sleep_hours=5, session_rpe=9, soreness_areas=["right_hamstring"], fueled=False, mood=2
    )
    assert r.score == 47
    assert r.band == "LOW"


def test_readiness_renormalizes_missing_inputs():
    r = scoring.readiness(sleep_hours=8, mood=5)  # rpe + soreness unknown; nutrition neutral
    assert "fatigue" in r.missing
    assert "soreness" in r.missing
    assert "nutrition" not in r.missing  # nutrition always contributes
    assert 0 <= r.score <= 100
