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
    read_meta: Sequence[Dict[str, Any]] = field(default_factory=list)
    read_map: Dict[str, Optional[str]] = field(default_factory=dict)
    deep_read_meta: Sequence[Dict[str, Any]] = field(default_factory=list)
    deep_read_map: Dict[str, Optional[str]] = field(default_factory=dict)
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
    """Ranks entries based on overlap with user's tag preferences using multiple signals.
    
    Signal sources (each tracked separately for debugging/tuning):
    - favorites: Explicit positive signal (strongest)
    - deep_read: Strong interest signal - user requested full paper analysis
    - read: Implicit negative signal (only with sufficient samples)
    """

    name = "tag_preference"

    def __init__(
        self,
        now: Optional[datetime] = None,
        recency_half_life_days: int = 21,
        top_tag_multiplier: float = 1.0,
        detail_tag_multiplier: float = 1.5,
        deep_read_multiplier: float = 2.5,  # deep_read signal weight relative to favorites
        min_negative_samples: int = 200,  # now the read list can not be taken as negative signal.
    ):
        self.now = now or datetime.now(timezone.utc)
        self.recency_half_life_days = max(1, recency_half_life_days)
        self.top_tag_multiplier = top_tag_multiplier
        self.detail_tag_multiplier = detail_tag_multiplier
        self.deep_read_multiplier = deep_read_multiplier
        self.min_negative_samples = max(1, min_negative_samples)
        self._profile: Dict[str, Any] = {}

    def score(self, context: RecommendationContext) -> Dict[str, StrategyScore]:
        favorites = list(context.favorites_meta or [])
        reads = list(context.read_meta or [])
        deep_reads = list(context.deep_read_meta or [])
        
        # Build tag weights from each source separately (for debugging/tuning)
        favorites_weights = self._build_positive_tag_weights(
            favorites=favorites, favorites_map=context.favorites_map
        )
        deep_read_weights = self._build_deep_read_tag_weights(
            deep_reads=deep_reads, 
            deep_read_map=context.deep_read_map,
        )
        negative_weights = self._build_negative_tag_weights(
            reads=reads, read_map=context.read_map, favorites_map=context.favorites_map
        )
        
        # Calculate net weights: favorites + deep_read - negative
        # Each source is tracked separately for transparency
        net_weights: Dict[str, float] = {}
        all_tags = set(favorites_weights.keys()) | set(deep_read_weights.keys()) | set(negative_weights.keys())
        for tag in all_tags:
            fav_w = favorites_weights.get(tag, 0.0)
            deep_w = deep_read_weights.get(tag, 0.0)
            neg_w = negative_weights.get(tag, 0.0)
            net_weights[tag] = fav_w + deep_w - neg_w
        
        if not net_weights or all(w <= 0 for w in net_weights.values()):
            self._profile = {
                "top_tags": [],
                "favorites_tag_weights": favorites_weights,
                "deep_read_tag_weights": deep_read_weights,
                "negative_tag_weights": negative_weights,
                "net_tag_weights": net_weights,
            }
            return {}

        ordered_tags = sorted(net_weights.items(), key=lambda item: item[1], reverse=True)
        self._profile = {
            "top_tags": [tag for tag, _ in ordered_tags[:8] if net_weights[tag] > 0],
            "favorites_tag_weights": favorites_weights,
            "deep_read_tag_weights": deep_read_weights,
            "negative_tag_weights": negative_weights,
            "net_tag_weights": net_weights,
        }

        total_preference = sum(w for w in net_weights.values() if w > 0) or 1.0
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
                net_weight = net_weights.get(tag)
                if net_weight is None:
                    continue
                # Include both positive and negative net weights
                # Negative weights will reduce the score
                boosted = net_weight * (self.top_tag_multiplier if tag_meta["is_top"] else self.detail_tag_multiplier)
                score_value += boosted
                if net_weight > 0:  # Only track positive matches for metadata
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

    def _build_positive_tag_weights(
        self,
        favorites: Sequence[Dict[str, Any]],
        favorites_map: Dict[str, Optional[str]],
    ) -> Dict[str, float]:
        """Build positive tag weights from favorites with recency weighting."""
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

    def _build_deep_read_tag_weights(
        self,
        deep_reads: Sequence[Dict[str, Any]],
        deep_read_map: Dict[str, Optional[str]],
    ) -> Dict[str, float]:
        """Build tag weights from deep read papers with recency weighting.
        
        Deep read indicates strong interest - user explicitly requested full paper analysis.
        Excludes papers already in favorites (already counted in favorites_weights).
        
        Weight formula: recency * tag_multiplier * deep_read_multiplier
        """
        weights: Dict[str, float] = {}
        for meta in deep_reads:
            entry_id = meta.get("id")
            if not entry_id:
                continue

            recency = self._recency_weight(deep_read_map.get(entry_id))
            top_tags = meta.get("top_tags") or []
            detail_tags = meta.get("detail_tags") or []

            for tag in top_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                weights[normalized] = weights.get(normalized, 0.0) + recency * self.top_tag_multiplier * self.deep_read_multiplier

            for tag in detail_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                weights[normalized] = weights.get(normalized, 0.0) + recency * self.detail_tag_multiplier * self.deep_read_multiplier

        return weights

    def _build_negative_tag_weights(
        self,
        reads: Sequence[Dict[str, Any]],
        read_map: Dict[str, Optional[str]],
        favorites_map: Dict[str, Optional[str]],
    ) -> Dict[str, float]:
        """Build negative tag weights from read list with recency weighting and minimum samples check.
        
        Excludes favorite papers from negative weights since favorites are explicit positive signals.
        """
        # First pass: count occurrences and build raw weights
        # Exclude papers that are also favorites (they're positive signals, not negative)
        raw_weights: Dict[str, float] = {}
        tag_counts: Dict[str, int] = {}
        
        for meta in reads:
            entry_id = meta.get("id")
            if not entry_id:
                continue
            # Skip if this paper is also a favorite (favorites are positive signals)
            if entry_id in favorites_map:
                continue
                
            recency = self._recency_weight(read_map.get(entry_id))
            top_tags = meta.get("top_tags") or []
            detail_tags = meta.get("detail_tags") or []

            for tag in top_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                raw_weights[normalized] = raw_weights.get(normalized, 0.0) + recency * self.top_tag_multiplier
                tag_counts[normalized] = tag_counts.get(normalized, 0) + 1

            for tag in detail_tags:
                normalized = _normalize_tag(tag)
                if not normalized:
                    continue
                raw_weights[normalized] = raw_weights.get(normalized, 0.0) + recency * self.detail_tag_multiplier
                tag_counts[normalized] = tag_counts.get(normalized, 0) + 1

        # Second pass: only include tags that meet minimum sample threshold
        weights: Dict[str, float] = {}
        for tag, weight in raw_weights.items():
            if tag_counts.get(tag, 0) >= self.min_negative_samples:
                weights[tag] = weight

        return weights

    def _recency_weight(self, timestamp_str: Optional[str]) -> float:
        """Calculate recency weight using exponential decay."""
        if not timestamp_str:
            return 1.0
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except ValueError:
            return 1.0

        delta_days = max((self.now - ts).days, 0)
        # Exponential decay so older signals still count but less strongly.
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

