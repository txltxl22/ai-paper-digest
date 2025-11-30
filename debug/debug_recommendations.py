#!/usr/bin/env python3
"""
Debug tool for recommendation system.

Usage:
    python debug/debug_recommendations.py <user_id>
    
Example:
    python debug/debug_recommendations.py yu
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from summary_service.recommendations import (
    RecommendationContext,
    RecommendationEngine,
    TagPreferenceStrategy,
)


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


def print_tag_weights(title: str, weights: Dict[str, float], limit: int = 20):
    """Print tag weights in a formatted way."""
    print(f"\n{title}:")
    if not weights:
        print("  (empty)")
        return
    
    sorted_tags = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    for tag, weight in sorted_tags[:limit]:
        print(f"  {tag:30s} {weight:8.4f}")
    if len(sorted_tags) > limit:
        print(f"  ... and {len(sorted_tags) - limit} more tags")


def debug_recommendations(uid: str):
    """Debug recommendation system for a specific user."""
    # Setup paths
    project_root = Path(__file__).parent.parent
    user_data_dir = project_root / "user_data"
    summary_dir = project_root / "summary"
    
    print_section(f"Recommendation Debug for User: {uid}")
    
    # Load user data
    print("\nLoading user data...")
    user_data = load_user_data(uid, user_data_dir)
    favorites_map = user_data.get('favorites', {})
    read_map = user_data.get('read', {})
    
    print(f"  Favorites: {len(favorites_map)} papers")
    print(f"  Read: {len(read_map)} papers")
    print(f"  Favorites that are also read: {len(set(favorites_map.keys()) & set(read_map.keys()))}")
    
    # Debug: Show sample favorites_map entries
    if favorites_map:
        print(f"\n  Sample favorites_map entries (first 3):")
        for i, (paper_id, timestamp) in enumerate(list(favorites_map.items())[:3]):
            print(f"    {paper_id}: {timestamp}")
    
    # Load all entries
    print("\nLoading entries from summary directory...")
    all_entries_meta = load_all_entries(summary_dir)
    print(f"  Total entries: {len(all_entries_meta)}")
    
    # Build favorites_meta and read_meta
    favorites_meta = [e for e in all_entries_meta if e["id"] in favorites_map]
    read_meta = [e for e in all_entries_meta if e["id"] in read_map]
    
    print(f"\n  Favorites in summary: {len(favorites_meta)}")
    print(f"  Read in summary: {len(read_meta)}")
    
    # Debug: Check which favorites are missing from summary
    favorites_in_map = set(favorites_map.keys())
    favorites_in_summary = {e["id"] for e in favorites_meta}
    missing_from_summary = favorites_in_map - favorites_in_summary
    if missing_from_summary:
        print(f"  ⚠️  {len(missing_from_summary)} favorites not found in summary directory (will use default recency=1.0)")
        print(f"      Missing IDs: {list(missing_from_summary)[:5]}{'...' if len(missing_from_summary) > 5 else ''}")
    
    # Build candidate entries (unread)
    read_ids = set(read_map.keys())
    candidate_entries = [e for e in all_entries_meta if e["id"] not in read_ids]
    print(f"  Candidate entries (unread): {len(candidate_entries)}")
    
    if not favorites_meta:
        print("\n❌ No favorite papers found in summary directory. Cannot generate recommendations.")
        return
    
    # Create strategy and engine
    strategy = TagPreferenceStrategy(min_negative_samples=100)
    engine = RecommendationEngine(strategies=[strategy])
    
    # Build context
    context = RecommendationContext(
        candidate_entries=candidate_entries,
        favorites_meta=favorites_meta,
        favorites_map=favorites_map,
        read_meta=read_meta,
        read_map=read_map,
        extra={'uid': uid},
    )
    
    # Calculate weights manually for debugging
    print_section("Tag Weight Calculation")
    
    # Show recency calculation parameters
    print(f"\nRecency Calculation Parameters:")
    print(f"  Half-life: {strategy.recency_half_life_days} days")
    print(f"  Current time: {strategy.now.isoformat()}")
    print(f"  Formula: exp(-ln(2) * (delta_days / {strategy.recency_half_life_days})) + 0.5")
    print(f"  Top tag multiplier: {strategy.top_tag_multiplier}")
    print(f"  Detail tag multiplier: {strategy.detail_tag_multiplier}")
    print(f"  Min negative samples: {strategy.min_negative_samples}")
    
    # Show recency calculations for favorites
    print_section("Recency Weight Calculation for Favorites")
    print(f"\nCalculating recency weights for {len(favorites_meta)} favorite papers:")
    print(f"Debug: favorites_map has {len(favorites_map)} entries")
    favorite_recency_details = []
    for fav in favorites_meta:
        fav_id = fav['id']
        timestamp_str = favorites_map.get(fav_id)
        if timestamp_str:
            try:
                # Handle both 'Z' format and '+08:00' format
                if timestamp_str.endswith('Z'):
                    ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    ts = datetime.fromisoformat(timestamp_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                # Convert to UTC for comparison
                if ts.tzinfo != timezone.utc:
                    ts = ts.astimezone(timezone.utc)
                delta_days = max((strategy.now - ts).days, 0)
                recency = math.exp(-math.log(2) * (delta_days / strategy.recency_half_life_days)) + 0.5
                favorite_recency_details.append((fav_id, ts, delta_days, recency, timestamp_str))
            except Exception as e:
                print(f"  DEBUG: Error parsing timestamp for {fav_id}: {timestamp_str} - {e}", file=sys.stderr)
                favorite_recency_details.append((fav_id, None, None, 1.0, timestamp_str))
        else:
            print(f"  DEBUG: No timestamp found for {fav_id} in favorites_map", file=sys.stderr)
            favorite_recency_details.append((fav_id, None, None, 1.0, None))
    
    for fav_id, ts, delta_days, recency, orig_timestamp in favorite_recency_details[:10]:
        if ts:
            print(f"  {fav_id}: timestamp={orig_timestamp} -> {ts.isoformat()}, delta={delta_days} days, recency_weight={recency:.4f}")
        else:
            print(f"  {fav_id}: timestamp={orig_timestamp or 'N/A'}, recency_weight={recency:.4f} (default/error)")
    if len(favorite_recency_details) > 10:
        print(f"  ... and {len(favorite_recency_details) - 10} more favorites")
    
    # Show recency calculations for read papers (excluding favorites)
    read_for_negative = [e for e in read_meta if e['id'] not in favorites_map]
    if read_for_negative:
        print_section("Recency Weight Calculation for Read Papers (Negative Signals)")
        print(f"\nCalculating recency weights for {len(read_for_negative)} read papers (excluding favorites):")
        read_recency_details = []
        for read_entry in read_for_negative:
            read_id = read_entry['id']
            timestamp_str = read_map.get(read_id)
            if timestamp_str:
                try:
                    # Handle both 'Z' format and '+08:00' format
                    if timestamp_str.endswith('Z'):
                        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        ts = datetime.fromisoformat(timestamp_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    # Convert to UTC for comparison
                    if ts.tzinfo != timezone.utc:
                        ts = ts.astimezone(timezone.utc)
                    delta_days = max((strategy.now - ts).days, 0)
                    recency = math.exp(-math.log(2) * (delta_days / strategy.recency_half_life_days)) + 0.5
                    read_recency_details.append((read_id, ts, delta_days, recency, timestamp_str))
                except Exception as e:
                    print(f"  DEBUG: Error parsing timestamp for {read_id}: {timestamp_str} - {e}", file=sys.stderr)
                    read_recency_details.append((read_id, None, None, 1.0, timestamp_str))
            else:
                read_recency_details.append((read_id, None, None, 1.0, None))
        
        for read_id, ts, delta_days, recency, orig_timestamp in read_recency_details[:10]:
            if ts:
                print(f"  {read_id}: timestamp={orig_timestamp} -> {ts.isoformat()}, delta={delta_days} days, recency_weight={recency:.4f}")
            else:
                print(f"  {read_id}: timestamp={orig_timestamp or 'N/A'}, recency_weight={recency:.4f} (default/error)")
        if len(read_recency_details) > 10:
            print(f"  ... and {len(read_recency_details) - 10} more read papers")
    
    # Calculate weights
    positive_weights = strategy._build_positive_tag_weights(favorites_meta, favorites_map)
    negative_weights = strategy._build_negative_tag_weights(read_meta, read_map, favorites_map)
    
    # Show detailed tag weight breakdown for top tags
    print_section("Detailed Tag Weight Breakdown")
    
    # Show how positive weights are calculated for top tags
    print(f"\nPositive Tag Weight Calculation (showing top 5 tags):")
    sorted_positive = sorted(positive_weights.items(), key=lambda x: x[1], reverse=True)
    for tag, total_weight in sorted_positive[:5]:
        print(f"\n  Tag: {tag}")
        print(f"    Total weight: {total_weight:.4f}")
        print(f"    Contributions from favorite papers:")
        contributions = []
        for fav in favorites_meta:
            fav_id = fav['id']
            timestamp_str = favorites_map.get(fav_id)
            recency = 1.0
            if timestamp_str:
                try:
                    # Handle both 'Z' format and '+08:00' format
                    if timestamp_str.endswith('Z'):
                        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        ts = datetime.fromisoformat(timestamp_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    # Convert to UTC for comparison
                    if ts.tzinfo != timezone.utc:
                        ts = ts.astimezone(timezone.utc)
                    delta_days = max((strategy.now - ts).days, 0)
                    recency = math.exp(-math.log(2) * (delta_days / strategy.recency_half_life_days)) + 0.5
                except Exception:
                    pass
            
            top_tags = fav.get('top_tags', [])
            detail_tags = fav.get('detail_tags', [])
            normalized_tag = tag.lower().strip()
            
            if normalized_tag in [t.lower().strip() for t in top_tags]:
                multiplier = strategy.top_tag_multiplier
                contribution = recency * multiplier
                contributions.append((fav_id, 'top', recency, multiplier, contribution))
            elif normalized_tag in [t.lower().strip() for t in detail_tags]:
                multiplier = strategy.detail_tag_multiplier
                contribution = recency * multiplier
                contributions.append((fav_id, 'detail', recency, multiplier, contribution))
        
        for fav_id, tag_type, rec, mult, contrib in contributions[:5]:
            print(f"      {fav_id} ({tag_type}): recency={rec:.4f} × multiplier={mult} = {contrib:.4f}")
        if len(contributions) > 5:
            print(f"      ... and {len(contributions) - 5} more contributions")
    
    print_tag_weights("Positive Tag Weights (from favorites)", positive_weights)
    print_tag_weights("Negative Tag Weights (from read, excluding favorites)", negative_weights)
    
    # Calculate net weights
    net_weights: Dict[str, float] = {}
    all_tags = set(positive_weights.keys()) | set(negative_weights.keys())
    for tag in all_tags:
        positive = positive_weights.get(tag, 0.0)
        negative = negative_weights.get(tag, 0.0)
        net_weights[tag] = positive - negative
    
    print_tag_weights("Net Tag Weights (positive - negative)", net_weights)
    
    # Show conflicts
    conflicts = {tag: (positive_weights.get(tag, 0), negative_weights.get(tag, 0)) 
                 for tag in all_tags 
                 if tag in positive_weights and tag in negative_weights}
    if conflicts:
        print(f"\nTag Conflicts (appear in both positive and negative):")
        for tag, (pos, neg) in sorted(conflicts.items(), key=lambda x: abs(x[1][0] - x[1][1]), reverse=True):
            net = pos - neg
            print(f"  {tag:30s} positive={pos:6.4f} negative={neg:6.4f} net={net:6.4f}")
    
    # Run recommendation engine
    print_section("Recommendation Results")
    
    response = engine.recommend(context)
    
    print(f"\nRecommendations generated: {len(response.scores)}")
    
    if response.scores:
        print("\nTop Recommendations:")
        sorted_scores = sorted(response.scores.items(), key=lambda x: x[1].score, reverse=True)
        for i, (entry_id, score) in enumerate(sorted_scores[:10], 1):
            entry = next((e for e in candidate_entries if e['id'] == entry_id), None)
            title = entry.get('title', '') if entry else ''
            abstract = entry.get('abstract', '') if entry else ''
            
            print(f"\n  {i}. {entry_id}")
            if title:
                print(f"     Title: {title[:80]}{'...' if len(title) > 80 else ''}")
            if abstract:
                abstract_preview = abstract[:150].replace('\n', ' ').strip()
                print(f"     Abstract: {abstract_preview}{'...' if len(abstract) > 150 else ''}")
            print(f"     Score: {score.score:.4f}")
            print(f"     Matched tags: {', '.join(score.matched_tags[:5])}")
            if score.matched_tags:
                print(f"     Breakdown:")
                for tag in score.matched_tags[:5]:
                    net_w = net_weights.get(tag, 0)
                    if entry:
                        is_top = tag in (entry.get('top_tags') or [])
                        multiplier = 1.0 if is_top else 1.5
                        contribution = net_w * multiplier
                        print(f"       {tag}: net_weight={net_w:.4f} × multiplier={multiplier} = {contribution:.4f}")
    else:
        print("\n❌ No recommendations generated!")
        
        # Debug why
        print("\nDebugging why no recommendations:")
        print(f"  Net weights with positive values: {sum(1 for w in net_weights.values() if w > 0)}")
        print(f"  Total positive net weight: {sum(w for w in net_weights.values() if w > 0):.4f}")
        
        # Check candidate entries
        print(f"\n  Checking candidate entries for tag matches:")
        positive_net_tags = {tag: w for tag, w in net_weights.items() if w > 0}
        matches_found = 0
        for entry in candidate_entries[:20]:
            entry_tags = set(entry.get('top_tags', []) + entry.get('detail_tags', []))
            matching_tags = {tag: net_weights[tag] for tag in entry_tags if tag in positive_net_tags}
            if matching_tags:
                matches_found += 1
                sorted_matches = sorted(matching_tags.items(), key=lambda x: x[1], reverse=True)
                print(f"    ✓ {entry['id']}: matches {len(matching_tags)} tags")
                for tag, weight in sorted_matches[:3]:
                    print(f"         {tag}: net_weight={weight:.4f}")
        if not matches_found:
            print("    ✗ No candidate entries have tags with positive net weights!")
            print(f"\n    Top 10 tags with positive net weight (looking for these):")
            sorted_positive = sorted(positive_net_tags.items(), key=lambda x: x[1], reverse=True)
            for tag, weight in sorted_positive[:10]:
                print(f"      {tag:30s} {weight:8.4f}")
            if candidate_entries:
                print(f"\n    Sample candidate entry tags (for comparison):")
                for entry in candidate_entries[:3]:
                    entry_id = entry['id']
                    title = entry.get('title', '')
                    entry_tags = set(entry.get('top_tags', []) + entry.get('detail_tags', []))
                    print(f"      {entry_id}: {list(entry_tags)[:8]}")
                    if title:
                        print(f"        Title: {title[:60]}{'...' if len(title) > 60 else ''}")
    
    # Show profile
    print_section("Strategy Profile")
    profile = response.profiles.get("tag_preference", {})
    print(f"\nTop tags: {profile.get('top_tags', [])}")
    print(f"Total positive tag weights: {sum(positive_weights.values()):.4f}")
    print(f"Total negative tag weights: {sum(negative_weights.values()):.4f}")
    print(f"Total net tag weights (positive): {sum(w for w in net_weights.values() if w > 0):.4f}")
    print(f"Total net tag weights (negative): {sum(w for w in net_weights.values() if w < 0):.4f}")
    
    # Show favorite papers details
    print_section("Favorite Papers Analysis")
    for fav in favorites_meta[:10]:
        fav_id = fav['id']
        is_also_read = fav_id in read_map
        title = fav.get('title', '')
        abstract = fav.get('abstract', '')
        
        print(f"\n  {fav_id} {'(also read)' if is_also_read else ''}")
        if title:
            print(f"    Title: {title[:80]}{'...' if len(title) > 80 else ''}")
        if abstract:
            abstract_preview = abstract[:150].replace('\n', ' ').strip()
            print(f"    Abstract: {abstract_preview}{'...' if len(abstract) > 150 else ''}")
        print(f"    Top tags: {fav.get('top_tags', [])}")
        print(f"    Detail tags: {fav.get('detail_tags', [])[:5]}")
        if fav_id in favorites_map:
            print(f"    Favorite time: {favorites_map[fav_id]}")
        if is_also_read:
            print(f"    Read time: {read_map[fav_id]}")
    
    if len(favorites_meta) > 10:
        print(f"\n  ... and {len(favorites_meta) - 10} more favorite papers")
    
    # Summary
    print_section("Summary")
    print(f"\n  User has {len(favorites_meta)} favorite papers in system")
    print(f"  User has {len(read_meta)} read papers in system")
    print(f"  {len(set(favorites_map.keys()) & set(read_map.keys()))} favorites are also read")
    print(f"  {len(candidate_entries)} unread candidate papers available")
    print(f"  {len(response.scores)} recommendations generated")
    
    if not response.scores:
        print(f"\n  ⚠️  No recommendations because:")
        positive_net_tags = {tag: w for tag, w in net_weights.items() if w > 0}
        if not positive_net_tags:
            print(f"     - All net tag weights are <= 0 (negative signals too strong)")
        else:
            print(f"     - No unread papers match the {len(positive_net_tags)} tags with positive net weights")
            print(f"     - User's favorite tags: {list(positive_net_tags.keys())[:5]}")
            print(f"     - But unread papers have different tags")
    else:
        print(f"\n  ✓ Recommendations working!")
        print(f"     Top recommendation: {list(response.scores.keys())[0]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug/debug_recommendations.py <user_id>")
        print("Example: python debug/debug_recommendations.py yu")
        sys.exit(1)
    
    uid = sys.argv[1]
    try:
        debug_recommendations(uid)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

