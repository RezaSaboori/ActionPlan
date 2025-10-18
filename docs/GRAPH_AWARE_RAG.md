# Graph-Aware RAG System Documentation

## Overview

The Graph-Aware RAG system is an advanced retrieval-augmented generation architecture that combines:

- **Neo4j Graph Structure**: Hierarchical document organization with precise line-based node tracking
- **Dual Vector Embeddings**: Separate summary and content embeddings for flexible retrieval
- **Multiple Retrieval Modes**: Adaptive query strategies based on task requirements
- **Ollama Embeddings**: Using `embeddinggemma:latest` for state-of-the-art embeddings

## Architecture

### Data Flow

```
Markdown Documents (/HELD/docs/*.md)
    ↓
[HELD/app.py] → Neo4j Graph
    - Creates hierarchical nodes with start_line, end_line, summary
    ↓
[GraphVectorBuilder] → Reads graph + MD files
    - Aligns chunks with graph node line ranges
    - Sub-chunks large sections (>1000 tokens)
    - Generates dual embeddings (summary + content)
    ↓
ChromaDB (dual vector collections)
    - Named vectors: summary_embedding, content_embedding
    - Metadata: node_id, title, line_range, etc.
    ↓
[GraphAwareRAG] ← Query with mode selection
    - node_name: Fast Neo4j keyword matching
    - summary: Summary embedding search
    - content: Content embedding search  
    - automatic: Dynamic mode selection
    ↓
Agents (Analyzer, Assigner, Prioritizer)
    - Each uses optimal mode for their task
```

## Components

### 1. OllamaEmbeddingsClient (`utils/ollama_embeddings.py`)

Generates embeddings using Ollama's API with:
- Batch processing support
- Embedding cache for efficiency
- Error handling and retry logic
- Connection health checks

```python
from utils.ollama_embeddings import OllamaEmbeddingsClient

client = OllamaEmbeddingsClient()
embedding = client.embed("your text here")
embeddings = client.embed_batch(["text 1", "text 2", "text 3"])
```

### 2. GraphAwareRAG (`rag_tools/graph_aware_rag.py`)

Advanced RAG module with multiple retrieval modes:

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

rag = GraphAwareRAG(collection_name="graph_documents")

# Different retrieval modes
results = rag.retrieve(query, mode="automatic", top_k=5)
results = rag.retrieve(query, mode="summary", top_k=5)
results = rag.retrieve(query, mode="content", top_k=5)
results = rag.retrieve(query, mode="node_name", top_k=5)

# Hybrid retrieval
results = rag.hybrid_retrieve(query, top_k=5)
```

#### Retrieval Modes

| Mode | Description | Use Case | Speed |
|------|-------------|----------|-------|
| `node_name` | Neo4j keyword matching | Specific section lookup | ⚡⚡⚡ Fastest |
| `summary` | Summary embedding search | Quick overview, high-level info | ⚡⚡ Fast |
| `content` | Content embedding search | Detailed information needed | ⚡ Comprehensive |
| `automatic` | Dynamic mode selection | General queries | ⚡⚡ Adaptive |

**Automatic Mode Logic:**
- Query < 10 words + keywords → `node_name`
- Query < 15 words or simple questions → `summary`
- Complex/detailed queries → `content`

### 3. GraphVectorBuilder (`data_ingestion/graph_vector_builder.py`)

Unified ingestion pipeline that:
1. Reads graph nodes from Neo4j
2. Extracts content from markdown files by line range
3. Chunks based on graph node boundaries
4. Sub-chunks large sections (>1000 tokens) with overlap
5. Generates both summary and content embeddings
6. Uploads to ChromaDB with dual collection configuration

### 4. Enhanced HybridRAG (`rag_tools/hybrid_rag.py`)

Updated to support GraphAwareRAG with backward compatibility:

```python
from rag_tools.hybrid_rag import HybridRAG

# Use new GraphAwareRAG (default)
rag = HybridRAG(
    graph_collection="rules",
    vector_collection="graph_documents",
    use_graph_aware=True
)

# Query with specific mode
results = rag.query(query_text, strategy="summary", top_k=5)

# Legacy mode (old VectorRAG)
rag_legacy = HybridRAG(use_graph_aware=False)
```

## Configuration

Settings in `config/settings.py`:

```python
# Ollama Embedding Configuration
ollama_embedding_model: str = "embeddinggemma:latest"
embedding_dimension: int = 768
max_section_tokens: int = 1000

# Retrieval Modes per Agent
analyzer_retrieval_mode: str = "automatic"    # Dynamic selection
assigner_retrieval_mode: str = "summary"      # Fast role lookup
prioritizer_retrieval_mode: str = "content"   # Detailed timing info
```

Environment variables (`.env`):
```bash
OLLAMA_EMBEDDING_MODEL=embeddinggemma:latest
EMBEDDING_DIMENSION=768
MAX_SECTION_TOKENS=1000

