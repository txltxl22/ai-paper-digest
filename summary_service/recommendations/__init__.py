"""
Recommendation engine package for personalized paper ordering.

Provides a pluggable engine that can be reused by the web layer,
RSS services, or any future batch jobs without creating Flask dependencies.
"""

from .engine import (
    RecommendationContext,
    RecommendationEngine,
    RecommendationResponse,
    RecommendationScore,
    RecommendationStrategy,
    StrategyScore,
    TagPreferenceStrategy,
    build_default_engine,
)

__all__ = [
    "RecommendationContext",
    "RecommendationEngine",
    "RecommendationResponse",
    "RecommendationScore",
    "RecommendationStrategy",
    "StrategyScore",
    "TagPreferenceStrategy",
    "build_default_engine",
]

