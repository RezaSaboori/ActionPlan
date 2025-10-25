# Analysis: Why Analyzer Returns Irrelevant Reproductive Health Nodes

## Problem Summary

The Analyzer is returning completely irrelevant nodes from "reproductive_health_in_war_and_humanitarian_emergencies" when queried about "Emergency Triage Protocol for Mass Casualty Events."

## Root Causes Identified

### 1. **Graph-Aware RAG is Disabled (PRIMARY ISSUE)**

**Location:** `rag_tools/hybrid_rag.py:25`

```python
def __init__(
    self,
    graph_collection: str = "rules",
    vector_collection: str = "rules_documents",
    use_graph_aware: bool = False,  # ← THE PROBLEM!
    markdown_logger=None
):
```

**Impact:**
- When `use_graph_aware=False`, the system uses **legacy mode** which relies on simple keyword matching
- The semantic embedding-based search (GraphAwareRAG) is completely bypassed
- Instead of using cosine similarity on embeddings, it's doing crude keyword regex matching

**Location:** `workflows/orchestration.py:47-50`

```python
main_hybrid_rag = HybridRAG(
    graph_collection=settings.graph_prefix,
    vector_collection=settings.documents_collection,
    markdown_logger=markdown_logger
    # Missing: use_graph_aware=True
)
```

The workflow doesn't pass `use_graph_aware=True`, so it defaults to False.

---

### 2. **Legacy Keyword Matching is Too Permissive**

**Location:** `rag_tools/graph_rag.py:156-189` (hybrid_search method)

```python
def hybrid_search(self, query: str, top_k: int = 5):
    # Extract keywords from query (simple approach)
    keywords = [word.lower() for word in query.split() if len(word) > 3]
    # Find matching nodes
    nodes = self.traverse_by_keywords(keywords, top_k=top_k)
```

**Location:** `rag_tools/graph_rag.py:36-67` (traverse_by_keywords method)

```python
def traverse_by_keywords(self, keywords: List[str], top_k: int = 5):
    # Build keyword search pattern (case-insensitive)
    keyword_pattern = '|'.join([f"(?i).*{kw}.*" for kw in keywords])
    
    query = """
    MATCH (h:Heading)
    WHERE h.title =~ $pattern OR h.summary =~ $pattern
    RETURN ...
    """
```

**The Problem:**

For the query:
```
"Identify the triage categories, decision‑making criteria, and resource‑allocation 
matrix described in the 'Emergency Logistics and Supply Chain Management in Urban 
Warfare and Disaster Conditions' guideline..."
```

Keywords extracted (words > 3 chars):
```
["Identify", "triage", "categories", "decision", "making", "criteria", 
"resource", "allocation", "matrix", "described", "Emergency", "Logistics", 
"Supply", "Chain", "Management", "Urban", "Warfare", "Disaster", "Conditions", 
"guideline", "outline", "they", "operationalized", "Code", "Orange", "protocol"]
```

These keywords are **too generic** and match MANY healthcare documents including:
- **Reproductive health** (has "emergency", "decision", "criteria", "protocol", "management")
- **Clinical protocols** (has "triage", "emergency", "conditions", "management")
- **Any guideline** (has "guideline", "protocol", "criteria")

The regex pattern `(?i).*emergency.*|.*triage.*|.*decision.*|.*protocol.*` matches almost everything!

---

### 3. **All Graph Results Get score=1.0**

**Location:** `rag_tools/hybrid_rag.py:116-136` (_graph_only method)

```python
def _graph_only(self, query: str, top_k: int) -> List[Dict[str, Any]]:
    """Graph-only search."""
    results = self.graph_rag.hybrid_search(query, top_k=top_k)
    
    # Format results
    formatted = []
    for r in results:
        formatted.append({
            'text': r.get('summary', r.get('title', '')),
            'score': 1.0,  # ← Graph doesn't provide scores
            ...
        })
```

**Impact:**
- All results from graph keyword search are assigned score=1.0
- No semantic relevance scoring
- This explains why your log shows "Score: 1.00" for ALL results

