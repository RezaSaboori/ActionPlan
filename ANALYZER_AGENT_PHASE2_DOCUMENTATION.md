# Analyzer Agent Phase 2: Comprehensive Documentation

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Phase 2 Workflow](#phase-2-workflow)
- [Core Components](#core-components)
- [LLM Prompts and Evaluation Framework](#llm-prompts-and-evaluation-framework)
- [Batch Processing](#batch-processing)
- [Configuration](#configuration)
- [Integration with RAG Systems](#integration-with-rag-systems)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

### Purpose

The Analyzer Agent's Phase 2 is responsible for **Action Extraction** - executing refined queries against the knowledge base and identifying specific document nodes (sections) that contain actionable recommendations relevant to the problem statement.

### Key Objectives

1. **Execute Refined Queries**: Run optimized queries generated in Phase 1 against the hybrid RAG system
2. **Filter Relevant Nodes**: Use LLM-based evaluation to identify nodes with actionable content
3. **Extract Node IDs**: Return a curated list of node IDs for downstream processing
4. **Scale Efficiently**: Handle large result sets through intelligent batch processing
5. **Prevent False Positives**: Apply domain-aware filtering to avoid cross-domain contamination

### Position in Workflow

```
Phase 1 (Context Building)
         ↓
    [Refined Queries Generated]
         ↓
Phase 2 (Action Extraction) ← YOU ARE HERE
         ↓
    [Node IDs Extracted]
         ↓
Phase 3 Agent (Deep Analysis)
```

---

## Architecture

### High-Level Design

Phase 2 follows a **Query-Execute-Filter-Extract** pattern:

```
┌─────────────────────────────────────────────────────────────┐
│                      PHASE 2 ENTRY POINT                    │
│  Input: refined_queries (from Phase 1), problem_statement   │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
        ┌──────────────────────────────┐
        │   For Each Refined Query     │
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │  Execute Query via HybridRAG │
        │  Strategy: "hybrid"          │
        │  top_k: settings × 2         │
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │  Extract Node Metadata       │
        │  - node_id                   │
        │  - title                     │
        │  - summary (up to 5000 chars)│
        │  - score                     │
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │  Check Batch Threshold       │
        │  len(nodes) > threshold?     │
        └──────────────┬───────────────┘
                       ↓
           ┌───────────┴────────────┐
           │                        │
      YES  ↓                        ↓  NO
  ┌────────────────┐      ┌─────────────────────┐
  │ Batch Process  │      │  Single LLM Call    │
  │ (chunks of N)  │      │  _identify_nodes    │
  └────────┬───────┘      └─────────┬───────────┘
           │                        │
           └───────────┬────────────┘
                       ↓
        ┌──────────────────────────────┐
        │   LLM Evaluation             │
        │   - Domain match             │
        │   - Functional alignment     │
        │   - Actionability            │
        │   - Contextual fit           │
        │   - Stakeholder alignment    │
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │  Collect Relevant Node IDs   │
        └──────────────┬───────────────┘
                       ↓
        ┌──────────────────────────────┐
        │  Deduplicate & Return        │
        │  all_node_ids (unique)       │
        └──────────────────────────────┘
```

### Key Methods

| Method | Purpose | Input | Output |
|--------|---------|-------|--------|
| `phase2_action_extraction()` | Main entry point | refined_queries, problem_statement | List[str] (node IDs) |
| `_identify_relevant_nodes()` | LLM-based evaluation | nodes, problem_statement | List[str] (filtered IDs) |
| `_process_nodes_in_batches()` | Batch processing | nodes, problem_statement, batch_size | List[str] (all IDs) |

---

## Phase 2 Workflow

### Step-by-Step Process

#### Step 1: Initialization

```python
def phase2_action_extraction(
    self,
    refined_queries: List[str],
    problem_statement: str
) -> List[str]:
    all_node_ids = []
    batch_threshold = self.settings.analyzer_phase2_batch_threshold  # Default: 50
    batch_size = self.settings.analyzer_phase2_batch_size  # Default: 20
```

**Purpose**: Set up processing parameters and storage

#### Step 2: Query Execution Loop

For each refined query generated in Phase 1:

```python
for idx, query in enumerate(refined_queries, 1):
    logger.info(f"Executing refined query {idx}/{len(refined_queries)}: {query[:100]}...")
    
    # Query the hybrid RAG system
    results = self.unified_rag.query(
        query,
        strategy="hybrid",  # Combines semantic + keyword search
        top_k=self.settings.top_k_results * 2  # Get extra results for filtering
    )
```

**Key Points**:
- **Strategy**: Uses "hybrid" mode combining semantic embeddings and graph structure
- **top_k Multiplier**: Fetches 2× the normal amount (default: 20 × 2 = 40 results)
- **Purpose**: Over-retrieve to ensure sufficient coverage before LLM filtering

#### Step 3: Node Metadata Extraction

```python
nodes = []
for result in results:
    metadata = result.get('metadata', {})
    node_id = metadata.get('node_id')
    if node_id:
        summary = metadata.get('summary', result.get('text', ''))
        nodes.append({
            'id': node_id,
            'title': metadata.get('title', 'Unknown'),
            'summary': summary[:5000] if summary else 'No summary',
            'score': result.get('score', 0.0)
        })
```

**Data Structure**:
- **node_id**: Unique identifier (e.g., "doc1_section_2_3")
- **title**: Section heading
- **summary**: Truncated to 5000 characters for LLM efficiency
- **score**: RAG similarity score (0.0-1.0)

#### Step 4: Batch Decision

```python
if len(nodes) > batch_threshold:
    relevant_ids = self._process_nodes_in_batches(
        nodes,
        problem_statement,
        batch_size
    )
else:
    relevant_ids = self._identify_relevant_nodes(
        nodes,
        problem_statement
    )
```

**Threshold Logic**:
- **< 50 nodes**: Single LLM call (faster, efficient)
- **≥ 50 nodes**: Batch processing (prevents context overflow)

#### Step 5: Deduplication

```python
all_node_ids.extend(relevant_ids)
# ... (after all queries processed)
unique_node_ids = list(set(all_node_ids))
```

**Purpose**: Remove duplicate node IDs from overlapping query results

---

## Core Components

### 1. Node Identification (`_identify_relevant_nodes`)

This is the **heart of Phase 2** - an LLM-based evaluation system that determines which nodes contain actionable, relevant content.

#### Input Format

```python
node_context = "\n\n".join([
    f"Node ID: {node['id']}\n"
    f"Title: {node.get('title', 'Untitled')}\n"
    f"Summary: {(node.get('summary') or 'No summary')[:300]}"
    for node in nodes[:100]
])
```

**Constraints**:
- Maximum 100 nodes per call (when not batching)
- Summaries truncated to 300 characters
- Clear formatting for LLM parsing

#### Evaluation Criteria

The LLM applies a **5-step evaluation framework**:

1. **Domain Match**: Does the node's subject area directly align with the problem's primary domain?
2. **Functional Alignment**: Does the node address the same functional need?
3. **Actionability**: Does the node contain implementable guidance (procedures, protocols, checklists)?
4. **Contextual Fit**: Is the operational context compatible (e.g., emergency vs. routine care)?
5. **Stakeholder Alignment**: Are the intended users/actors relevant?

**Rejection Criteria** (all must apply):
- Completely unrelated domain
- Zero operational overlap
- Purely definitional without procedural guidance
- Fundamentally incompatible context

#### Output Format

```json
{
  "relevant_node_ids": ["node_id_1", "node_id_2", "node_id_3"]
}
```

**Fallback**: If JSON parsing fails, returns top 5 nodes by score

---

### 2. Batch Processing (`_process_nodes_in_batches`)

Handles large node sets by dividing them into manageable chunks.

#### Algorithm

```python
def _process_nodes_in_batches(
    self,
    nodes: List[Dict[str, Any]],
    problem_statement: str,
    batch_size: int
) -> List[str]:
    all_relevant_ids = []
    
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}: nodes {i} to {i+len(batch)}")
        
        relevant_ids = self._identify_relevant_nodes(batch, problem_statement)
        all_relevant_ids.extend(relevant_ids)
    
    return all_relevant_ids
```

#### Example Scenario

- **Total nodes**: 87
- **Batch size**: 20
- **Processing**: 5 batches (20, 20, 20, 20, 7)
- **LLM calls**: 5 separate evaluations
- **Result**: Combined list of all relevant IDs

#### Benefits

1. **Prevents Token Overflow**: Keeps each LLM call within context limits
2. **Progress Tracking**: Logs batch-by-batch progress
3. **Error Isolation**: One failing batch doesn't break the entire process
4. **Configurable**: Adjustable via settings

---

## LLM Prompts and Evaluation Framework

### Prompt Structure

The Phase 2 prompt is designed to prevent **false positives** (irrelevant nodes) through structured reasoning:

```
┌───────────────────────────────────────────────────────────┐
│                    PROMPT STRUCTURE                       │
├───────────────────────────────────────────────────────────┤
│ 1. PROBLEM STATEMENT                                      │
│    - User's original request                              │
│    - Context from orchestrator                            │
├───────────────────────────────────────────────────────────┤
│ 2. DOCUMENT NODES TO EVALUATE                             │
│    - Node ID, Title, Summary (300 chars each)            │
│    - Formatted for clear parsing                          │
├───────────────────────────────────────────────────────────┤
│ 3. EVALUATION FRAMEWORK (4 STEPS)                         │
│    Step 1: Understand Core Domain                         │
│    Step 2: Apply Strict Relevance Criteria               │
│    Step 3: Apply Flexible Filtering                      │
│    Step 4: Verify Potential Value                        │
├───────────────────────────────────────────────────────────┤
│ 4. COMMON FALSE POSITIVE PATTERNS                         │
│    - Keyword overlap without semantic match               │
│    - Adjacent but distinct domains                        │
│    - Different operational levels                         │
│    - Generic administrative overlap                       │
├───────────────────────────────────────────────────────────┤
│ 5. OUTPUT REQUIREMENTS                                    │
│    - JSON format: {"relevant_node_ids": [...]}           │
│    - Quality standards: Recall over precision             │
└───────────────────────────────────────────────────────────┘
```

### System Prompt

```python
system_prompt = """You are a senior policy analyst with expertise in document 
classification, operational planning, and cross-domain reasoning. You excel at 
distinguishing between superficially similar but fundamentally different content 
domains. Your analyses are precise, systematic, and follow structured evaluation 
frameworks."""
```

**Temperature**: 0.2 (low variability for consistent filtering)

### Evaluation Examples

#### Example 1: Valid Match

**Problem**: "Develop emergency triage protocols for mass casualty events"

**Node**:
```
Title: Emergency Triage Protocol
Summary: Describes START triage system for rapid categorization of patients 
during mass casualty incidents. Includes color-coded priority levels and 
assessment procedures...
```

**Evaluation**:
- ✅ Domain Match: Emergency care
- ✅ Functional Alignment: Triage procedures
- ✅ Actionability: Describes specific procedures
- ✅ Contextual Fit: Mass casualty scenario
- ✅ Stakeholder Alignment: Emergency personnel

**Result**: **INCLUDED**

#### Example 2: False Positive (Rejected)

**Problem**: "Develop supply chain protocols for emergency logistics"

**Node**:
```
Title: Clinical Triage Procedures
Summary: Guidelines for clinical assessment and prioritization of patients 
in emergency departments. Covers vital signs monitoring and treatment 
allocation...
```

**Evaluation**:
- ❌ Domain Match: Clinical care vs. logistics
- ❌ Functional Alignment: Patient care vs. supply management
- ✅ Actionability: Contains procedures
- ❌ Contextual Fit: Different operational domain
- ❌ Stakeholder Alignment: Clinicians vs. logistics staff

**Result**: **REJECTED** (Domain mismatch)

---

## Batch Processing

### Configuration

```python
# In config/settings.py
analyzer_phase2_batch_threshold: int = Field(
    default=50, 
    env="ANALYZER_PHASE2_BATCH_THRESHOLD"
)
analyzer_phase2_batch_size: int = Field(
    default=20, 
    env="ANALYZER_PHASE2_BATCH_SIZE"
)
```

### Tuning Guidelines

| Scenario | Threshold | Batch Size | Rationale |
|----------|-----------|------------|-----------|
| Small KnowledgeBase | 100 | 30 | Fewer nodes, larger batches |
| Large KnowledgeBase | 50 | 20 | More nodes, smaller batches |
| Fast LLM | 75 | 25 | Can handle more per call |
| Slow LLM | 40 | 15 | Reduce individual call size |

### Performance Metrics

**Example Execution** (3 refined queries, 120 total nodes):

```
Query 1: 45 nodes → Single call → 8 relevant IDs (3.2s)
Query 2: 52 nodes → Batched (3 batches) → 12 relevant IDs (9.7s)
Query 3: 23 nodes → Single call → 5 relevant IDs (2.8s)

Total: 25 unique node IDs extracted in 15.7s
```

---

## Configuration

### Environment Variables

```bash
# Batch Processing
ANALYZER_PHASE2_BATCH_THRESHOLD=50  # When to enable batching
ANALYZER_PHASE2_BATCH_SIZE=20       # Nodes per batch

# RAG Query Settings
TOP_K_RESULTS=20                    # Base number of results (×2 in Phase 2)

# LLM Configuration
ANALYZER_PROVIDER=ollama            # LLM provider
ANALYZER_MODEL=gpt-oss:20b         # Model for evaluation
ANALYZER_TEMPERATURE=0.1            # Generation temperature
```

### Settings Access in Code

```python
from config.settings import get_settings

settings = get_settings()
batch_threshold = settings.analyzer_phase2_batch_threshold
batch_size = settings.analyzer_phase2_batch_size
top_k = settings.top_k_results
```

---

## Integration with RAG Systems

### HybridRAG Query

Phase 2 leverages the **HybridRAG** system with specific parameters:

```python
results = self.unified_rag.query(
    query,
    strategy="hybrid",  # Key: combines semantic + structural search
    top_k=self.settings.top_k_results * 2
)
```

### Strategy Breakdown

**"hybrid" Strategy**:
1. **Semantic Search**: Queries summary embeddings in Neo4j using cosine similarity
2. **Keyword Search**: Uses graph structure for term matching
3. **RRF Fusion**: Combines results using Reciprocal Rank Fusion
4. **MMR Diversity**: Applies Maximal Marginal Relevance to reduce redundancy

### Result Format

Each result from HybridRAG:

```python
{
    'text': 'Full section content...',
    'score': 0.87,  # Similarity score (0.0-1.0)
    'metadata': {
        'node_id': 'doc5_section_3_2',
        'title': 'Emergency Response Protocols',
        'summary': 'This section describes...',
        'document_name': 'Emergency Operations Plan',
        'level': 3,
        'line': 145
    }
}
```

### Why "hybrid" Mode?

- **Semantic Precision**: Embeddings capture meaning beyond keywords
- **Structural Context**: Graph relationships preserve document hierarchy
- **Diversity**: MMR prevents retrieving duplicate information
- **Robustness**: Fusion ensures relevant results even if one method fails

---

## Error Handling

### Query Execution Errors

```python
try:
    results = self.unified_rag.query(...)
except Exception as e:
    logger.error(f"Error executing query {idx}: {e}")
    continue  # Skip to next query
```

**Behavior**: Logs error and continues with remaining queries

### LLM Evaluation Errors

```python
try:
    result = self.llm.generate_json(...)
    # ... parse result ...
except Exception as e:
    logger.error(f"Error identifying relevant nodes: {e}")
    return [node['id'] for node in nodes[:5]]  # Fallback
```

**Fallback Strategy**: Returns top 5 nodes by RAG score

### Batch Processing Errors

```python
try:
    relevant_ids = self._identify_relevant_nodes(batch, problem_statement)
    all_relevant_ids.extend(relevant_ids)
except Exception as e:
    logger.error(f"Error processing batch starting at {i}: {e}")
    continue  # Skip failed batch, continue with next
```

**Behavior**: Isolated batch failure doesn't crash the entire process

### Empty Results

```python
if not refined_queries:
    logger.warning("No refined queries provided, cannot extract node IDs")
    return []
```

**Graceful Degradation**: Returns empty list, allows workflow to continue

---

## Performance Optimization

### 1. Over-Retrieval Strategy

```python
top_k=self.settings.top_k_results * 2  # Fetch 2× results
```

**Purpose**: Retrieve extra candidates knowing LLM will filter ~50-70%

**Trade-off**: More RAG computation vs. better recall after filtering

### 2. Summary Truncation

```python
'summary': summary[:5000] if summary else 'No summary'
```

**Purpose**: Limit token usage per node (5000 chars ≈ 1200 tokens)

**Impact**: 
- Faster LLM calls
- Lower cost
- Maintains essential context

### 3. Progressive Batching

```python
if len(nodes) > batch_threshold:
    # Batch processing
else:
    # Single call
```

**Purpose**: Only batch when necessary to avoid overhead

### 4. In-Memory Deduplication

```python
unique_node_ids = list(set(all_node_ids))
```

**Purpose**: Fast O(n) deduplication using Python sets

### 5. Logging Strategy

```python
logger.info(f"Query {idx} yielded {len(relevant_ids)} relevant node IDs")
logger.info(f"Phase 2 complete: {len(unique_node_ids)} unique node IDs")
```

**Purpose**: Track progress without overwhelming logs

---

## Examples

### Example 1: Small Result Set (No Batching)

**Input**:
- Refined queries: 2
- Problem: "Hand hygiene protocols in hospitals"

**Execution**:
```
Query 1: 18 nodes → Single LLM call → 7 relevant
Query 2: 22 nodes → Single LLM call → 9 relevant
Deduplication: 14 unique node IDs
```

**Output**: `["doc1_section_2", "doc1_section_3_1", ..., "doc2_section_5"]`

---

### Example 2: Large Result Set (Batching)

**Input**:
- Refined queries: 4
- Problem: "Emergency preparedness for mass casualty incidents"

**Execution**:
```
Query 1: 45 nodes → Single LLM call → 12 relevant
Query 2: 78 nodes → Batched (4 batches of 20) → 23 relevant
Query 3: 34 nodes → Single LLM call → 8 relevant
Query 4: 61 nodes → Batched (4 batches of 20) → 18 relevant
Deduplication: 52 unique node IDs
```

**Batch Processing Detail for Query 2**:
```
  Batch 1 (nodes 0-20):   6 relevant IDs
  Batch 2 (nodes 20-40):  8 relevant IDs
  Batch 3 (nodes 40-60):  5 relevant IDs
  Batch 4 (nodes 60-78):  4 relevant IDs
  Total:                 23 relevant IDs
```

**Output**: List of 52 node IDs

---

### Example 3: Error Recovery

**Scenario**: One query fails, others succeed

**Execution**:
```
Query 1: 38 nodes → ✅ Success → 9 relevant
Query 2: 52 nodes → ❌ RAG connection error → Skipped
Query 3: 41 nodes → ✅ Success → 11 relevant
Query 4: 27 nodes → ✅ Success → 6 relevant
Deduplication: 24 unique node IDs
```

**Result**: Continues processing, logs error, returns partial results

---

## Troubleshooting

### Issue 1: Too Many Irrelevant Nodes

**Symptoms**: Phase 3 receives nodes from unrelated domains

**Diagnosis**:
```python
# Check LLM evaluation prompt
logger.info(f"Nodes being evaluated: {len(nodes)}")
if self.markdown_logger:
    self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
```

**Solutions**:
1. Lower `temperature` in LLM call (more deterministic filtering)
2. Add domain keywords to Phase 1 query generation
3. Review LLM system prompt for domain-aware instructions

### Issue 2: Too Few Nodes Returned

**Symptoms**: Phase 2 returns < 5 node IDs despite large knowledge base

**Diagnosis**:
```python
# Check RAG retrieval
logger.info(f"Query returned {len(results)} results")
logger.info(f"Nodes extracted: {len(nodes)}")
logger.info(f"Relevant IDs after LLM: {len(relevant_ids)}")
```

**Solutions**:
1. Increase `top_k` multiplier: `top_k=self.settings.top_k_results * 3`
2. Broaden Phase 1 query terms (less specific keywords)
3. Check if embeddings exist: `python scripts/verify_embeddings.py`

### Issue 3: Batch Processing Never Triggers

**Symptoms**: All queries processed in single calls despite large results

**Check Configuration**:
```bash
echo $ANALYZER_PHASE2_BATCH_THRESHOLD  # Should be < typical result count
```

**Solution**: Lower threshold in `.env`:
```bash
ANALYZER_PHASE2_BATCH_THRESHOLD=30  # Instead of 50
```

### Issue 4: LLM Evaluation Timeouts

**Symptoms**: Batch processing hangs or times out

**Solutions**:
1. Reduce batch size:
   ```bash
   ANALYZER_PHASE2_BATCH_SIZE=10  # Instead of 20
   ```
2. Truncate summaries more aggressively:
   ```python
   'summary': summary[:2000]  # Instead of 5000
   ```
3. Switch to faster model:
   ```bash
   ANALYZER_MODEL=llama3.1:8b  # Instead of gpt-oss:20b
   ```

### Issue 5: Duplicate Node IDs

**Symptoms**: Same node ID appears multiple times in output

**Expected Behavior**: Final deduplication should prevent this

**Verification**:
```python
logger.info(f"Total IDs before dedup: {len(all_node_ids)}")
logger.info(f"Unique IDs after dedup: {len(unique_node_ids)}")
```

**If Issue Persists**: Check for string formatting inconsistencies in node IDs

---

## Advanced Topics

### Custom Evaluation Criteria

To modify the LLM evaluation logic, edit the prompt in `_identify_relevant_nodes`:

```python
prompt = f"""You are an expert document analyst...

## Evaluation Framework

### Custom Criterion: Technical Depth
For engineering protocols, require:
- Specific technical parameters
- Quantitative thresholds
- Measurable outcomes

{node_context}

...
"""
```

### Alternative Scoring Methods

Instead of binary include/exclude, use weighted scoring:

```python
# Modify output format in prompt
{
  "node_scores": [
    {"node_id": "doc1_section_2", "relevance_score": 0.85},
    {"node_id": "doc1_section_3", "relevance_score": 0.62}
  ]
}

# Filter by threshold
relevant_ids = [
    item['node_id'] for item in result['node_scores'] 
    if item['relevance_score'] > 0.7
]
```

### Integration with Phase 3

Node IDs from Phase 2 are passed to Phase 3 agent:

```python
# In workflows/orchestration.py
phase2_output = analyzer.execute(context)
node_ids = phase2_output['node_ids']

# Phase 3 uses these for deep analysis
phase3_context = phase3_agent.analyze_subjects(
    node_ids=node_ids,
    problem_statement=problem_statement
)
```

---

## Best Practices

### 1. Query Quality Matters

Phase 2 effectiveness depends on Phase 1 query quality:

```python
# Good Phase 1 Query
"emergency triage mass casualty protocols resource allocation"

# Poor Phase 1 Query
"emergency management procedures and guidelines"
```

### 2. Monitor Filtering Rates

Track how many nodes pass LLM evaluation:

```python
initial_count = len(nodes)
relevant_count = len(relevant_ids)
filter_rate = (initial_count - relevant_count) / initial_count
logger.info(f"Filtered {filter_rate:.1%} of nodes")
```

**Expected**: 50-70% filtering rate
**Too high (>80%)**: Queries may be too specific
**Too low (<30%)**: Evaluation may be too lenient

### 3. Balance Precision and Recall

Phase 2 design favors **recall over precision**:

```python
# From evaluation framework
"Better to include a potentially relevant node than miss an important one"
```

**Rationale**: Phase 3 provides additional filtering; Phase 2 should cast a wide net

### 4. Use Markdown Logger

Enable detailed logging for debugging:

```python
if self.markdown_logger:
    self.markdown_logger.log_llm_call(prompt, result, temperature=0.2)
```

Generates comprehensive logs for later analysis

### 5. Test with Representative Queries

Validate Phase 2 with domain-specific test cases:

```bash
python scripts/test_analyzer_fix.py
```

Check for:
- ✓ Varied similarity scores
- ✓ No cross-domain contamination
- ✓ Scores in valid range [0.0, 1.0]

---

## Conclusion

Phase 2 of the Analyzer Agent is a sophisticated **query execution and node filtering system** that bridges high-level document discovery (Phase 1) with deep content analysis (Phase 3). Its hybrid RAG approach, LLM-based evaluation framework, and scalable batch processing make it robust for large knowledge bases while maintaining high relevance standards.

**Key Takeaways**:
- Uses hybrid semantic + structural search for comprehensive retrieval
- Applies structured 5-criterion evaluation framework to prevent false positives
- Scales to large result sets through configurable batch processing
- Provides graceful error handling and fallback mechanisms
- Optimized for recall (capture relevant content) while filtering noise

For questions or issues, refer to the troubleshooting section or examine the detailed logs generated during execution.

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-16  
**Maintainer**: ActionPlan System Team  
**Related Documentation**:
- `ANALYZER_AGENT_PHASE1_DOCUMENTATION.md` (if exists)
- `README.md` (System overview)
- `config/settings.py` (Configuration reference)
- `rag_tools/hybrid_rag.py` (RAG implementation)

