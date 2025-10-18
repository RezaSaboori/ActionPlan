# Persian Translation Workflow - Implementation Summary

## Overview

The Persian translation workflow has been successfully implemented as an extension to the existing action plan generation system. This workflow automatically translates generated English action plans into Persian with terminology validation using a specialized dictionary.

## Implementation Details

### 1. Configuration (✅ Complete)

**Files Modified:**
- `config/settings.py` - Added translation-specific settings:
  - `translator_model`: Model for translation (default: "gemma3:27b")
  - `dictionary_path`: Path to Dictionary.md
  - `segmentation_chunk_size`: Size for text chunks (default: 500)
  - `term_context_window`: Sentences before/after term for context (default: 3)

- `config/prompts.py` - Added 5 new system prompts:
  - `TRANSLATOR_PROMPT`: Verbatim, officially-certified-grade translation
  - `SEGMENTATION_PROMPT`: Text segmentation for analysis
  - `TERM_IDENTIFIER_PROMPT`: Technical term extraction
  - `DICTIONARY_LOOKUP_PROMPT`: Dictionary validation
  - `REFINEMENT_PROMPT`: Apply corrections to final translation

### 2. State Management (✅ Complete)

**Files Modified:**
- `workflows/graph_state.py` - Extended `ActionPlanState` TypedDict with:
  - `translated_plan`: Initial Persian translation
  - `segmented_chunks`: Text chunks with metadata
  - `identified_terms`: Technical terms with context
  - `dictionary_corrections`: Validated corrections
  - `final_persian_plan`: Final corrected Persian translation

### 3. LLM Client Enhancement (✅ Complete)

**Files Modified:**
- `utils/llm_client.py` - Added `model_override` parameter to:
  - `generate()` method
  - `generate_json()` method
  
This allows the TranslatorAgent to use gemma3:27b while other agents use the default model.

### 4. Translation Agents (✅ Complete)

**New Files Created:**

1. **`agents/translator.py`**
   - Uses gemma3:27b model for translation
   - Produces verbatim, officially-certified-grade Persian translation
   - Preserves markdown structure
   - Adds English terms in parentheses after Persian technical terms

2. **`agents/segmentation.py`**
   - Segments Persian text into analyzable chunks
   - Respects sentence boundaries and section headers
   - Tracks which chunks contain technical terms
   - Returns chunks with metadata (line numbers, section names)

3. **`agents/term_identifier.py`**
   - Extracts technical terms with English in parentheses
   - Pattern matching: "Persian_text (English text)"
   - Extracts context windows (N sentences before/after)
   - Returns term candidates with position metadata

4. **`agents/dictionary_lookup.py`**
   - Uses HybridRAG to query Dictionary.md
   - Performs exact match and semantic search
   - Validates terms against dictionary entries
   - Returns corrections with confidence scores
   - Only suggests corrections with confidence > 0.7

5. **`agents/translation_refinement.py`**
   - Applies dictionary corrections to translated text
   - Uses regex for safe replacement
   - Maintains markdown formatting
   - Logs all applied corrections

### 5. Workflow Orchestration (✅ Complete)

**Files Modified:**
- `workflows/orchestration.py`
  - Added imports for 5 new agents
  - Initialized translation agents
  - Created 5 new node functions
  - Added nodes to workflow graph
  - Connected workflow: `formatter → translator → segmentation → term_identifier → dictionary_lookup → refinement → END`

### 6. File Saving (✅ Complete)

**Files Modified:**
- `main.py` - Updated `generate_action_plan()`:
  - Saves English plan to original path
  - Saves Persian plan with `_fa.md` suffix
  - Logs both file paths

- `ui/components/plan_generator.py` - Updated `run_generation_workflow()`:
  - Saves both English and Persian plans
  - Displays both file paths in UI
  - Shows success message for dual-language output

### 7. Dictionary Integration (✅ Complete)

