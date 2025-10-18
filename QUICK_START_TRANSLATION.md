# Quick Start: Persian Translation Workflow

## Prerequisites

1. **Ensure gemma3:27b model is available:**
```bash
ollama list | grep gemma3
# If not present: ollama pull gemma3:27b
```

2. **Ingest Dictionary.md (One-time setup):**
```bash
cd /storage03/Saboori/ActionPlan/Agents
python main.py ingest --docs-dir /storage03/Saboori/ActionPlan/HELD/docs
```

This will index Dictionary.md into the knowledge base for term validation.

## Generate Bilingual Action Plan

### Option 1: Command Line

```bash
python main.py generate --subject "your action plan subject"
```

Output:
- `action_plans/your_subject_TIMESTAMP.md` (English)
- `action_plans/your_subject_TIMESTAMP_fa.md` (Persian)

### Option 2: Streamlit UI

```bash
streamlit run streamlit_app.py
```

Navigate to the plan generator, enter your subject, and click "Generate Plan".

## What Happens During Translation

1. **Translator** (gemma3:27b) → Creates verbatim Persian translation
2. **Segmentation** → Splits text into analyzable chunks
3. **Term Identifier** → Finds technical terms with English in parentheses
4. **Dictionary Lookup** → Validates terms against Dictionary.md
5. **Refinement** → Applies corrections and produces final Persian plan

## Check Results

```bash
# List generated plans
ls -lh action_plans/

# View English plan
cat action_plans/*_TIMESTAMP.md

# View Persian plan
cat action_plans/*_TIMESTAMP_fa.md
```

## Verify Translation Quality

Look for:
- ✅ Proper markdown formatting preserved
- ✅ Technical terms: "Persian_term (English Term)"
- ✅ Dictionary corrections applied (check logs)
- ✅ No untranslated sections

## Monitor Workflow

```bash
# Watch real-time logs
tail -f action_plan_orchestration.log

# Filter for translation stages
tail -f action_plan_orchestration.log | grep -E "Translator|Dictionary|Refinement"
```

## Configuration (Optional)

Edit `.env` file to customize:

```bash
# Translation model
TRANSLATOR_MODEL=gemma3:27b

# Chunk size for segmentation
SEGMENTATION_CHUNK_SIZE=500

# Context window (sentences before/after term)
TERM_CONTEXT_WINDOW=3
```

## Troubleshooting

**Problem:** Persian plan not generated  
**Solution:** Check if gemma3:27b is installed: `ollama list`

**Problem:** No dictionary corrections  
**Solution:** Verify Dictionary.md was ingested: `python main.py stats`

**Problem:** Translation errors  
**Solution:** Check logs: `tail -100 action_plan_orchestration.log`

---

**That's it!** The translation workflow runs automatically after every action plan generation.

