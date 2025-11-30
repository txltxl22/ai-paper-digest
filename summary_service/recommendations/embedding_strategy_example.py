"""
Example embedding-based recommendation strategy.

This is a reference implementation showing how to add semantic similarity
using local embedding models to complement the tag-based approach.

To use this:
1. Install: uv add sentence-transformers
2. Import and add to RecommendationEngine strategies
3. Combine with TagPreferenceStrategy for hybrid recommendations
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Sequence
from dataclasses import dataclass
import numpy as np
from pathlib import Path

from .engine import RecommendationContext, StrategyScore, RecommendationStrategy

logger = logging.getLogger(__name__)

# Try to import sentence-transformers, but make it optional
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    logger.warning(
        "sentence-transformers not installed. "
        "Install with: uv add sentence-transformers"
    )


class EmbeddingPreferenceStrategy:
    """
    Recommendation strategy using semantic embeddings for similarity.
    
    This strategy:
    1. Embeds user's favorite papers (title + tags)
    2. Embeds candidate papers (title + tags)
    3. Calculates cosine similarity
    4. Returns scores based on similarity to favorites
    
    Best used in combination with TagPreferenceStrategy for hybrid recommendations.
    """

    name = "embedding_preference"

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        cache_dir: Optional[Path] = None,
        similarity_threshold: float = 0.3,
    ):
        """
        Initialize embedding strategy.
        
        Args:
            model_name: HuggingFace model name (e.g., 'all-MiniLM-L6-v2', 'all-mpnet-base-v2')
            cache_dir: Directory to cache embeddings (optional)
            similarity_threshold: Minimum similarity score to include (0.0-1.0)
        """
        if not EMBEDDING_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required. Install with: uv add sentence-transformers"
            )
        
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.similarity_threshold = similarity_threshold
        self._model: Optional[SentenceTransformer] = None
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._profile: Dict[str, Any] = {}

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"Model loaded successfully")
        return self._model

    def _text_for_embedding(self, entry: Dict[str, Any]) -> str:
        """Create text representation of a paper for embedding."""
        parts = []
        
        # Add title if available
        title = entry.get("title") or entry.get("id", "")
        if title:
            parts.append(title)
        
        # Add tags
        top_tags = entry.get("top_tags", [])
        detail_tags = entry.get("detail_tags", [])
        all_tags = top_tags + detail_tags
        if all_tags:
            parts.append(" ".join(all_tags))
        
        # Add summary excerpt if available (first 200 chars)
        summary = entry.get("summary") or entry.get("content", "")
        if summary:
            parts.append(summary[:200])
        
        return " ".join(parts).strip()

    def _get_embedding(self, entry: Dict[str, Any], use_cache: bool = True) -> np.ndarray:
        """Get embedding for an entry, with optional caching."""
        entry_id = entry.get("id")
        if not entry_id:
            # Generate a temporary ID for caching
            entry_id = hash(self._text_for_embedding(entry))
        
        if use_cache and entry_id in self._embedding_cache:
            return self._embedding_cache[entry_id]
        
        text = self._text_for_embedding(entry)
        embedding = self.model.encode(text, show_progress_bar=False, convert_to_numpy=True)
        
        if use_cache:
            self._embedding_cache[entry_id] = embedding
        
        return embedding

    def score(self, context: RecommendationContext) -> Dict[str, StrategyScore]:
        """Score candidate entries based on embedding similarity to favorites."""
        if not context.favorites_meta:
            self._profile = {"message": "No favorites available"}
            return {}
        
        # Get embeddings for favorite papers
        favorite_embeddings = []
        for fav in context.favorites_meta:
            try:
                emb = self._get_embedding(fav)
                favorite_embeddings.append(emb)
            except Exception as e:
                logger.warning(f"Failed to embed favorite {fav.get('id')}: {e}")
                continue
        
        if not favorite_embeddings:
            self._profile = {"message": "No valid favorite embeddings"}
            return {}
        
        # Average favorite embeddings to create a "user preference vector"
        # Alternative: could use max similarity instead of average
        user_preference = np.mean(favorite_embeddings, axis=0)
        user_preference = user_preference / (np.linalg.norm(user_preference) + 1e-8)  # Normalize
        
        # Score candidate entries
        scores: Dict[str, StrategyScore] = {}
        similarities = []
        
        for entry in context.candidate_entries:
            entry_id = entry.get("id")
            if not entry_id:
                continue
            
            try:
                entry_embedding = self._get_embedding(entry)
                entry_embedding = entry_embedding / (np.linalg.norm(entry_embedding) + 1e-8)  # Normalize
                
                # Cosine similarity
                similarity = float(np.dot(user_preference, entry_embedding))
                similarities.append(similarity)
                
                if similarity < self.similarity_threshold:
                    continue
                
                # Scale similarity to 0-1 range (cosine similarity is already -1 to 1)
                # Shift to 0-1: (similarity + 1) / 2, then scale up
                normalized_score = (similarity + 1) / 2
                
                scores[entry_id] = StrategyScore(
                    value=normalized_score,
                    matched_tags=[],  # Embeddings don't provide tag-level matches
                    metadata={
                        "similarity": similarity,
                        "model": self.model_name,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to score entry {entry_id}: {e}")
                continue
        
        # Profile information
        if similarities:
            self._profile = {
                "model": self.model_name,
                "favorites_count": len(favorite_embeddings),
                "candidates_scored": len(scores),
                "avg_similarity": float(np.mean(similarities)),
                "max_similarity": float(np.max(similarities)),
                "min_similarity": float(np.min(similarities)),
            }
        else:
            self._profile = {"message": "No similarities calculated"}
        
        return scores

    def profile(self) -> Optional[Dict[str, Any]]:
        """Return profiling information about the strategy."""
        return self._profile


# Example usage in index_page/routes.py:
#
# from summary_service.recommendations.embedding_strategy_example import EmbeddingPreferenceStrategy
# from summary_service.recommendations.engine import RecommendationEngine, TagPreferenceStrategy
#
# # Create hybrid engine
# tag_strategy = TagPreferenceStrategy(now=now)
# embedding_strategy = EmbeddingPreferenceStrategy(model_name="all-MiniLM-L6-v2")
# engine = RecommendationEngine(strategies=[tag_strategy, embedding_strategy])
#
# # The engine will combine scores from both strategies

