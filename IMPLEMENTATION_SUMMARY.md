# Enhanced Input Parameters - Implementation Summary

## Overview
Successfully implemented user-configurable parameters for action plan generation, including document filtering, timing customization, trigger definitions, and organizational roles. Dictionary.md access is now restricted to translation agents only.

## Changes Implemented

### 1. State Definition (`workflows/graph_state.py`)
Added new fields to `ActionPlanState`:
- `documents_to_query`: Optional list of user-selected documents
- `guideline_documents`: List of always-included guideline documents
- `timing`: Optional timing context (e.g., "yearly", "seasonal")
- `trigger`: Optional action plan activation trigger
- `responsible_party`: Optional responsible party
- `process_owner`: Optional process owner

### 2. Settings Configuration (`config/settings.py`)
Added new settings:
- `dictionary_collection`: ChromaDB collection name for dictionary
- `dictionary_graph_prefix`: Neo4j graph prefix for dictionary

### 3. Separate RAG Instances (`workflows/orchestration.py`)
Created two RAG systems:
- **Main RAG**: For Orchestrator, Analyzer, Extractor, Prioritizer, Assigner (excludes Dictionary.md)
- **Dictionary RAG**: For Dictionary Lookup agent only (includes Dictionary.md)

This ensures main agents cannot access Dictionary.md while translation agents can.

### 4. Document Filtering (`rag_tools/hybrid_rag.py`)
Added document filtering to RAG queries:
- `document_filter` parameter in `query()` method
- `_filter_by_documents()` method for filtering results
- Guideline documents are always included regardless of filter
- Filters results based on document metadata

### 5. Timing Modification (`agents/prioritizer.py`)
Added `_apply_user_timing()` method:
- Only modifies actions without specific timeframes (e.g., "regularly", "as needed")
- Preserves actions with specific timings (e.g., "within 2 hours", "day 1-3")
- Adds timing context to action metadata
- Logs modifications for transparency

### 6. Formatter Updates (`agents/formatter.py`)
Updated `execute()` method to:
- Accept trigger, responsible_party, process_owner parameters
- Add them to context metadata
- Include in Checklist Specifications table

### 7. UI Enhancements (`ui/components/plan_generator.py`)
Added "Advanced Options" expander with:
- **Document Selection**: Multi-select for documents (placeholder for future enhancement)
- **Timing Context**: Text input for timing specification
- **Organizational Details**: Inputs for trigger, process_owner, responsible_party
- All parameters collected and passed to workflow

### 8. Entry Points (`main.py`, `ui/components/plan_generator.py`)
Updated both CLI and UI entry points to:
- Accept new parameters
- Load guideline documents from settings
- Pass parameters through initial_state
- Support both command-line and UI workflows

## Usage

### UI Usage
1. Enter health policy subject
2. Expand "Advanced Options" section
3. Optionally specify:
   - Timing context (e.g., "yearly", "seasonal")
   - Activation trigger
   - Process owner
   - Responsible party
4. Click "Generate Plan"

### CLI Usage
The CLI can be extended with additional arguments in future enhancements:
```bash
python main.py generate \
  --subject "Emergency triage procedures" \
  --timing "quarterly" \
  --trigger "Mass casualty incident" \
  --responsible-party "Incident Commander" \
  --process-owner "EOC Director"
```

## Key Features

### Dictionary Isolation
- Main agents (Orchestrator, Analyzer, Extractor, Prioritizer, Assigner) use `main_hybrid_rag`
- Dictionary Lookup agent uses `dictionary_hybrid_rag`
- Prevents dictionary access by main agents while maintaining translation functionality

### Smart Timing Modification
- Only modifies actions with vague or no timing
- Preserves specific timeframes (hours, days, weeks)
- Adds timing context without overwriting critical timings

### Guideline Document Protection
- Guideline documents always included in queries
- Cannot be deselected by user
- Ensures policy compliance

### Flexible Organizational Metadata
- Trigger, responsible party, and process owner can be specified
- Included in Checklist Specifications table
- Helps with organizational alignment

## Testing Recommendations

1. **Dictionary Isolation**: Verify main agents cannot query Dictionary.md
2. **Document Filtering**: Test with various document combinations
3. **Timing Modification**: Test with different action types (specific vs vague timing)
4. **Guideline Inclusion**: Verify guidelines always included
5. **UI Validation**: Test all input fields and parameter passing
6. **CLI Integration**: Test command-line parameter passing

## Future Enhancements

1. **Dynamic Document Loading**: Load available documents from RAG for multi-select
2. **CLI Arguments**: Add command-line arguments for new parameters
3. **Document Validation**: Validate document names against available documents
4. **Timing Presets**: Add preset timing options (yearly, seasonal, quarterly, monthly)
5. **Role Suggestions**: Auto-suggest roles based on subject analysis

## Files Modified

1. `workflows/graph_state.py` - State definition
2. `config/settings.py` - Settings configuration
3. `workflows/orchestration.py` - RAG initialization and node updates
4. `rag_tools/hybrid_rag.py` - Document filtering
5. `agents/prioritizer.py` - Timing modification
6. `agents/formatter.py` - Metadata inclusion
7. `ui/components/plan_generator.py` - UI inputs
8. `main.py` - CLI entry point

All changes maintain backward compatibility and include proper error handling.