---

### 4. **LLM Filtering Accepts Too Many False Positives**

**Location:** `agents/analyzer.py:409-479` (_identify_relevant_nodes method)

The LLM is asked to filter nodes, but when presented with nodes that contain words like "protocol", "emergency", "management", it's too permissive in accepting them as relevant.

Example from log (lines 308-386):
```json
"relevant_node_ids": [
    "reproductive_health_in_war_and_humanitarian_emergencies_h7",
    "reproductive_health_in_war_and_humanitarian_emergencies_h14",
    "reproductive_health_in_war_and_humanitarian_emergencies_h15",
    ...
]
```

The LLM sees:
- "2.2 Six MISP Objectives and Operational **Protocols**" ✗
- "III. CLINICAL **PROTOCOLS** FOR PRIORITY SRH CONDITIONS" ✗
- "**Emergency** Obstetric and Newborn Care (EmONC)" ✗
- "Checklist Template Guide" ✓ (actually somewhat relevant)
- "Strategic Consequences" (mentions "triage") ✓

It accepts reproductive health protocols because they share surface-level keywords with triage protocols, but they're completely different contexts.

---

## The Complete Pipeline Flow (Current Broken State)

```
Query: "triage categories, resource allocation, emergency response..."
    ↓
[Analyzer Phase 2] unified_rag.query(strategy="hybrid")
    ↓
[HybridRAG] use_graph_aware=False → uses legacy _hybrid_search()
    ↓
[Legacy hybrid_search] calls graph_rag.hybrid_search()
    ↓
[GraphRAG.hybrid_search] extracts keywords: ["triage", "categories", "resource", 
                         "allocation", "emergency", "response", "protocol"...]
    ↓
[GraphRAG.traverse_by_keywords] regex pattern: "(?i).*(triage|categories|resource|
                                allocation|emergency|response|protocol).*"
    ↓
[Neo4j Query] WHERE h.title =~ $pattern OR h.summary =~ $pattern
    ↓
**MATCHES EVERYTHING**: reproductive health, triage, protocols, emergency obstetric care...
    ↓
[Format Results] All get score=1.0 (no semantic scoring)
    ↓
[LLM Filter] Sees titles with "protocol", "emergency", "management" → accepts them
    ↓
**RESULT**: Irrelevant reproductive health nodes with score=1.0
```

---

## Solutions

### Solution 1: Enable GraphAwareRAG (RECOMMENDED)

**File:** `workflows/orchestration.py:47-50`

**Change:**
```python
main_hybrid_rag = HybridRAG(
    graph_collection=settings.graph_prefix,
    vector_collection=settings.documents_collection,
    use_graph_aware=True,  # ← ADD THIS
    markdown_logger=markdown_logger
)
```

**File:** `rag_tools/hybrid_rag.py:25`

**Change:**
```python
def __init__(
    self,
    graph_collection: str = "rules",
    vector_collection: str = "rules_documents",
    use_graph_aware: bool = True,  # ← Change default to True
    markdown_logger=None
):
```

**Why this works:**
- Uses actual semantic embeddings stored in Neo4j
- Computes cosine similarity between query embedding and document embeddings
- Provides meaningful scores (0.0 to 1.0) based on semantic relevance
- Won't match "Clinical Management of Rape" when query is about "mass casualty triage"

---

### Solution 2: Improve Keyword Extraction (SECONDARY)

Even if we keep legacy mode, improve the keyword extraction to be smarter.

**File:** `rag_tools/graph_rag.py:156-189`

**Change:**
```python
def hybrid_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Combine keyword search with graph traversal."""
    
    # Improved keyword extraction with stop words filtering
    stop_words = {
        'identify', 'locate', 'extract', 'find', 'review', 'determine',
        'describe', 'outline', 'explain', 'summarize', 'detail', 'they',
        'that', 'this', 'what', 'which', 'where', 'when', 'how', 'from',
        'with', 'have', 'been', 'will', 'can', 'should', 'must'
    }
    
    # Extract keywords (length > 3, not stop words)
    words = query.lower().split()
    keywords = [w for w in words if len(w) > 3 and w not in stop_words]
    
    # Limit to most distinctive keywords (e.g., first 10)
    keywords = keywords[:10]
    
    # Find matching nodes
    nodes = self.traverse_by_keywords(keywords, top_k=top_k)
    ...
```

