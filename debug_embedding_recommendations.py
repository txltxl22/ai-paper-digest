#!/usr/bin/env python3
"""
Debug tool for embedding-based recommendation system.

Usage:
    python debug_embedding_recommendations.py <user_id> [model_name]
    
Examples:
    python debug_embedding_recommendations.py yu
    python debug_embedding_recommendations.py yu all-MiniLM-L6-v2
    python debug_embedding_recommendations.py yu all-mpnet-base-v2
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import numpy as np

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("❌ Error: sentence-transformers not installed.")
    print("   Install with: uv add sentence-transformers")
    sys.exit(1)

from summary_service.recommendations import (
    RecommendationContext,
    RecommendationEngine,
    TagPreferenceStrategy,
)
from summary_service.recommendations.embedding_strategy_example import EmbeddingPreferenceStrategy


def load_user_data(uid: str, user_data_dir: Path) -> Dict[str, Any]:
    """Load user data from JSON file."""
    user_file = user_data_dir / f"{uid}.json"
    if not user_file.exists():
        raise FileNotFoundError(f"User data file not found: {user_file}")
    return json.loads(user_file.read_text())


def load_all_entries(summary_dir: Path) -> List[Dict[str, Any]]:
    """Load all entry metadata from summary directory using Pydantic models."""
    from summary_service.record_manager import load_summary_with_service_record
    
    json_files = [f for f in summary_dir.glob("*.json") if not f.name.endswith('.tags.json')]
    
    entries_meta = []
    for json_file in json_files:
        try:
            arxiv_id = json_file.stem
            
            # Load using Pydantic model
            record = load_summary_with_service_record(arxiv_id, summary_dir)
            if not record:
                continue
            
            # Skip summaries without one_sentence_summary (not fully processed)
            one_sentence_summary = record.summary_data.structured_content.one_sentence_summary
            if not one_sentence_summary or not one_sentence_summary.strip():
                continue
            
            # Extract tags from Tags model
            tags_obj = record.summary_data.tags
            top_tags = [str(t).strip().lower() for t in (tags_obj.top or []) if str(t).strip()]
            detail_tags = [str(t).strip().lower() for t in (tags_obj.tags or []) if str(t).strip()]
            
            # Extract English title and abstract from PaperInfo
            paper_info = record.summary_data.structured_content.paper_info
            title = paper_info.title_en or paper_info.title_zh
            abstract = paper_info.abstract or ''
            
            # Get summary/content - try multiple locations (matching EntryScanner logic)
            # First try markdown_content (full markdown)
            markdown_content = record.summary_data.markdown_content or ''
            # Then try one_sentence_summary from structured_content
            one_sentence = one_sentence_summary or ''
            # Fallback to abstract
            text_content = markdown_content or one_sentence or abstract or ''
            
            # Parse updated time
            updated_str = record.summary_data.updated_at
            if updated_str:
                try:
                    updated = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                except Exception:
                    updated = datetime.fromtimestamp(json_file.stat().st_mtime, tz=timezone.utc)
            else:
                updated = datetime.fromtimestamp(json_file.stat().st_mtime, tz=timezone.utc)
            
            # Parse submission/creation time
            created_str = record.service_data.created_at
            if created_str:
                try:
                    submission_time = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                except Exception:
                    submission_time = updated
            else:
                submission_time = updated
            
            entry = {
                'id': arxiv_id,
                'title': title,
                'summary': text_content,
                'content': text_content,
                'abstract': abstract,
                'top_tags': top_tags,
                'detail_tags': detail_tags,
                'updated': updated,
                'submission_time': submission_time,
            }
            entries_meta.append(entry)
        except Exception as e:
            print(f"Warning: Error loading {json_file}: {e}", file=sys.stderr)
            continue
    
    return entries_meta


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def debug_embedding_recommendations(uid: str, model_name: str = "all-MiniLM-L6-v2"):
    """Debug embedding-based recommendation system for a specific user."""
    # Setup paths
    project_root = Path(__file__).parent
    user_data_dir = project_root / "user_data"
    summary_dir = project_root / "summary"
    
    print_section(f"Embedding Recommendation Debug for User: {uid}")
    print(f"Model: {model_name}")
    
    # Load user data
    print("\nLoading user data...")
    user_data = load_user_data(uid, user_data_dir)
    favorites_map = user_data.get('favorites', {})
    read_map = user_data.get('read', {})
    
    print(f"  Favorites: {len(favorites_map)} papers")
    print(f"  Read: {len(read_map)} papers")
    print(f"  Favorites that are also read: {len(set(favorites_map.keys()) & set(read_map.keys()))}")
    
    # Load all entries
    print("\nLoading entries from summary directory...")
    all_entries_meta = load_all_entries(summary_dir)
    print(f"  Total entries: {len(all_entries_meta)}")
    
    # Debug: Check how many entries have titles
    entries_with_titles = sum(1 for e in all_entries_meta if e.get('title'))
    print(f"  Entries with titles: {entries_with_titles}/{len(all_entries_meta)}")
    if entries_with_titles < len(all_entries_meta):
        # Show a sample entry without title for debugging
        sample_no_title = next((e for e in all_entries_meta if not e.get('title')), None)
        if sample_no_title:
            print(f"  Sample entry without title: {sample_no_title.get('id')}")
    
    # Build favorites_meta and read_meta
    favorites_meta = [e for e in all_entries_meta if e["id"] in favorites_map]
    read_meta = [e for e in all_entries_meta if e["id"] in read_map]
    
    print(f"\n  Favorites in summary: {len(favorites_meta)}")
    print(f"  Read in summary: {len(read_meta)}")
    
    # Build candidate entries (unread)
    read_ids = set(read_map.keys())
    candidate_entries = [e for e in all_entries_meta if e["id"] not in read_ids]
    print(f"  Candidate entries (unread): {len(candidate_entries)}")
    
    if not favorites_meta:
        print("\n❌ No favorite papers found in summary directory. Cannot generate recommendations.")
        return
    
    # Initialize embedding strategy
    print_section("Initializing Embedding Strategy")
    print(f"\nLoading model: {model_name}")
    print("  (This may take a moment on first run as the model downloads...)")
    
    try:
        embedding_strategy = EmbeddingPreferenceStrategy(
            model_name=model_name,
            similarity_threshold=0.3,
        )
        print("  ✅ Model loaded successfully")
    except Exception as e:
        print(f"  ❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Build context
    context = RecommendationContext(
        candidate_entries=candidate_entries,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={'uid': uid},
    )
    
    # Analyze favorite papers and their embeddings
    print_section("Favorite Papers Analysis")
    
    favorite_embeddings = []
    favorite_texts = []
    
    for fav in favorites_meta:
        fav_id = fav['id']
        text = embedding_strategy._text_for_embedding(fav)
        favorite_texts.append((fav_id, text))
        
        try:
            emb = embedding_strategy._get_embedding(fav, use_cache=True)
            favorite_embeddings.append(emb)
            
            print(f"\n  {fav_id}")
            print(f"    Title: {fav.get('title', 'N/A')[:60]}")
            print(f"    Tags: {', '.join((fav.get('top_tags', []) + fav.get('detail_tags', []))[:5])}")
            print(f"    Text length: {len(text)} chars")
            print(f"    Embedding shape: {emb.shape}")
            print(f"    Embedding norm: {np.linalg.norm(emb):.4f}")
        except Exception as e:
            print(f"    ❌ Failed to embed: {e}")
    
    if not favorite_embeddings:
        print("\n❌ No valid favorite embeddings generated!")
        return
    
    # Calculate user preference vector
    print_section("User Preference Vector")
    
    user_preference = np.mean(favorite_embeddings, axis=0)
    user_preference = user_preference / (np.linalg.norm(user_preference) + 1e-8)
    
    print(f"\n  Number of favorite papers: {len(favorite_embeddings)}")
    print(f"  Preference vector shape: {user_preference.shape}")
    print(f"  Preference vector norm: {np.linalg.norm(user_preference):.4f}")
    print(f"  Embedding dimension: {len(user_preference)}")
    
    # Show similarity between favorite papers
    print(f"\n  Similarity between favorite papers:")
    for i, (fav_id1, _) in enumerate(favorite_texts[:5]):
        for j, (fav_id2, _) in enumerate(favorite_texts[:5]):
            if i < j:
                emb1 = favorite_embeddings[i]
                emb1_norm = emb1 / (np.linalg.norm(emb1) + 1e-8)
                emb2 = favorite_embeddings[j]
                emb2_norm = emb2 / (np.linalg.norm(emb2) + 1e-8)
                similarity = float(np.dot(emb1_norm, emb2_norm))
                print(f"    {fav_id1} ↔ {fav_id2}: {similarity:.4f}")
    
    # Score candidate entries
    print_section("Scoring Candidate Entries")
    
    print(f"\n  Scoring {len(candidate_entries)} candidate entries...")
    print("  (This may take a moment...)")
    
    embedding_scores = embedding_strategy.score(context)
    
    print(f"\n  ✅ Scored {len(embedding_scores)} entries above threshold ({embedding_strategy.similarity_threshold})")
    
    # Show embedding strategy profile
    profile = embedding_strategy.profile()
    if profile:
        print(f"\n  Strategy Profile:")
        for key, value in profile.items():
            if isinstance(value, float):
                print(f"    {key}: {value:.4f}")
            else:
                print(f"    {key}: {value}")
    
    # Show top recommendations from embedding strategy
    print_section("Top Embedding-Based Recommendations")
    
    if embedding_scores:
        sorted_scores = sorted(embedding_scores.items(), key=lambda x: x[1].value, reverse=True)
        
        print(f"\n  Top 10 Recommendations:")
        for i, (entry_id, score) in enumerate(sorted_scores[:10], 1):
            entry = next((e for e in candidate_entries if e['id'] == entry_id), None)
            similarity = score.metadata.get('similarity', 0.0)
            
            print(f"\n  {i}. {entry_id}")
            print(f"     Title: {entry.get('title', 'N/A')[:60] if entry else 'N/A'}")
            print(f"     Embedding Score: {score.value:.4f}")
            print(f"     Cosine Similarity: {similarity:.4f}")
            if entry:
                tags = (entry.get('top_tags', []) + entry.get('detail_tags', []))[:5]
                print(f"     Tags: {', '.join(tags)}")
                
                # Show text used for embedding
                text = embedding_strategy._text_for_embedding(entry)
                print(f"     Text preview: {text[:100]}...")
    else:
        print("\n  ❌ No recommendations generated!")
        print(f"     Threshold: {embedding_strategy.similarity_threshold}")
        print(f"     Try lowering the threshold or check if favorites have sufficient content.")
    
    # Compare with tag-based strategy
    print_section("Comparison: Embedding vs Tag-Based")
    
    tag_strategy = TagPreferenceStrategy(min_negative_samples=100)
    tag_scores = tag_strategy.score(context)
    
    print(f"\n  Embedding strategy: {len(embedding_scores)} recommendations")
    print(f"  Tag strategy: {len(tag_scores)} recommendations")
    
    # Find overlap
    embedding_ids = set(embedding_scores.keys())
    tag_ids = set(tag_scores.keys())
    overlap = embedding_ids & tag_ids
    
    print(f"  Overlap: {len(overlap)} papers recommended by both")
    print(f"  Embedding-only: {len(embedding_ids - tag_ids)} papers")
    print(f"  Tag-only: {len(tag_ids - embedding_ids)} papers")
    
    if overlap:
        print(f"\n  Papers recommended by both strategies:")
        for entry_id in list(overlap)[:5]:
            emb_score = embedding_scores[entry_id].value
            tag_score = tag_scores[entry_id].value
            similarity = embedding_scores[entry_id].metadata.get('similarity', 0.0)
            print(f"    {entry_id}: embedding={emb_score:.4f} (sim={similarity:.4f}), tag={tag_score:.4f}")
    
    if embedding_ids - tag_ids:
        print(f"\n  Papers recommended ONLY by embedding strategy (semantic similarity):")
        for entry_id in list(embedding_ids - tag_ids)[:5]:
            entry = next((e for e in candidate_entries if e['id'] == entry_id), None)
            emb_score = embedding_scores[entry_id].value
            similarity = embedding_scores[entry_id].metadata.get('similarity', 0.0)
            print(f"    {entry_id}: score={emb_score:.4f}, similarity={similarity:.4f}")
            if entry:
                print(f"      Title: {entry.get('title', 'N/A')[:60]}")
                print(f"      Tags: {', '.join((entry.get('top_tags', []) + entry.get('detail_tags', []))[:5])}")
    
    # Hybrid engine test
    print_section("Hybrid Engine Test")
    
    print("\n  Testing combined embedding + tag strategies...")
    hybrid_engine = RecommendationEngine(strategies=[tag_strategy, embedding_strategy])
    hybrid_response = hybrid_engine.recommend(context)
    
    print(f"  Hybrid recommendations: {len(hybrid_response.scores)}")
    
    if hybrid_response.scores:
        sorted_hybrid = sorted(hybrid_response.scores.items(), key=lambda x: x[1].score, reverse=True)
        print(f"\n  Top 5 Hybrid Recommendations:")
        for i, (entry_id, score) in enumerate(sorted_hybrid[:5], 1):
            entry = next((e for e in candidate_entries if e['id'] == entry_id), None)
            breakdown = score.breakdown
            print(f"\n  {i}. {entry_id}")
            print(f"     Total Score: {score.score:.4f}")
            print(f"     Breakdown: {breakdown}")
            if entry:
                print(f"     Title: {entry.get('title', 'N/A')[:60]}")
    
    # Summary
    print_section("Summary")
    
    print(f"\n  User: {uid}")
    print(f"  Model: {model_name}")
    print(f"  Favorites in system: {len(favorites_meta)}")
    print(f"  Candidate papers: {len(candidate_entries)}")
    print(f"  Embedding recommendations: {len(embedding_scores)}")
    print(f"  Tag recommendations: {len(tag_scores)}")
    print(f"  Hybrid recommendations: {len(hybrid_response.scores)}")
    
    if embedding_scores:
        similarities = [s.metadata.get('similarity', 0.0) for s in embedding_scores.values()]
        print(f"\n  Similarity statistics:")
        print(f"    Average: {np.mean(similarities):.4f}")
        print(f"    Max: {np.max(similarities):.4f}")
        print(f"    Min: {np.min(similarities):.4f}")
        print(f"    Median: {np.median(similarities):.4f}")
    
    if not embedding_scores:
        print(f"\n  ⚠️  No embedding recommendations because:")
        print(f"     - Similarity threshold: {embedding_strategy.similarity_threshold}")
        print(f"     - Try lowering the threshold or check favorite papers have sufficient content")
        print(f"     - Consider using a different model (e.g., all-mpnet-base-v2 for better quality)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_embedding_recommendations.py <user_id> [model_name]")
        print("Examples:")
        print("  python debug_embedding_recommendations.py yu")
        print("  python debug_embedding_recommendations.py yu all-MiniLM-L6-v2")
        print("  python debug_embedding_recommendations.py yu all-mpnet-base-v2")
        sys.exit(1)
    
    uid = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "all-MiniLM-L6-v2"
    
    try:
        debug_embedding_recommendations(uid, model_name)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

