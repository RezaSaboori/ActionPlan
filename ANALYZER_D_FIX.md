# Analyzer_D Threshold & Fallback Fix

## Problem Identified

**Symptom**: Action plan generation failing with 0 actions extracted

**Root Cause**: 
- Analyzer_D was filtering out ALL nodes because scoring threshold (0.7) was too strict
- All 7 subjects returned "0 relevant nodes"
- This cascaded to Extractor (0 actions), Quality Checker (score 0.0), and empty final plan

**Log Evidence**:
```
07:51:24 - Subject 'Assessment of nutritional status...': Found 0 relevant nodes
07:51:40 - Subject 'Designing and implementing...': Found 0 relevant nodes
...ALL 7 subjects: Found 0 relevant nodes

07:52:42 - EXTRACTOR AGENT COMPLETED: Total actions: 0 across 7 subjects
07:52:46 - Quality check result: retry (score: 0.0)
```

## Solution Implemented

### 1. **Lowered Score Threshold**
**File**: `config/settings.py`
- Changed `analyzer_d_score_threshold` from **0.7 → 0.5**
- More lenient threshold allows moderately relevant nodes through

### 2. **Added Minimum Nodes Guarantee**
**File**: `config/settings.py`
- Added new setting: `analyzer_d_min_nodes_per_subject = 3`
- Guarantees at least 3 nodes per subject for extraction

### 3. **Implemented Fallback Mechanism**
**File**: `agents/analyzer_d.py`

#### Changes Made:
1. **In `__init__`**: Load `min_nodes_per_subject` setting
2. **In `execute` method**: Added fallback check after scoring
   ```python
   if len(relevant_nodes) < self.min_nodes_per_subject and parent_nodes:
       relevant_nodes = self.apply_fallback_selection(parent_nodes, subject, self.min_nodes_per_subject)
   ```
3. **New method `apply_fallback_selection`**:
   - Scores all parent nodes
   - Sorts by score (descending)
   - Returns top-K nodes even if below threshold
   - Logs scores for transparency

## How It Works

### Normal Flow (nodes meet threshold):
1. Score nodes with LLM
2. Filter nodes with score ≥ 0.5
3. Return filtered nodes

### Fallback Flow (no/few nodes meet threshold):
1. Detect insufficient nodes (< 3)
2. Score ALL parent nodes
3. Sort by score descending
4. Take top 3 nodes regardless of threshold
5. Log warning with scores

## Benefits

1. **Guaranteed Output**: Always returns at least min_nodes nodes
2. **Better Quality**: Lowered threshold (0.7 → 0.5) catches more relevant content
3. **Graceful Degradation**: Falls back to best available nodes instead of failing
4. **Transparency**: Logs fallback activation and scores
5. **Configurable**: All values adjustable via settings/env vars

## Configuration

Via `.env` file:
```bash
# Lower threshold for more lenient filtering (default: 0.5)
ANALYZER_D_SCORE_THRESHOLD=0.5

# Minimum nodes guaranteed per subject (default: 3)
ANALYZER_D_MIN_NODES_PER_SUBJECT=3
```

## Expected Behavior

### Before Fix:
```
Subject 1: Found 0 relevant nodes → 0 actions → Empty plan
Subject 2: Found 0 relevant nodes → 0 actions → Empty plan
...
Result: Empty plan, quality score 0.0
```

### After Fix:
```
Subject 1: Found 0 nodes above 0.5 → Fallback activated → 3 best nodes selected
Subject 2: Found 1 node above 0.5 → Fallback activated → 3 best nodes selected
...
Result: Actions extracted, quality score > 0.7, complete plan
```

## Testing Recommendations

1. **Run previous failing case**: "Nutritional support in conflict zones"
2. **Verify logs show**:
   - Threshold checks passing (some nodes ≥ 0.5)
   - OR fallback activating with scores listed
   - Actions extracted (> 0)
3. **Check output quality**: Actions should be relevant to subject

## Monitoring

Look for these log patterns:

**Success (threshold working)**:
```
Subject 'X': Found 5 relevant nodes
```

**Success (fallback activated)**:
```
Only 0 nodes found above threshold for 'X'. Applying fallback...
Fallback selected 3 nodes with scores: ['0.42', '0.38', '0.35']
Subject 'X': Found 3 relevant nodes
```

## Rollback

If this causes issues, revert by:
1. Change threshold back to 0.7 in `settings.py`
2. Remove fallback code from `analyzer_d.py`
3. Or set via env: `ANALYZER_D_SCORE_THRESHOLD=0.7`

## Version
Analyzer_D Fix v1.0 - October 16, 2025

