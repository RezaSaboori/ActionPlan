# HELD - Health Emergency Document Analyzer

## Overview

The HELD (Health Emergency and Logistics Documents) system processes markdown documents about health emergency management and stores them in Neo4j with embedded summaries for advanced RAG (Retrieval-Augmented Generation) capabilities.

## New RAG Strategy

### Embedding Storage in Neo4j

Each node's summary is now:
1. **Generated** using Ollama (cogito:8b model)
2. **Embedded** using Ollama embeddings (embeddinggemma:latest)
3. **Stored** as a `summary_embedding` property in Neo4j nodes

### Retrieval Strategy

The system combines **embedding similarity** with **Neo4j graph queries**:

```
Query → Embedding
         ↓
    [Neo4j Query]
         ↓
   Compute Cosine Similarity
         ↓
   Combine with Graph Structure
         ↓
    Ranked Results
```

#### Retrieval Modes

1. **Summary Mode** (`mode="summary"`)
   - Queries Neo4j for nodes with embeddings
   - Computes cosine similarity in-memory
   - Fast and lightweight

2. **Hybrid Mode** (`hybrid_retrieve()`)
   - Combines keyword matching with embedding similarity
   - Enriches results with graph context (parent/children)
   - Balanced approach

3. **Expanded Hybrid Mode** (`hybrid_retrieve_with_graph_expansion()`)
   - Retrieves nodes by embedding similarity
   - Expands to related nodes via graph relationships
   - Boosts scores based on related node relevance
   - Most comprehensive

## Architecture

```
Markdown Documents
    ↓
[app.py] → Parse & Summarize (Ollama)
    ↓
[OllamaEmbeddingsClient] → Embed Summaries
    ↓
[Neo4j] → Store Nodes with Embeddings
    {
      id, title, level,
      start_line, end_line,
      summary, summary_embedding[]
    }
    ↓
[GraphAwareRAG] → Query with Combined Strategy
    - Embedding similarity
    - Graph structure
    - Context enrichment
    ↓
Ranked Results
```

## Directory Structure

```
held/
├── app.py                      # Document processor with embedding generation
├── docs/                       # Source markdown documents
├── ref/                        # Reference documents
├── test_rag_with_embeddings.py # Test suite for RAG system
└── README.md                   # This file
```

## Usage

### 1. Process Documents

```bash
cd /storage03/Saboori/ActionPlan/Agents/held
python app.py --clear  # Clear database and reprocess all documents
python app.py          # Process new documents only
```

This will:
- Parse markdown documents from `docs/` directory
- Generate hierarchical summaries using Ollama
- Generate embeddings for each summary
- Store everything in Neo4j with embeddings

### 2. Query the RAG System

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

rag = GraphAwareRAG()

# Summary-based retrieval (using Neo4j embeddings)
results = rag.retrieve(
    "emergency response protocols",
    mode="summary",
    top_k=5
)

# Hybrid retrieval (embeddings + graph structure)
results = rag.hybrid_retrieve(
    "health emergency management",
    top_k=5,
    graph_weight=0.3,
    vector_weight=0.7
)

# Advanced hybrid with graph expansion
results = rag.hybrid_retrieve_with_graph_expansion(
    "disaster preparedness guidelines",
    top_k=5,
    expansion_depth=1
)

rag.close()
```

### 3. Run Tests

```bash
cd /storage03/Saboori/ActionPlan/Agents/held
python test_rag_with_embeddings.py
```

## Neo4j Node Schema

### Document Node
```cypher
(:Document {
  name: String,
  type: "root"
})
```

### Heading Node
```cypher
(:Heading {
  id: String,              # Unique identifier
  title: String,           # Section title
  level: Integer,          # Heading level (1-6)
  start_line: Integer,     # Start line in source document
  end_line: Integer,       # End line in source document
  summary: String,         # AI-generated summary
  summary_embedding: [Float]  # Embedding vector (3584 dimensions)
})
```

### Relationships
```cypher
(:Document)-[:HAS_SUBSECTION]->(:Heading)
(:Heading)-[:HAS_SUBSECTION]->(:Heading)
```

## Key Components

### 1. DocumentAnalyzer Class (app.py)

- **`extract_hierarchy()`**: Parse markdown headings
- **`build_document_tree()`**: Build hierarchical structure
- **`summarize_nodes_recursively()`**: Generate summaries bottom-up
- **`generate_cypher_statements()`**: Create Neo4j import statements with embeddings

### 2. GraphAwareRAG Class (rag_tools/graph_aware_rag.py)

- **`_retrieve_by_summary()`**: Query Neo4j embeddings with cosine similarity
- **`hybrid_retrieve()`**: Combine embeddings + graph structure
- **`hybrid_retrieve_with_graph_expansion()`**: Advanced retrieval with graph traversal
- **`get_node_context()`**: Fetch parent/children context

### 3. OllamaEmbeddingsClient (utils/ollama_embeddings.py)

- **`embed()`**: Generate single embedding
- **`embed_batch()`**: Batch embedding generation
- **`cosine_similarity()`**: Compute similarity between embeddings

## Configuration

Configured via `config/settings.py`:

```python
# Neo4j settings
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "cardiosmartai"

# Ollama settings
ollama_base_url = "http://localhost:11434"
ollama_embedding_model = "embeddinggemma:latest"
embedding_dimension = 3584  # embeddinggemma dimension
```

## Advantages of Neo4j Embedding Storage

1. **Unified Storage**: Embeddings stored with graph structure
2. **Graph-Enhanced Retrieval**: Leverage relationships for better context
3. **Flexible Queries**: Combine Cypher with vector similarity
4. **Reduced Complexity**: No separate vector database needed
5. **Context Enrichment**: Easy access to parent/child nodes

## Performance Considerations

- **Batch Embedding**: Generates embeddings in batches for efficiency
- **Caching**: OllamaEmbeddingsClient caches embeddings
- **Lazy Loading**: Embeddings computed only for nodes with summaries
- **Cosine Similarity**: Computed in-memory (consider Neo4j vector index for large datasets)

## Future Enhancements

1. **Neo4j Vector Index**: Use native vector search (Neo4j 5.11+)
2. **Hybrid Scoring**: More sophisticated weighting algorithms
3. **Multi-hop Expansion**: Dynamic expansion based on relevance
4. **Embedding Fine-tuning**: Domain-specific embedding models
5. **Incremental Updates**: Update only changed documents

## Troubleshooting

### Ollama Not Running
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if needed
ollama serve
```

### Neo4j Connection Issues
```bash
# Check Neo4j status
sudo systemctl status neo4j

# Restart Neo4j
sudo systemctl restart neo4j
```

### Embedding Dimension Mismatch
The system auto-detects and updates the embedding dimension. If you change models, clear the cache:
```python
from utils.ollama_embeddings import OllamaEmbeddingsClient
client = OllamaEmbeddingsClient()
client.clear_cache()
```

## References

- [Neo4j Graph Database](https://neo4j.com/)
- [Ollama Embeddings](https://ollama.ai/)
- [EmbeddingGemma Model](https://ollama.ai/library/embeddinggemma)
- [Cogito Model](https://ollama.ai/library/cogito)

