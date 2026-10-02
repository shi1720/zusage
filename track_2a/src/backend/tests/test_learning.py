from datetime import UTC, datetime, timedelta

from zusage.db import Drill, Interview
from zusage.learning import calibration, review, streak_days


def test_leitner_promotion_and_reset():
    now = datetime(2026, 10, 1, tzinfo=UTC)
    d = Drill(user_id="u", question_id="q", box=1, due_at=now)
    review(d, 3.5, now)
    assert d.box == 2 and d.due_at == now + timedelta(days=3)
    review(d, 3.2, now)
    assert d.box == 3 and d.due_at == now + timedelta(days=7)
    review(d, 1.5, now)
    assert d.box == 1 and d.due_at == now + timedelta(days=1) and d.reps == 3 and d.best_score == 3.5


def _iv(turns, days_ago=0):
    return Interview(user_id="u", occupation_id="x", language="de", persona_id="warm", answers=len(turns),
                     state={"turns": turns}, created_at=datetime.now(UTC) - timedelta(days=days_ago))


def test_calibration_accuracy_and_bias():
    turns = [{"self_rating": 3, "assessment": {"scores": {"clarity": 4}}},
             {"self_rating": 3, "assessment": {"scores": {"clarity": 2}}},
             {"self_rating": 1, "assessment": {"scores": {"clarity": 1}}}]
    cal = calibration([_iv(turns)])
    assert cal["n"] == 3 and cal["accuracy"] == round(2 / 3, 2) and cal["bias"] > 0


def test_streak_counts_consecutive_days():
    ivs = [_iv([{}], 0), _iv([{}], 1), _iv([{}], 2), _iv([{}], 5)]
    assert streak_days(ivs) == 3
