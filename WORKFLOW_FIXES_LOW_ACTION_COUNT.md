# Workflow Fixes: Low Action Count Issue

**Date:** 2025-11-12  
**Issue:** Only 10 actions were extracted for "Mass Casualty Triage and Treatment Protocol"  
**Expected:** 50-100+ actions for such a complex scenario

---

## Root Cause Analysis

### Problem Chain Identified:

1. **RAG Query** → Retrieves only 10 results per query (top_k=5 * 2)
2. **Analyzer Phase 2 Filter** → Uses overly strict LLM prompt
3. **LLM Evaluation** → Rejects most/all nodes (2 of 5 queries returned EMPTY!)
4. **Result** → Only 6 unique nodes selected across 5 queries
5. **Phase3 Expansion** → Expands to 12 nodes (modest)
6. **Extractor** → Many nodes have 0 actions due to missing WHO/WHEN
7. **Final Output** → Only 10 complete actions

---

## Critical Issues Found

### 1. **Overly Strict Analyzer Filtering Prompt** ⚠️ CRITICAL

**Location:** `Agents/agents/analyzer.py` lines 540-544

**Problem:**
```python
**Quality Standards:**
- Precision over recall: Better to miss a marginally relevant node than include an irrelevant one
- Zero tolerance for cross-domain contamination
- Each included node must have DIRECT, SPECIFIC applicability
```

**Impact:**
- Query 1: Returned 10 nodes → LLM selected **0** ❌
- Query 2: Returned 10 nodes → LLM selected **2** ✓
- Query 3: Returned 10 nodes → LLM selected **2** ✓
- Query 4: Returned 10 nodes → LLM selected **4** ✓
- Query 5: Returned 10 nodes → LLM selected **0** ❌

**Total: Only 6-8 unique nodes from 50 retrieved!**

**Fix Applied:**
```python
**Quality Standards:**
- Recall over precision: Better to include a potentially relevant node than miss an important one
- Be inclusive: Cross-domain nodes may contain valuable actionable content
- Each included node should have POTENTIAL applicability (direct or indirect)
```

---

### 2. **Hard-Coded 30-Node Evaluation Limit**

**Location:** `Agents/agents/analyzer.py` line 523

**Problem:**
```python
for node in nodes[:30]  # Limit to avoid token overflow
```

Even if RAG returns 100 nodes, only first 30 are evaluated by LLM.

**Fix Applied:**
```python
for node in nodes[:100]  # Increased limit - batching will handle large sets
```

**Rationale:** The analyzer has batch processing logic (lines 474-485) that handles large node sets automatically.

---

### 3. **Low `top_k_results` Setting**

**Location:** `Agents/config/settings.py` line 146

**Problem:**
```python
top_k_results: int = Field(default=5, env="TOP_K_RESULTS")
```

Each query retrieves `top_k * 2 = 10` results maximum (line 453 in analyzer.py).

**Fix Applied:**
```python
top_k_results: int = Field(default=20, env="TOP_K_RESULTS")  # Increased from 5
```

**Impact:** Each query now retrieves up to 40 results instead of 10.

---

### 4. **Rejection Criteria Too Aggressive**

**Location:** `Agents/agents/analyzer.py` lines 567-574

**Problem:**
```python
### Step 3: Apply Rejection Filters
**Automatic Rejection Criteria** (reject if ANY apply):
- Node is from a fundamentally different domain
- Node's terminology overlap is superficial
- Node addresses a different phase/stage
- Node's scope is mismatched
- Node is purely theoretical/background
- Node's recommendations are incompatible
```

Rejecting on **ANY** of these criteria is too harsh.

**Fix Applied:**
```python
### Step 3: Apply Flexible Filtering
**Consider rejecting ONLY if ALL of these apply**:
- Node is from a completely unrelated domain (e.g., agriculture for clinical care queries)
- Node's content has zero operational overlap with the problem
- Node is purely definitional without any procedural guidance
- Node's recommendations are fundamentally incompatible with the problem's context

**Note**: Nodes from adjacent domains, different phases, or different organizational levels 
may still contain valuable transferable guidance.
```