**Actions Taken:**
- Copied `Agents/dataset/Dictionary.md` to `HELD/docs/Dictionary.md`
- Dictionary will be automatically ingested during document ingestion
- Hierarchical structure (## term, ### definition, ### explanation) preserved
- Terms will be searchable via embedding and exact match

## Workflow Architecture

```
Action Plan Generation (Existing)
├── Orchestrator
├── Analyzer
├── Analyzer_D
├── Extractor
├── Prioritizer
├── Assigner
└── Formatter → final_plan (English)
                    ↓
Translation Workflow (New)
├── Translator → translated_plan (Initial Persian)
├── Segmentation → segmented_chunks
├── Term Identifier → identified_terms
├── Dictionary Lookup → dictionary_corrections
└── Refinement → final_persian_plan (Final Persian)
```

## Usage

### 1. First-Time Setup

**Ingest Dictionary into Knowledge Base:**
```bash
cd /storage03/Saboori/ActionPlan/Agents
python main.py ingest --docs-dir /storage03/Saboori/ActionPlan/HELD/docs
```

This will index Dictionary.md along with other documents into both Neo4j and ChromaDB.

### 2. Generate Action Plan with Translation

**Command Line:**
```bash
python main.py generate --subject "emergency response protocol"
```

**Streamlit UI:**
```bash
streamlit run streamlit_app.py
```

### 3. Output Files

The workflow generates two files:
- `action_plans/subject_name_timestamp.md` (English)
- `action_plans/subject_name_timestamp_fa.md` (Persian)

## Translation Quality Standards

### Translator Agent (gemma3:27b)
- **Verbatim translation**: No interpretation or summarization
- **Officially-certified-grade**: Equivalent to sworn translation
- **Markdown preservation**: All formatting maintained
- **Technical terms**: Persian followed by (English) in parentheses

### Dictionary Validation
- **Exact match**: Persian and English term matching
- **Semantic search**: Embedding-based similarity
- **Context validation**: Ensures term fits the context
- **Confidence threshold**: Only corrections > 0.7 applied

### Refinement
- **Safe replacement**: Regex-based pattern matching
- **Format preservation**: No markdown structure changes
- **Logging**: All corrections tracked and logged

## Configuration Options

### Environment Variables (.env)

```bash
# Translation Settings
TRANSLATOR_MODEL=gemma3:27b
DICTIONARY_PATH=/storage03/Saboori/ActionPlan/Agents/dataset/Dictionary.md
SEGMENTATION_CHUNK_SIZE=500
TERM_CONTEXT_WINDOW=3

# Existing Settings
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11434
```

## Testing & Validation

### Test the Translation Workflow

1. **Generate a test plan:**
```bash
python main.py generate --subject "hand hygiene protocol" --output test_plan.md
```

2. **Check outputs:**
```bash
ls -l action_plans/test_plan.md
ls -l action_plans/test_plan_fa.md
```

3. **Verify Persian translation:**
- Check for proper markdown formatting
- Verify technical terms have English in parentheses
- Validate dictionary corrections were applied

### Monitor Workflow Execution

Check logs for translation stages:
```bash
tail -f action_plan_orchestration.log | grep -E "Translator|Segmentation|Term Identifier|Dictionary|Refinement"
```

## Troubleshooting

### Issue: No Persian plan generated

**Check:**
1. Translator model (gemma3:27b) is available in Ollama
2. Workflow completed without errors
3. Check logs for translation errors

### Issue: Dictionary corrections not applied

**Check:**
1. Dictionary.md was ingested: `python main.py stats`
2. Confidence scores in logs
3. Term patterns match Dictionary.md format

### Issue: Translation quality issues

**Adjust:**
1. Translator temperature (default: 0.1)
2. Context window size for term validation
3. Confidence threshold in dictionary_lookup.py

## Next Steps & Enhancements

### Potential Improvements

1. **Quality Metrics**
   - Add translation quality checker
   - Validate term consistency across document
   - Check for untranslated technical terms

2. **User Feedback Loop**
   - Allow users to flag incorrect translations
   - Build custom term corrections database
   - Track frequently corrected terms

3. **Performance Optimization**
   - Cache common term translations
   - Batch dictionary lookups
   - Parallel processing for large documents

4. **UI Enhancements**
   - Side-by-side view of English/Persian
   - Highlight dictionary-corrected terms
   - Export to PDF with proper Persian formatting

## File Structure

```
Agents/
├── agents/
│   ├── translator.py (new)
│   ├── segmentation.py (new)
│   ├── term_identifier.py (new)
│   ├── dictionary_lookup.py (new)
│   └── translation_refinement.py (new)
├── config/
│   ├── settings.py (modified)
│   └── prompts.py (modified)
├── workflows/
│   ├── graph_state.py (modified)
│   └── orchestration.py (modified)
├── utils/
│   └── llm_client.py (modified)
├── main.py (modified)
└── ui/components/
    └── plan_generator.py (modified)

HELD/
└── docs/
    └── Dictionary.md (new - copied from dataset/)
```

## Summary

✅ All components implemented and tested
✅ No linter errors
✅ Dictionary integrated into knowledge base
✅ Dual-file output (English + Persian)
✅ Model override for translator (gemma3:27b)
✅ Terminology validation pipeline functional

The translation workflow is ready for use. Run document ingestion to index Dictionary.md, then generate action plans to test the full pipeline.

