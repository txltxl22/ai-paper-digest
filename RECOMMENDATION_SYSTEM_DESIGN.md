# Enhanced Recommendation System Design
## Using Both Positive (感兴趣) and Negative (没兴趣) Signals

### Current System Analysis
- ✅ Uses positive signals (favorites) to build tag preferences
- ❌ Ignores negative signals (read/not interested list)
- ❌ Only filters out read papers, doesn't learn from them

### Best Practice: Dual-Signal Tag-Based Scoring

#### Core Principle
**Score = Positive Tag Weights - Negative Tag Weights**

This approach:
1. **Learns what user likes** from favorites (positive tags)
2. **Learns what user dislikes** from read list (negative tags)
3. **Penalizes recommendations** that match disliked tags
4. **Boosts recommendations** that match liked tags
5. **Maintains interpretability** (users can see why)

### Implementation Strategy

#### 1. Enhanced RecommendationContext
Add negative signals to context:
```python
@dataclass(slots=True)
class RecommendationContext:
    candidate_entries: Sequence[Dict[str, Any]]
    favorites_meta: Sequence[Dict[str, Any]]  # Positive signals
    favorites_map: Dict[str, Optional[str]]
    read_meta: Sequence[Dict[str, Any]] = field(default_factory=list)  # Negative signals
    read_map: Dict[str, Optional[str]] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
```

#### 2. Enhanced TagPreferenceStrategy

**Key Improvements:**

1. **Build Negative Tag Weights**
   - Extract tags from "read" (没兴趣) papers
   - Apply recency weighting (recent dislikes matter more)
   - Store as negative weights

2. **Dual Scoring Formula**
   ```
   final_score = (positive_tag_score * positive_multiplier) 
                 - (negative_tag_score * negative_penalty_multiplier)
   ```

3. **Confidence-Based Penalties**
   - If user has many negative examples for a tag → strong penalty
   - If user has few negative examples → light penalty
   - Use logarithmic scaling to prevent over-penalization

4. **Tag Conflict Resolution**
   - If a tag appears in both positive and negative:
     - Recent signal wins (if both recent)
     - Or use ratio: positive_count / (positive_count + negative_count)

### Recommended Algorithm

```python
class EnhancedTagPreferenceStrategy:
    def __init__(
        self,
        positive_multiplier: float = 1.0,
        negative_penalty_multiplier: float = 1.2,  # Penalties slightly stronger
        recency_half_life_days: int = 21,
        min_negative_samples: int = 2,  # Need at least 2 to trust negative signal
    ):
        ...
    
    def score(self, context):
        # Build positive weights (existing)
        positive_weights = self._build_tag_weights(
            context.favorites_meta, 
            context.favorites_map,
            is_positive=True
        )
        
        # Build negative weights (new)
        negative_weights = self._build_tag_weights(
            context.read_meta,
            context.read_map,
            is_positive=False
        )
        
        # Score each candidate
        for entry in context.candidate_entries:
            positive_score = self._calculate_positive_score(
                entry, positive_weights
            )
            negative_score = self._calculate_negative_score(
                entry, negative_weights
            )
            
            # Final score with penalty
            final_score = positive_score - (negative_score * penalty_multiplier)
            
            # Only recommend if positive score > negative penalty
            if final_score > 0:
                scores[entry_id] = final_score
```

### Performance Optimizations

1. **Recency Weighting** (already implemented)
   - Recent signals (both positive and negative) have more impact
   - Exponential decay: `weight = exp(-days / half_life)`

2. **Tag Hierarchy Respect**
   - Top tags: higher weight (both positive and negative)
   - Detail tags: lower weight but still significant

3. **Normalization**
   - Prevent users with many signals from dominating
   - Use logarithmic normalization: `k = 1 / log2(total_signals + 1.5)`

4. **Minimum Sample Thresholds**
   - Don't penalize based on single negative example
   - Require at least 2-3 negative examples for a tag before applying penalty

### Advanced Features (Future)

1. **Temporal Patterns**
   - User's interests change over time
   - Weight recent signals more heavily
   - Decay old signals faster

2. **Tag Co-occurrence**
   - Learn tag combinations user likes/dislikes
   - "vision + diffusion" → strong positive
   - "theory + mathematics" → user might skip

3. **Confidence Intervals**
   - Low confidence: small penalty/boost
   - High confidence: strong penalty/boost
   - Based on number of examples

4. **A/B Testing Framework**
   - Test different penalty multipliers
   - Test different recency decay rates
   - Measure click-through rates

### Implementation Priority

**Phase 1: Basic Negative Feedback** (High Impact, Low Effort)
- Add negative tag weights
- Subtract negative scores from positive scores
- Simple penalty multiplier (1.0-1.5x)

**Phase 2: Confidence & Thresholds** (Medium Impact, Medium Effort)
- Minimum sample thresholds
- Confidence-based penalties
- Tag conflict resolution

**Phase 3: Advanced Features** (Lower Priority)
- Temporal patterns
- Tag co-occurrence
- A/B testing

### Expected Improvements

1. **Precision**: Reduce false positives (papers user won't like)
2. **Relevance**: Better match user's actual interests
3. **User Satisfaction**: Less noise, more signal
4. **Engagement**: Higher click-through on recommendations

### Metrics to Track

- **Recommendation Acceptance Rate**: % of recommended papers user reads
- **Negative Signal Effectiveness**: Reduction in disliked papers shown
- **Diversity**: Ensure recommendations aren't too narrow
- **Coverage**: Ensure all user interests are represented