---

### Solution 3: Improve LLM Filtering Prompt (TERTIARY)

**File:** `agents/analyzer.py:435-456`

**Enhance the prompt:**
```python
prompt = f"""Analyze the following document nodes and identify which ones contain **actionable recommendations** relevant to the problem statement.

**IMPORTANT**: Be STRICT in your assessment. Only select nodes that are DIRECTLY relevant to the specific problem domain. Do not select nodes just because they share generic keywords like "protocol", "emergency", or "management".

**Problem Statement:**
{problem_statement}

**Document Nodes:**
{node_context}

**Your Task:**
Identify node IDs that contain:
- Concrete actions, procedures, or protocols SPECIFICALLY FOR THIS PROBLEM
- Implementation guidance DIRECTLY APPLICABLE to this scenario
- Specific steps or checklists FOR THIS EXACT USE CASE
- Operational recommendations WITHIN THIS DOMAIN

**Critical Filtering Rules:**
❌ REJECT nodes from unrelated domains even if they use similar terminology
❌ REJECT generic protocols that don't match the specific scenario
❌ REJECT clinical protocols when the query is about operational/logistical protocols
✅ ACCEPT only nodes that directly address the problem statement's core requirements

**Output Format:**
Return a JSON object with a list of relevant node IDs:
{{
  "relevant_node_ids": ["node_id_1", "node_id_2", ...]
}}

Respond with valid JSON only."""
```

---

## Recommended Action Plan

1. **IMMEDIATE FIX**: Enable `use_graph_aware=True` in:
   - `rag_tools/hybrid_rag.py` (default parameter)
   - `workflows/orchestration.py` (when creating main_hybrid_rag)

2. **VERIFY**: Check that embeddings exist in Neo4j:
   ```cypher
   MATCH (h:Heading)
   WHERE h.summary_embedding IS NOT NULL
   RETURN count(h) as nodes_with_embeddings
   ```

3. **TEST**: Re-run the same query and verify results use semantic similarity

4. **OPTIONAL**: Implement Solutions 2 and 3 for additional robustness

---

## Testing the Fix

After enabling GraphAwareRAG, the query flow will be:

```
Query: "triage categories, resource allocation, emergency response..."
    ↓
[Analyzer Phase 2] unified_rag.query(strategy="hybrid")
    ↓
[HybridRAG] use_graph_aware=True → uses graph_aware_rag.hybrid_retrieve()
    ↓
[GraphAwareRAG.hybrid_retrieve] 
    • Calls _retrieve_by_summary() with embeddings
    • Computes cosine similarity: query_embedding vs. node_embeddings
    ↓
[Neo4j Query with Embeddings] 
    MATCH (h:Heading)
    WHERE h.summary_embedding IS NOT NULL
    RETURN h.*, h.summary_embedding
    ↓
[Compute Similarity] cosine_similarity(query_emb, each node_emb)
    ↓
[Sort by Score] Nodes sorted by actual semantic relevance (0.0-1.0)
    ↓
**RESULT**: Only semantically similar nodes (e.g., mass casualty triage, 
           emergency operations, logistics protocols)
```

Expected log output should show:
- Scores ranging from ~0.4 to ~0.9 (not all 1.0)
- Nodes from documents like:
  - "Emergency Logistics and Supply Chain Management..."
  - "Implementing Emergency Operations Centers..."
  - "National Health System Response Plan..."
- NO reproductive health nodes

---

## Conclusion

The core issue is that **semantic search is disabled** and the system is falling back to crude keyword matching that can't distinguish between "mass casualty triage protocols" and "clinical reproductive health protocols" because they share too many generic healthcare terms.

Enabling `use_graph_aware=True` will activate proper embedding-based semantic search that understands the contextual difference between these domains.

