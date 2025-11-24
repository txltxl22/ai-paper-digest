"""
Reusable recommendation engine primitives.

This module intentionally lives inside summary_service/ so it can be shared by
the web application, RSS batch jobs, or any future CLI tooling without
introducing Flask dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple, Any
import math


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RecommendationContext:
    """Context block passed to recommendation strategies."""

    candidate_entries: Sequence[Dict[str, Any]]
    favorites_meta: Sequence[Dict[str, Any]]
    favorites_map: Dict[str, Optional[str]]
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyScore:
    """Per-strategy score for a single entry."""

    value: float
    matched_tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RecommendationScore:
    """Aggregated score information returned to callers."""

    score: float
    matched_tags: List[str] = field(default_factory=list)
    breakdown: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RecommendationResponse:
    """Container for engine output."""

    scores: Dict[str, RecommendationScore]
    profiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RecommendationStrategy(Protocol):
    """Interface for plug-and-play recommendation strategies."""

    name: str

    def score(self, context: RecommendationContext) -> Dict[str, StrategyScore]:
        """Return per-entry strategy scores."""

    def profile(self) -> Optional[Dict[str, Any]]:
        """Optional: expose strategy-specific profile info (e.g., tag weights)."""
        return None


class RecommendationEngine:
    """Aggregates multiple strategies and returns sortable scores."""

    def __init__(self, strategies: Sequence[RecommendationStrategy]):
        if not strategies:
            raise ValueError("At least one recommendation strategy is required.")
        self.strategies = list(strategies)

    def recommend(self, context: RecommendationContext) -> RecommendationResponse:
        aggregated: Dict[str, RecommendationScore] = {}

        for strategy in self.strategies:
            partial_scores = strategy.score(context)
            for entry_id, strategy_score in partial_scores.items():
                if strategy_score.value <= 0:
                    continue
                current = aggregated.setdefault(
                    entry_id,
                    RecommendationScore(
                        score=0.0,
                        matched_tags=[],
                        breakdown={},
                        metadata={},
                    ),
                )
                current.score += strategy_score.value
                current.breakdown[strategy.name] = (
                    current.breakdown.get(strategy.name, 0.0) + strategy_score.value
                )
                current.matched_tags = _merge_ranked_tags(
                    current.matched_tags, strategy_score.matched_tags
                )
                if strategy_score.metadata:
                    current.metadata[strategy.name] = strategy_score.metadata

        profiles = {
            strategy.name: profile
            for strategy in self.strategies
            if (profile := strategy.profile()) is not None
        }

        return RecommendationResponse(scores=aggregated, profiles=profiles)


# ---------------------------------------------------------------------------
# Tag preference strategy
# ---------------------------------------------------------------------------


class TagPreferenceStrategy:
    """Ranks entries based on overlap with the user's favorite tag profile."""

    name = "tag_preference"

    def __init__(
        self,
        now: Optional[datetime] = None,
        recency_half_life_days: int = 21,
        top_tag_multiplier: float = 1.0,
        detail_tag_multiplier: float = 1.5,
    ):
        self.now = now or datetime.now(timezone.utc)
        self.recency_half_life_days = max(1, recency_half_life_days)
        self.top_tag_multiplier = top_tag_multiplier
        self.detail_tag_multiplier = detail_tag_multiplier
        self._profile: Dict[str, Any] = {}

    def score(self, context: RecommendationContext) -> Dict[str, StrategyScore]:
        favorites = list(context.favorites_meta or [])
        if not favorites:
            self._profile = {"top_tags": [], "tag_weights": {}}
            return {}

        tag_weights = self._build_tag_weights(
            favorites=favorites, favorites_map=context.favorites_map
        )
        if not tag_weights:
            self._profile = {"top_tags": [], "tag_weights": {}}
            return {}

        ordered_tags = sorted(tag_weights.items(), key=lambda item: item[1], reverse=True)
        self._profile = {
            "top_tags": [tag for tag, _ in ordered_tags[:8]],
            "tag_weights": tag_weights,
        }

        total_preference = sum(tag_weights.values()) or 1.0
        k = 1 / math.log2(total_preference + 1.5)  # dampen large users

        scores: Dict[str, StrategyScore] = {}
        for entry in context.candidate_entries:
            entry_id = entry.get("id")
            if not entry_id:
                continue
            entry_tags = _extract_entry_tags(entry)
            if not entry_tags:
                continue

            matched: List[Tuple[str, float]] = []
            score_value = 0.0
            for tag, tag_meta in entry_tags:
                weight = tag_weights.get(tag)
                if weight is None:
                    continue
                boosted = weight * (self.top_tag_multiplier if tag_meta["is_top"] else self.detail_tag_multiplier)
                score_value += boosted
                matched.append((tag, boosted))

            if score_value <= 0:
                continue

            normalized_score = score_value * k
            matched_sorted = [tag for tag, _ in sorted(matched, key=lambda item: item[1], reverse=True)]
            scores[entry_id] = StrategyScore(
                value=normalized_score,
                matched_tags=matched_sorted,
                metadata={
                    "raw_score": score_value,
                    "matched_count": len(matched_sorted),
                },
            )

        return scores

    def profile(self) -> Optional[Dict[str, Any]]:
        return self._profile

    # Internals ----------------------------------------------------------------

    def _build_tag_weights(
        self,
        favorites: Sequence[Dict[str, Any]],
        favorites_map: Dict[str, Optional[str]],
    ) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        for meta in favorites:
            entry_id = meta.get("id")
            if not entry_id:
                continue
            recency = self._recency_weight(favorites_map.get(entry_id))
            top_tags = meta.get("top_tags") or []
            detail_tags = meta.get("detail_tags") or []

            for tag in top_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                weights[normalized] = weights.get(normalized, 0.0) + recency * self.top_tag_multiplier

            for tag in detail_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                weights[normalized] = weights.get(normalized, 0.0) + recency * self.detail_tag_multiplier

        return weights

    def _recency_weight(self, timestamp_str: Optional[str]) -> float:
        if not timestamp_str:
            return 1.0
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            return 1.0

        delta_days = max((self.now - ts).days, 0)
        # Exponential decay so older favorites still count but less strongly.
        return math.exp(-math.log(2) * (delta_days / self.recency_half_life_days)) + 0.5


# ---------------------------------------------------------------------------
# Helpers & defaults
# ---------------------------------------------------------------------------


def _normalize_tag(tag: Optional[str]) -> Optional[str]:
    if not isinstance(tag, str):
        return None
    clean = tag.strip().lower()
    return clean or None


def _extract_entry_tags(entry: Dict[str, Any]) -> List[Tuple[str, Dict[str, bool]]]:
    tags: List[Tuple[str, Dict[str, bool]]] = []
    seen = set()

    for tag in entry.get("top_tags") or []:
        normalized = _normalize_tag(tag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tags.append((normalized, {"is_top": True}))

    for tag in entry.get("detail_tags") or []:
        normalized = _normalize_tag(tag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tags.append((normalized, {"is_top": False}))

    return tags


def _merge_ranked_tags(existing: List[str], new: List[str], limit: int = 12) -> List[str]:
    combined = existing[:]
    seen = set(combined)
    for tag in new:
        if tag not in seen:
            combined.append(tag)
            seen.add(tag)
        if len(combined) >= limit:
            break
    return combined


def build_default_engine() -> RecommendationEngine:
    """Factory for the default engine used by the web index."""
    return RecommendationEngine(strategies=[TagPreferenceStrategy()])

