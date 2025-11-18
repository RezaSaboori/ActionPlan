# Downstream Impacts of Extractor Refactor

## Summary
The extractor agent has been successfully refactored to match the new prompt schema. However, several downstream agents that consume extractor output will need updates to work with the new structure.

## Changes Made to Extractor

### New Output Structure
```python
{
    "actions": List[Dict],  # All actions with flags (actor_flagged, timing_flagged)
    "formulas": List[Dict],  # Separate formulas with variables_definition
    "tables": List[Dict],  # Non-action tables only (extraction_flag=False)
    "dependencies": List[Dict],  # NEW: Dependencies/resources/budgets
    "metadata": Dict  # Statistics
}
```

### Removed Fields
- `complete_actions` - merged into `actions`
- `flagged_actions` - merged into `actions`
- `subject_actions` - no longer needed
- `actions_by_actor` - no longer generated
- `formatted_output` - no longer generated

### Action Schema Changes
- Removed: `what`, `context`, `full_context`, `original_formula_reference`
- Kept: `who`, `when`, `action`, `reference`, `timing_flagged`, `actor_flagged`

### Formula Schema Changes
- Removed: `computation_example`, `sample_result`, `related_actions`, `merged_into_actions`
- Added: `variables_definition` (Dict)
- Kept: `formula`, `formula_context`, `reference`

### Table Schema Changes
- Removed: `headers`, `rows`, `extracted_actions`
- Added: `extraction_flag` (Boolean)
- Kept: `table_title`, `table_type`, `markdown_content`, `reference`

## Agents Requiring Updates

### 1. Deduplicator Agent (`agents/deduplicator.py`)

**Current Behavior:**
- Expects `complete_actions` and `flagged_actions` as separate lists
- Processes them independently
- Returns `refined_complete_actions` and `refined_flagged_actions`

**Required Changes:**
1. Update `execute()` to accept single `actions` list
2. Filter or group actions based on flags if needed
3. Return single `refined_actions` list
4. Update all references to `complete_actions` and `flagged_actions`
5. Update prompt templates to work with unified action structure

**Files to Update:**
- `agents/deduplicator.py` - Main logic
- `config/prompts.py` - DEDUPLICATOR_USER_PROMPT_TEMPLATE

### 2. Selector Agent (`agents/selector.py`)

**Status:** Needs investigation

**Likely Changes:**
- Update to work with single `actions` list
- Adjust filtering logic for new flag structure
- Update input/output schemas

### 3. Workflow Orchestration (`workflows/orchestration.py`)

**Status:** ✅ UPDATED

Changes made:
- Updated `extractor_node()` to use new output structure
- Updated markdown logging
- Removed references to old fields

### 4. Graph State (`workflows/graph_state.py`)

**Status:** ✅ UPDATED

Changes made:
- Updated `ActionPlanState` to reflect new structure
- Removed legacy fields
- Added `dependencies` field

### 5. Other Potential Consumers

**Need to check:**
- `agents/prioritizer.py` - May consume actions
- `agents/assigner.py` - May consume actions
- `agents/formatter.py` - May format actions
- `agents/quality_checker.py` - May validate actions
- UI components in `ui/components/` - May display actions

## Migration Strategy for Downstream Agents

### For Each Agent:

1. **Update Input Schema**
   - Change from `complete_actions` + `flagged_actions` to single `actions` list
   - Add support for new fields: `formulas`, `dependencies`

2. **Update Processing Logic**
   - Use `actor_flagged` and `timing_flagged` instead of separate lists
   - Access `action` field instead of `what` field
   - Handle formulas separately if needed

3. **Update Output Schema**
   - Return single list or maintain flag-based grouping as needed
   - Ensure downstream compatibility

4. **Update Prompts**
   - Update any LLM prompts that reference old schema
   - Use new field names in examples and instructions

5. **Update Tests**
   - Update test data to match new schema
   - Add tests for new fields (formulas, dependencies)

## Testing Checklist

After updating each agent:

- [ ] Agent accepts new extractor output format
- [ ] Agent processes actions with flags correctly
- [ ] Agent handles formulas appropriately
- [ ] Agent handles dependencies (if relevant)
- [ ] Agent output matches expected schema
- [ ] Integration tests pass
- [ ] No references to old field names remain

## Notes

- Formulas are now separate, not integrated into actions
- Tables only include non-action tables (extraction_flag=False)
- Dependencies are a new category that needs handling
- All actions are in a single list with boolean flags

## Priority Order for Updates

1. ✅ Extractor (DONE)
2. ✅ Orchestration (DONE)
3. ✅ State (DONE)
4. Deduplicator (HIGH - directly consumes extractor output)
5. Selector (HIGH - may depend on deduplicator)
6. Other agents (MEDIUM - indirect consumers)
7. UI components (LOW - display layer)