ANALYZER_RETRIEVAL_MODE=automatic
ASSIGNER_RETRIEVAL_MODE=summary
PRIORITIZER_RETRIEVAL_MODE=content
```

## Usage

### Building the Vector Store

1. **First, create the graph in Neo4j** (if not already done):
   ```bash
   cd /storage03/Saboori/ActionPlan/HELD
   python app.py --clear  # Creates graph with start_line, end_line, summary
   ```

2. **Build the dual-embedding vector store**:
   ```bash
   cd /storage03/Saboori/ActionPlan/Agents
   python scripts/build_graph_vector_store.py \
       --docs-dir /storage03/Saboori/ActionPlan/HELD/docs/ \
       --collection graph_documents \
       --clear
   ```

Options:
- `--summary-collection`: ChromaDB collection name for summaries
- `--content-collection`: ChromaDB collection name for content
- `--docs-dir`: Path to markdown files
- `--clear`: Clear existing collection before building
- `--verbose`: Enable debug logging
- `--skip-check`: Skip prerequisite checks

### Using in Agents

The agents are automatically configured to use their optimal retrieval modes:

**AnalyzerAgent** (automatic mode):
```python
# Automatically selects best mode based on query
relevant_sections = analyzer._find_relevant_sections(subject)
```

**AssignerAgent** (summary mode):
```python
# Fast retrieval of role summaries
role_context = assigner._get_role_context()
```

**PrioritizerAgent** (content mode):
```python
# Comprehensive timing information
timing_context = prioritizer._get_timing_context()
```

### Direct RAG Usage

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

# Initialize
rag = GraphAwareRAG(collection_name="graph_documents")

# Query examples
results = rag.retrieve(
    query="emergency triage protocols",
    mode="automatic",  # Let system decide
    top_k=5
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Text: {result['text'][:200]}...")
    print(f"Score: {result['score']}")
    print(f"Mode: {result['retrieval_mode']}")
    print(f"Node: {result['node_id']}")
    print()

# Get node context from graph
context = rag.get_node_context(
    node_id="guideline_h5",
    include_parent=True,
    include_children=True
)
```

## ChromaDB Collection Structure

### Dual Collections

Two separate collections are used:
- **`summaries`**: Stores embeddings of section summaries for fast, high-level retrieval.
- **`documents`**: Stores embeddings of full section content for detailed, comprehensive retrieval.

### Document Metadata (Payload)

```json
{
  "node_id": "document_h1",
  "title": "Emergency Response Protocols",
  "level": 2,
  "start_line": 45,
  "end_line": 120,
  "chunk_index": 0,
  "total_chunks": 1,
  "content": "Full section content...",
  "summary": "Brief summary...",
  "source": "emergency_guidelines"
}
```

## Performance Optimization

### Chunking Strategy

1. **Node-aligned chunks**: Prefer keeping entire sections together
2. **Smart sub-chunking**: Only split sections >1000 tokens
3. **Overlap**: 50 words overlap between sub-chunks
4. **Line tracking**: Maintain precise line ranges for all chunks

### Embedding Cache

The OllamaEmbeddingsClient caches embeddings to avoid regeneration:
```python
client = OllamaEmbeddingsClient()
client.clear_cache()  # Clear if needed
client.disable_cache()  # Disable caching
client.enable_cache()  # Re-enable
```

### Batch Processing

Embeddings are generated in batches for efficiency:
```python
# Automatic batching in GraphVectorBuilder
# Default batch_size=50 for uploads
```

## Best Practices

### 1. Mode Selection

- **Use `automatic`** for general-purpose agents
- **Use `summary`** when you need quick overviews
- **Use `content`** for detailed analysis
- **Use `node_name`** for known section lookups

### 2. Graph Updates

When documents change:
1. Update Neo4j graph (run HELD/app.py)
2. Rebuild vector store (run build_graph_vector_store.py)
3. Both must be in sync!

### 3. Query Optimization

- Keep queries focused and specific
- Use filter_metadata to narrow scope
- Adjust top_k based on needs (5-10 typically optimal)

### 4. Monitoring

Check vector store stats:
```python
builder = GraphVectorBuilder("graph_documents")
stats = builder.get_stats()
print(stats)
```

## Troubleshooting

### Issue: Embeddings fail

**Solution**: Check Ollama is running and model is available:
```bash
ollama list
ollama pull embeddinggemma:latest
```

### Issue: Empty results

**Solution**: 
1. Verify vector store has data: `stats = builder.get_stats()`
2. Check collection name matches
3. Try different retrieval modes

### Issue: Slow queries

**Solution**:
1. Use faster modes (`node_name` or `summary`)
2. Reduce `top_k` value
3. Add metadata filters
4. Enable embedding cache

### Issue: Graph/Vector mismatch

**Solution**: Rebuild both in sequence:
```bash
# 1. Rebuild graph
cd /storage03/Saboori/ActionPlan/HELD
python app.py --clear

# 2. Rebuild vectors
cd /storage03/Saboori/ActionPlan/Agents
python scripts/build_graph_vector_store.py --clear --docs-dir /storage03/Saboori/ActionPlan/HELD/docs/
```

## Advanced Features

### Hybrid Retrieval

Combines graph structure with vector similarity:
```python
results = rag.hybrid_retrieve(
    query="emergency protocols",
    top_k=5,
    graph_weight=0.3,  # 30% graph-based
    vector_weight=0.7   # 70% vector-based
)
```

### Context Expansion

Get related nodes from graph:
```python
context = rag.get_node_context(
    node_id="protocol_h3",
    include_parent=True,
    include_children=True
)
```

## Future Enhancements

- [ ] Cross-document relationship extraction
- [ ] Multi-hop graph reasoning
- [ ] Temporal awareness (document versions)
- [ ] Query rewriting and expansion
- [ ] Relevance feedback learning
- [ ] Multi-lingual support

## References

- NodeRAG: https://arxiv.org/abs/2406.16438
- GraphRAG: Microsoft Research
- LightRAG: Lightweight graph-based retrieval
- ChromaDB: https://www.trychroma.com/

