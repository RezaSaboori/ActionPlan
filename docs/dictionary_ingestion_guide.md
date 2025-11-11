# Dictionary Ingestion Guide

## Overview

The Dictionary.md file is now located at `/storage03/Saboori/ActionPlan/Agents/translator_tools/Dictionary.md` and must be ingested into **separate** ChromaDB collection and Neo4j graph to ensure complete isolation from main documents.

## Why Separate Collections?

The dictionary data is used exclusively by the **DictionaryLookupAgent** during the translation workflow. Keeping it in a separate collection ensures:

1. **Isolation**: Dictionary terms don't pollute main document search results
2. **Targeted Retrieval**: DictionaryLookupAgent only searches dictionary data
3. **Clean Architecture**: Main agents (Analyzer, Extractor, etc.) never access dictionary
4. **Performance**: Smaller, focused collections for faster lookups

## Architecture

### ChromaDB Collections
- **Main Documents**: `health_documents` collection (default)
- **Dictionary**: `dictionary` collection (isolated)

### Neo4j Graphs
- **Main Documents**: `health` prefix (default)
- **Dictionary**: `dictionary` prefix (isolated)

### Agent Access
- **Main Agents** (Orchestrator, Analyzer, Extractor, etc.): Use `main_hybrid_rag` → accesses `health_documents` and `health` graph
- **DictionaryLookupAgent**: Uses `dictionary_hybrid_rag` → accesses `dictionary` collection and `dictionary` graph

## Running Dictionary Ingestion

### Prerequisites

1. Ensure Dictionary.md exists at:
   ```
   /storage03/Saboori/ActionPlan/Agents/translator_tools/Dictionary.md
   ```

2. Verify settings in `.env` or `config/settings.py`:
   ```bash
   DICTIONARY_COLLECTION=dictionary
   DICTIONARY_GRAPH_PREFIX=dictionary
   DICTIONARY_PATH=translator_tools/Dictionary.md
   ```

### Command

```bash
cd /storage03/Saboori/ActionPlan/Agents

# Ingest dictionary (clear existing data first)
python -m data_ingestion.dictionary_ingestion \
    --dictionary-path translator_tools/Dictionary.md \
    --dictionary-collection dictionary \
    --dictionary-graph-prefix dictionary \
    --clear
```

### Options

- `--dictionary-path`: Path to Dictionary.md file (default: `translator_tools/Dictionary.md`)
- `--dictionary-collection`: ChromaDB collection name (default: `dictionary`)
- `--dictionary-graph-prefix`: Neo4j graph prefix (default: `dictionary`)
- `--clear`: Clear existing dictionary data before ingesting (recommended)

## Verification

After ingestion, verify the data:

```python
from data_ingestion.dictionary_ingestion import DictionaryIngestionPipeline

pipeline = DictionaryIngestionPipeline()
stats = pipeline.get_stats()
print(stats)
pipeline.close()
```

Expected output:
```
{
    'chroma_collection': {
        'name': 'dictionary',
        'count': 50  # Number of dictionary entries
    },
    'neo4j_graph': {
        'total_terms': 50,
        'terms_with_embeddings': 50,
        'coverage_percentage': 100.0
    }
}
```

## Dictionary Format

The Dictionary.md file uses this format:

```markdown
## خطر قابل قبول Acceptable risk

### تعريف واژه: 

[Persian definition text]

### توضيح

[Persian explanation text]
```

Each entry is parsed to extract:
- **Persian term**: خطر قابل قبول
- **English term**: Acceptable risk
- **Definition**: Text under "تعريف واژه"
- **Explanation**: Text under "توضيح"

## Troubleshooting

### Issue: Collection not found
```
Solution: Run ingestion script with --clear flag
```

### Issue: Embeddings not generated
```
Solution: Verify Ollama is running and embedding model is available:
ollama list | grep embeddinggemma
```

### Issue: Dictionary not used during translation
```
Solution: Verify DictionaryLookupAgent is using dictionary_hybrid_rag (check orchestration.py line 80)
```

## Integration with Translation Workflow

The translation workflow follows this sequence:

1. **Translator** → Creates initial Persian translation
2. **Segmentation** → Splits into chunks
3. **TermIdentifier** → Identifies technical terms
4. **DictionaryLookup** → Searches dictionary collection for corrections
5. **TranslationRefinement** → Applies corrections to final translation

Only step 4 accesses the dictionary collection.

