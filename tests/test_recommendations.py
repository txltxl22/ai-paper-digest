from datetime import datetime, timedelta, timezone

from summary_service.recommendations import (
    RecommendationContext,
    RecommendationEngine,
    RecommendationResponse,
    StrategyScore,
    TagPreferenceStrategy,
)
from summary_service.recommendations.engine import RecommendationScore


def _make_entry(entry_id: str, top=None, detail=None, days_ago: int = 0):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": entry_id,
        "top_tags": top or [],
        "detail_tags": detail or [],
        "updated": ts,
        "submission_time": ts,
    }


def test_tag_preference_strategy_prioritizes_detail_tags():
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", top=["vision"], detail=["diffusion"]),
        _make_entry("fav2", detail=["alignment", "reasoning"], days_ago=3),
    ]
    favorites_map = {
        "fav1": now.isoformat(),
        "fav2": (now - timedelta(days=3)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", top=["vision"]),
        _make_entry("paper-b", detail=["alignment"]),
        _make_entry("paper-c", detail=["other"]),
    ]

    strategy = TagPreferenceStrategy(now=now)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        extra={},
    )
    scores = strategy.score(ctx)

    assert "paper-a" in scores
    assert "paper-b" in scores
    # Detail tags are prioritized over top tags (detail_tag_multiplier=1.5 > top_tag_multiplier=1.0)
    assert scores["paper-b"].value > scores["paper-a"].value
    assert "paper-c" not in scores


def test_engine_combines_multiple_strategies_and_profiles():
    class ConstantStrategy:
        name = "constant"

        def __init__(self, value):
            self.value = value

        def score(self, context: RecommendationContext):
            return {
                entry["id"]: StrategyScore(value=self.value)
                for entry in context.candidate_entries
            }

        def profile(self):
            return {"value": self.value}

    favorites = [_make_entry("fav", top=["llm"])]
    favorites_map = {"fav": datetime.now(timezone.utc).isoformat()}
    candidates = [_make_entry("paper-x", detail=["llm"])]
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites,
        favorites_map=favorites_map,
        extra={},
    )

    engine = RecommendationEngine(
        strategies=[TagPreferenceStrategy(), ConstantStrategy(0.4)]
    )
    response = engine.recommend(ctx)

    assert "paper-x" in response.scores
    score = response.scores["paper-x"]
    assert score.score > 0.4  # Tag strategy added weight
    assert "constant" in score.breakdown
    assert "tag_preference" in response.profiles
    assert "constant" in response.profiles


def test_route_sorting_prefers_recommended_entries():
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    entries = [
        _make_entry("recent", detail=["agent"], days_ago=0),
        _make_entry("older", detail=["agent"], days_ago=2),
        _make_entry("unmatched", detail=["cv"], days_ago=0),
    ]

    scores = {
        "recent": RecommendationScore(score=1.5, matched_tags=["agent"]),
        "older": RecommendationScore(score=0.2, matched_tags=["agent"]),
    }
    response = RecommendationResponse(scores=scores, profiles={})

    annotated = []
    for entry in entries:
        item = dict(entry)
        rec = response.scores.get(item["id"])
        if rec:
            item["recommendation"] = {"score": rec.score}
        else:
            item["recommendation"] = None
        annotated.append(item)

    def sort_key(item):
        rec = item.get("recommendation") or {}
        score = rec.get("score", 0.0)
        has_reco = 0 if score > 0 else 1
        updated_ts = item["updated"].timestamp()
        return (has_reco, -score, -updated_ts)

    annotated.sort(key=sort_key)
    ordered_ids = [item["id"] for item in annotated]

    assert ordered_ids[:2] == ["recent", "older"]
    assert ordered_ids[-1] == "unmatched"

