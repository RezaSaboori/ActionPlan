# Multi-Phase Analyzer System v3.0 - Implementation Complete

**Date:** October 15, 2025  
**Status:** ✅ Implementation Complete

## Overview

The Multi-Phase Analyzer System represents a complete redesign of the analysis workflow, introducing:

1. **Analyzer Agent (2-Phase)**: Context Building → Subject Identification
2. **phase3 Agent (Deep Analysis)**: LLM-based graph traversal with relevance scoring
3. **Enhanced Extractor**: Multi-subject processing with structured who/when/what extraction

## Architecture Changes

### New Workflow Flow

```
Orchestrator → Analyzer (2-Phase) → phase3 → Extractor → Prioritizer → Assigner → Formatter
     ↓              ↓                     ↓            ↓
   Topics    Subjects (3-8)     Subject Nodes    Actions (who/when/what)
```

### Component Details

#### 1. GraphRAG Extensions (`rag_tools/graph_rag.py`)

**New Methods:**
- `get_parent_documents(topics)` - Find Document nodes by topics
- `get_introduction_nodes(doc_name)` - Get first-level headings
- `get_node_by_id(node_id)` - Retrieve specific node
- `navigate_upward(node_id, levels)` - Navigate N levels up
- `consolidate_branches(nodes)` - Deduplicate nodes
- `get_children(node_id)` - Get direct children
- `read_node_content(...)` - Read full content by lines
- `get_section_hierarchy_string(node_id)` - Get hierarchical path

#### 2. Analyzer Agent (`agents/analyzer.py`)

**Phase 1: Context Building**
- Finds parent documents based on topics from Orchestrator
- Reads introduction nodes and summaries
- Samples first/last lines for context
- Builds document structure map

**Phase 2: Subject Identification**
- Uses LLM to analyze user subject + context
- Generates 3-8 specific subjects for deep analysis
- Example: "hand hygiene" → ["handwashing protocols", "sanitizer use", "PPE requirements"]

**Input:**
```python
{
    "subject": "emergency triage protocols",
    "topics": ["triage", "emergency"],
    "structure": {...}
}
```

**Output:**
```python
{
    "context_map": {
        "documents": [...],
        "structure_summary": "..."
    },
    "identified_subjects": ["triage classification", "patient flow", ...]
}
```

#### 3. phase3 Agent (`agents/phase3.py`)

**Step 1: Initial Node Selection**
- Queries RAG with subject
- Gets top-K nodes
- Navigates 2 levels up, selects parent nodes
- Consolidates branches

**Step 2: Branch Traversal & Scoring**
- Scores each node using LLM (0-1 scale)
- Threshold-based traversal (default: 0.7)
- Recursive depth-limited exploration (default: max 3 levels)
- Tracks visited nodes to avoid cycles

**LLM Scoring:**
- 0.0-0.3: Not relevant
- 0.4-0.6: Somewhat relevant
- 0.7-0.9: Highly relevant
- 1.0: Extremely relevant

**Input:**
```python
{
    "identified_subjects": ["triage classification", "patient flow"]
}
```

**Output:**
```python
{
    "subject_nodes": [
        {
            "subject": "triage classification",
            "nodes": [
                {"id": "...", "title": "...", "relevance_score": 0.85, ...},
                ...
            ]
        },
        ...
    ]
}
```

#### 4. Enhanced Extractor (`agents/extractor.py`)

**Multi-Subject Processing:**
- Processes each subject separately
- Reads full node content using line numbers
- Extracts actions in structured format
- Can consult Quality Agent
- Can consult Orchestrator for clarifications

**Action Format (who/when/what):**
```python
{
    "action": "Triage Team Lead establishes triage area within 30 minutes",
    "who": "Triage Team Lead",
    "when": "Within 30 minutes of incident notification",
    "what": "Establish primary triage area with designated zones",
    "source_node": "doc_h2_3",
    "source_lines": "145-167",
    "full_context": "...",
    "subject": "triage area setup"
}
```

**Input:**
```python
{
    "subject_nodes": [{subject: "...", nodes: [...]}, ...]
}
```

**Output:**
```python
{
    "subject_actions": [
        {
            "subject": "triage classification",
            "actions": [...]
        },
        ...
    ]
}
```

## Configuration

### New Environment Variables (`.env`)

```bash
# phase3 Configuration
phase3_SCORE_THRESHOLD=0.7
phase3_MAX_DEPTH=3
phase3_INITIAL_TOP_K=10

# Analyzer Configuration
ANALYZER_CONTEXT_SAMPLE_LINES=10
```

### Settings Fields (`config/settings.py`)

```python
phase3_score_threshold: float = 0.7
phase3_max_depth: int = 3
phase3_initial_top_k: int = 10
analyzer_context_sample_lines: int = 10
```

## New Prompts

1. **ANALYZER_PHASE1_PROMPT** - Context building instructions
2. **ANALYZER_PHASE2_PROMPT** - Subject identification with examples
3. **ANALYZER_D_SCORING_PROMPT** - Node relevance scoring guidelines
4. **EXTRACTOR_MULTI_SUBJECT_PROMPT** - Who/when/what extraction format