Changed from "reject if ANY apply" to "reject ONLY if ALL apply".

---

### 5. **"No or Maybe = Reject" Logic**

**Location:** `Agents/agents/analyzer.py` lines 576-582

**Problem:**
```python
Before including a node, ask:
- "Would a practitioner working on THIS SPECIFIC problem find THIS node directly useful?"
- "Does this node provide guidance that moves toward solving THIS problem?"
- "Is the connection between this node and the problem DIRECT, not inferential?"

**If the answer to any question is 'No' or 'Maybe', REJECT the node.**
```

This rejects nodes on uncertainty ("Maybe"), which is too conservative.

**Fix Applied:**
```python
Before including a node, ask:
- "Could a practitioner working on THIS problem find THIS node useful?"
- "Does this node provide guidance that might help solve THIS problem?"
- "Is there a reasonable connection between this node and the problem?"

**If the answer to ANY question is 'Yes' or 'Maybe', INCLUDE the node. 
Only reject if clearly irrelevant.**
```

Changed to **inclusive logic**: "Maybe" now means INCLUDE instead of REJECT.

---

## Additional Fix: Extractor Prompt for Incomplete Actions

**Location:** `Agents/config/prompts.py` lines 516-538, 584-601, 702-704

**Problem:** Extractor was skipping actions when WHO/WHEN were not explicitly stated, or hallucinating details.

**Fix Applied:** Added clear instructions to extract actions with empty WHO/WHEN fields:
- Use empty string ("") for missing WHO/WHEN
- DO NOT infer or hallucinate
- Let validation flag them for downstream agents

---

## Expected Impact

### Before Fixes:
- 5 queries × 10 results = 50 retrieved nodes
- Strict filtering → 6 selected nodes
- Phase3 expansion → 12 final nodes
- Extraction → 10 complete actions

### After Fixes:
- 5 queries × 40 results = 200 retrieved nodes
- Inclusive filtering → Expected 30-50 selected nodes
- Phase3 expansion → Expected 50-80 final nodes
- Extraction → Expected 50-100+ actions (including flagged)

**Estimated Improvement: 5-10x more actions extracted**

---

## Testing Recommendations

1. **Re-run the same scenario:**
   - Name: "Mass Casualty Triage and Treatment Protocol"
   - Level: center
   - Phase: response
   - Subject: war

2. **Compare metrics:**
   - Number of nodes selected by Analyzer Phase 2
   - Number of nodes after Phase3 expansion
   - Number of complete actions extracted
   - Number of flagged actions (should be > 0 now)

3. **Verify quality:**
   - Check that included nodes are actually relevant
   - Ensure filtering is not TOO loose now
   - Confirm flagged actions have empty WHO/WHEN

---

## Configuration Options

Users can now tune the trade-off via environment variables:

```bash
# For more aggressive retrieval (current defaults after fixes):
export TOP_K_RESULTS=20

# For even more comprehensive extraction:
export TOP_K_RESULTS=30

# For faster processing with fewer nodes:
export TOP_K_RESULTS=10
```

---

## Files Modified

1. `Agents/agents/analyzer.py` - Lines 523, 567-582, 611-614
2. `Agents/config/settings.py` - Line 146
3. `Agents/config/prompts.py` - Lines 516-538, 584-601, 702-704

---

## Conclusion

The workflow had multiple compounding bottlenecks:
- Low retrieval limits
- Overly conservative filtering
- Incomplete action extraction

All issues have been systematically addressed. The system should now:
- ✅ Retrieve 4x more nodes per query
- ✅ Use inclusive filtering (favor recall over precision)
- ✅ Evaluate up to 100 nodes (vs 30 before)
- ✅ Extract incomplete actions and flag them
- ✅ Pass flagged actions to downstream agents for completion

Expected result: **5-10x increase in extracted actions** for complex scenarios.

