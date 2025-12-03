# Debug and Profile Scripts

This directory contains debug and profiling scripts for the recommendation system and other components.

## Scripts

### `debug_recommendations.py`

Debug tool for the tag-based recommendation system.

**Usage:**
```bash
python debug/debug_recommendations.py <user_id>
```

**Example:**
```bash
python debug/debug_recommendations.py yu
```

**What it shows:**
- User's favorite and read papers
- Tag weight calculations (positive, negative, net)
- Tag conflicts
- Top recommendations with scores and matched tags
- Favorite papers analysis
- Summary statistics

### `debug_embedding_recommendations.py`

Debug tool for the embedding-based recommendation system.

**Usage:**
```bash
python debug/debug_embedding_recommendations.py <user_id> [model_name]
```

**Examples:**
```bash
python debug/debug_embedding_recommendations.py yu
python debug/debug_embedding_recommendations.py yu all-MiniLM-L6-v2
python debug/debug_embedding_recommendations.py yu all-mpnet-base-v2
```

**What it shows:**
- Favorite papers and their embeddings
- User preference vector
- Similarity between favorite papers
- Candidate paper scoring with cosine similarity
- Comparison between embedding and tag-based strategies
- Hybrid engine test results

**Requirements:**
- `sentence-transformers` package (install with `uv add sentence-transformers`)

## Notes

- Both scripts use Pydantic models for type-safe data loading
- Scripts automatically find the project root and load data from `user_data/` and `summary/` directories
- All paths are relative to the project root