Access via: `get_prompt("analyzer_phase2")`, etc.

## Workflow State Extensions

**New State Fields:**
```python
topics: List[str]                      # From Orchestrator
context_map: Dict[str, Any]            # Analyzer Phase 1
identified_subjects: List[str]         # Analyzer Phase 2
subject_nodes: List[Dict[str, Any]]    # phase3
subject_actions: List[Dict[str, Any]]  # Enhanced Extractor
```

## Quality Control Integration

- Analyzer → Quality Check → phase3
- phase3 → Quality Check → Extractor
- Extractor can consult Quality Agent per subject
- Quality feedback loops with retry logic (max 3 retries)

## Testing

**Run comprehensive tests:**
```bash
python test_analyzer_system.py
```

**Test Coverage:**
1. GraphRAG navigation methods
2. Analyzer 2-phase workflow
3. phase3 scoring and traversal
4. Extractor multi-subject processing
5. Full workflow integration

## Usage Example

```python
from workflows.orchestration import create_workflow
from workflows.graph_state import ActionPlanState

workflow = create_workflow()

state: ActionPlanState = {
    "subject": "emergency triage protocols",
    "current_stage": "start",
    "retry_count": {},
    "errors": [],
    "metadata": {}
}

result = workflow.invoke(state)

# Access results
topics = result["topics"]
subjects = result["identified_subjects"]
subject_nodes = result["subject_nodes"]
subject_actions = result["subject_actions"]
final_plan = result["final_plan"]
```

## Performance Considerations

**LLM Calls per Subject:**
- Phase 2 (Subject ID): 1 call
- phase3 (Scoring): Variable (depends on graph depth & threshold)
- Extractor: 1 call per node

**Optimization Tips:**
1. Adjust `phase3_SCORE_THRESHOLD` to control traversal depth
2. Reduce `phase3_MAX_DEPTH` for faster processing
3. Limit `phase3_INITIAL_TOP_K` for fewer initial nodes
4. Batch LLM calls where possible (future enhancement)

## Migration from v2.1

**Backward Compatibility:**
- Legacy state fields maintained (`extracted_actions`, `refined_actions`)
- Extractor consolidates `subject_actions` into `refined_actions`
- Downstream agents (Prioritizer, Assigner) unchanged

**New Features:**
- Topic-based document discovery
- Multi-subject parallel analysis
- Structured action extraction (who/when/what)
- LLM-based relevance scoring
- Graph-guided deep traversal

## Key Benefits

1. **More Focused Analysis**: Breaks broad subjects into specific, actionable topics
2. **Intelligent Traversal**: LLM scoring prevents irrelevant branch exploration
3. **Better Traceability**: Full content retrieval with exact line numbers
4. **Structured Actions**: Who/when/what format for implementation clarity
5. **Scalable**: Processes multiple subjects in parallel
6. **Quality Integrated**: Built-in quality checks and refinement

## Files Modified

**New Files:**
- `agents/phase3.py` (247 lines)
- `test_analyzer_system.py` (395 lines)

**Modified Files:**
- `rag_tools/graph_rag.py` (+230 lines)
- `agents/analyzer.py` (complete rewrite, 252 lines)
- `agents/extractor.py` (complete rewrite, 294 lines)
- `workflows/graph_state.py` (+6 fields)
- `workflows/orchestration.py` (+50 lines, new nodes)
- `config/prompts.py` (+170 lines, 4 new prompts)
- `config/settings.py` (+4 fields)
- `.env` (+7 lines)

**Total Lines Added: ~1,400**

## Next Steps

1. ✅ Run comprehensive tests: `python test_analyzer_system.py`
2. ✅ Verify database connectivity (Neo4j, ChromaDB)
3. ⏳ Test with real documents and subjects
4. ⏳ Monitor LLM scoring quality
5. ⏳ Optimize threshold and depth parameters
6. ⏳ Generate sample action plan
7. ⏳ Document edge cases and limitations

## Known Limitations

1. **LLM Scoring Variability**: Scores may vary between runs (temperature=0.1 helps)
2. **Graph Cycles**: Handled via visited node tracking
3. **Source Path Discovery**: Requires source field in node metadata
4. **Performance**: Deep traversal with many nodes can be slow
5. **Context Window**: Very deep graphs may hit context limits

## Support & Troubleshooting

**Common Issues:**

1. **No subjects identified**
   - Check if topics are valid
   - Verify documents exist in database
   - Check LLM connectivity

2. **Low relevance scores**
   - Adjust `phase3_SCORE_THRESHOLD`
   - Verify node summaries are meaningful
   - Check subject specificity

3. **No actions extracted**
   - Ensure nodes have source paths
   - Verify content is readable
   - Check node line ranges

**Debug Logging:**
```bash
LOG_LEVEL=DEBUG python main.py generate --subject "your subject"
```

---

**Version:** 3.0  
**Implemented:** October 15, 2025  
**Status:** ✅ Ready for Testing

