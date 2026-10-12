from apps.risk.recommendation import RouteRecommender, RouteScore

R = RouteRecommender()


def _score(rid, severe=0, high=0, avg=0, dur=3600, notravel=0):
    return RouteScore(
        rid,
        no_travel_miles=notravel,
        severe_miles=severe,
        high_miles=high,
        avg_risk=avg,
        duration_s=dur,
    )


def test_prefers_fewest_severe_miles():
    scores = [_score("a", severe=50), _score("b", severe=5), _score("c", severe=20)]
    assert R.recommend(scores) == "b"


def test_no_travel_beats_severe():
    scores = [_score("a", notravel=1, severe=0), _score("b", notravel=0, severe=100)]
    assert R.recommend(scores) == "b"


def test_tiebreak_high_then_avg_then_time():
    assert R.recommend([_score("a", high=10), _score("b", high=2)]) == "b"
    assert R.recommend([_score("a", avg=1.5), _score("b", avg=0.5)]) == "b"
    assert R.recommend([_score("a", dur=5000), _score("b", dur=3000)]) == "b"


def test_rank_orders_best_first_and_empty_none():
    ranked = R.rank([_score("a", severe=9), _score("b", severe=1)])
    assert [s.route_id for s in ranked] == ["b", "a"]
    assert R.recommend([]) is None
