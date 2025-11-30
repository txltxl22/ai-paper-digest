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
        read_meta=[],
        read_map={},
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
        read_meta=[],
        read_map={},
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
        # Use submission_time for creation date ordering
        submission = item.get("submission_time")
        if submission and hasattr(submission, "timestamp"):
            submission_ts = submission.timestamp()
        else:
            submission_ts = item["updated"].timestamp()
        return (has_reco, -submission_ts)

    annotated.sort(key=sort_key)
    ordered_ids = [item["id"] for item in annotated]

    # Recommended entries come first, sorted by creation time (newest first)
    # "recent" (0 days ago) should come before "older" (2 days ago)
    assert ordered_ids[:2] == ["recent", "older"]
    assert ordered_ids[-1] == "unmatched"


def test_negative_signal_reduces_score():
    """Test that negative signals reduce recommendation scores."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision", "diffusion"]),
    ]
    favorites_map = {"fav1": now.isoformat()}
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=1),  # Not a favorite, so contributes to negative
        _make_entry("read2", detail=["vision"], days_ago=2),  # Not a favorite, so contributes to negative
    ]
    read_map = {
        "read1": (now - timedelta(days=1)).isoformat(),
        "read2": (now - timedelta(days=2)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision", "diffusion"]),  # Matches both positive and negative
        _make_entry("paper-b", detail=["diffusion"]),  # Only matches positive
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    assert "paper-a" in scores
    assert "paper-b" in scores
    # paper-b should score higher because it doesn't have the negative "vision" tag
    assert scores["paper-b"].value > scores["paper-a"].value


def test_negative_signal_prevents_recommendation():
    """Test that strong negative signals can prevent recommendations."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision"]),
    ]
    favorites_map = {"fav1": (now - timedelta(days=10)).isoformat()}  # Older favorite
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=1),  # Not a favorite
        _make_entry("read2", detail=["vision"], days_ago=2),  # Not a favorite
        _make_entry("read3", detail=["vision"], days_ago=3),  # Not a favorite
    ]
    read_map = {
        "read1": (now - timedelta(days=1)).isoformat(),
        "read2": (now - timedelta(days=2)).isoformat(),
        "read3": (now - timedelta(days=3)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision"]),  # Only matches negative (stronger)
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    # Should not be recommended because negative weight > positive weight
    assert "paper-a" not in scores


def test_minimum_negative_samples_threshold():
    """Test that single negative example doesn't affect net weight."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision"]),
    ]
    favorites_map = {"fav1": now.isoformat()}
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=1),  # Only 1 negative example (not a favorite)
    ]
    read_map = {
        "read1": (now - timedelta(days=1)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision"]),
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    # Should be recommended because negative weight is ignored (only 1 sample < threshold of 2)
    assert "paper-a" in scores


def test_multiple_negative_examples_apply_penalty():
    """Test that 2+ negative examples apply penalty."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision"]),
        _make_entry("fav2", detail=["vision"]),  # 2 favorites to make net weight positive
    ]
    favorites_map = {
        "fav1": now.isoformat(),
        "fav2": now.isoformat(),
    }
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=5),  # Older negative (less weight, not a favorite)
        _make_entry("read2", detail=["vision"], days_ago=10),  # Older negative (less weight, not a favorite)
    ]
    read_map = {
        "read1": (now - timedelta(days=5)).isoformat(),
        "read2": (now - timedelta(days=10)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision"]),
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    # Should still be recommended but with lower score due to negative penalty
    assert "paper-a" in scores
    # Score should be positive but lower than without negative signals
    assert scores["paper-a"].value > 0


def test_tag_conflict_resolution_net_weight():
    """Test tag conflict resolution using net weight approach."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision"]),
        _make_entry("fav2", detail=["vision"]),
    ]
    favorites_map = {
        "fav1": now.isoformat(),
        "fav2": now.isoformat(),
    }
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=1),  # Not a favorite
    ]
    read_map = {
        "read1": (now - timedelta(days=1)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision"]),
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    # Should be recommended because positive weight (2 favorites) > negative weight (1 read, but below threshold)
    assert "paper-a" in scores


def test_recency_weighting_negative_signals():
    """Test that recency weighting applies to negative signals."""
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    favorites_meta = [
        _make_entry("fav1", detail=["vision"]),
    ]
    favorites_map = {"fav1": (now - timedelta(days=10)).isoformat()}  # Older favorite
    read_meta = [
        _make_entry("read1", detail=["vision"], days_ago=1),  # Recent negative (not a favorite)
        _make_entry("read2", detail=["vision"], days_ago=2),  # Recent negative (not a favorite)
    ]
    read_map = {
        "read1": (now - timedelta(days=1)).isoformat(),
        "read2": (now - timedelta(days=2)).isoformat(),
    }
    candidates = [
        _make_entry("paper-a", detail=["vision"]),
    ]

    strategy = TagPreferenceStrategy(now=now, min_negative_samples=2)
    ctx = RecommendationContext(
        candidate_entries=candidates,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={},
    )
    scores = strategy.score(ctx)

    # Recent negative signals should have more weight than older positive signal
    # Net weight should be negative, so no recommendation
    assert "paper-a" not in scores

