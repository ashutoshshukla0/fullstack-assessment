"""Route ranking: fewest No-Travel miles, then fewest Severe miles, then
fewest High miles, then lowest average risk, then shortest travel time.
"""

from dataclasses import dataclass

# Quantize mileage tiebreaks to displayed precision so float noise cannot
# decide a ranking.
RANK_MILES_PRECISION = 1


@dataclass(frozen=True)
class RouteScore:
    route_id: str
    no_travel_miles: float
    severe_miles: float
    high_miles: float
    avg_risk: float
    duration_s: float


class RouteRecommender:
    """Stateless ranking over precomputed per-route scores."""

    @staticmethod
    def sort_key(score: RouteScore) -> tuple[float, float, float, float, float]:
        return (
            round(score.no_travel_miles, RANK_MILES_PRECISION),
            round(score.severe_miles, RANK_MILES_PRECISION),
            round(score.high_miles, RANK_MILES_PRECISION),
            round(score.avg_risk, 2),
            score.duration_s,
        )

    def recommend(self, scores: list[RouteScore]) -> str | None:
        """Return the winning route_id, None when empty or all impassable."""
        if not scores:
            return None
        if all(s.no_travel_miles > 0 for s in scores):
            return None
        return min(scores, key=self.sort_key).route_id

    def rank(self, scores: list[RouteScore]) -> list[RouteScore]:
        """Scores ordered best-first (stable for equal keys)."""
        return sorted(scores, key=self.sort_key)
