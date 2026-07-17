from app.services import scoring


def test_acwr_steady_is_one():
    res = scoring.acwr([300] * 28, baseline=300)
    assert res.acwr == 1.0
    assert res.provisional is False
    assert res.flags == []


def test_acwr_spike_flags_injury_risk():
    # 3 steady weeks, then a week of doubled load -> acute >> chronic.
    res = scoring.acwr([300] * 21 + [600] * 7, baseline=300)
    assert res.acwr is not None and res.acwr > 1.5
    assert "HIGH_INJURY_RISK" in res.flags


def test_acwr_drop_flags_undertraining():
    res = scoring.acwr([300] * 21 + [100] * 7, baseline=300)
    assert res.acwr is not None and res.acwr < 0.8
    assert "UNDERTRAINING" in res.flags


def test_acwr_provisional_when_history_sparse():
    res = scoring.acwr([400] * 3, baseline=300)
    assert res.provisional is True
