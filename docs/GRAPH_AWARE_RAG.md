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

### Direct RAG Usage

```