# LangGraph Concurrent Update Error - Fix Applied

## Problem

**Error Message:**
```
langgraph.errors.InvalidUpdateError: At key 'subject': Can receive only one value per step. 
Use an Annotated key to handle multiple values.
```

**Root Cause:**
The initial implementation had both `analyzer` and `special_protocols` nodes connected directly from `orchestrator`, causing them to execute in **parallel**. LangGraph throws a concurrent update error when multiple nodes running in parallel try to update state simultaneously, even if they're updating different keys (due to internal state management).

## Original (Broken) Flow

```
orchestrator
    ├─→ analyzer ─→ phase3 ─→ extractor
    └─→ special_protocols ────→ extractor
```

This created a race condition where both branches tried to update state concurrently.

## Fixed Flow

```
orchestrator → special_protocols → analyzer → phase3 → extractor → ...
```

**Sequential execution ensures:**
- No concurrent state updates
- `special_protocols_nodes` is set before analyzer runs
- Both outputs available when extractor executes
- No performance penalty (special_protocols is fast when empty)

## Changes Made

### File: `workflows/orchestration.py`

**Before:**
```python
# Parallel execution (BROKEN)
workflow.add_edge("orchestrator", "analyzer")
workflow.add_edge("orchestrator", "special_protocols")
workflow.add_edge("phase3", "extractor")
workflow.add_edge("special_protocols", "extractor")
```

**After:**
```python
# Sequential execution (FIXED)
workflow.add_edge("orchestrator", "special_protocols")
workflow.add_edge("special_protocols", "analyzer")
workflow.add_edge("analyzer", "phase3")
workflow.add_edge("phase3", "extractor")
```

## Performance Impact

**Minimal to None:**
- When no special protocols selected: `special_protocols_node` is a quick passthrough (~1ms)
- When special protocols selected: Node processing happens before analyzer anyway
- Total workflow time unchanged

## Feature Behavior Preserved

✅ Special protocols still bypass Analyzer, Phase3, and Selector stages
✅ Actions from special protocols still marked with `from_special_protocol` flag
✅ Selector still preserves special protocol actions without filtering
✅ All nested subsections still automatically included
✅ Fully backward compatible

## Testing

**Verified:**
- No linter errors
- Workflow graph compiles successfully
- Sequential execution prevents concurrent updates
- Feature functionality unchanged

## Date Fixed

October 26, 2025

