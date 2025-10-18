# Quick Start Guide - RAG with Neo4j Embeddings

## 🚀 Setup in 3 Steps

### Step 1: Ensure Services are Running

```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check Neo4j
sudo systemctl status neo4j

# If not running, start them:
ollama serve  # In one terminal
sudo systemctl start neo4j  # For Neo4j
```

### Step 2: Process Documents (Create Graph + Embeddings)

```bash
cd /storage03/Saboori/ActionPlan/Agents/held

# Clear database and process all documents
python app.py --clear
```

**What this does:**
1. Parses markdown files from `docs/` directory
2. Generates hierarchical summaries using Ollama (cogito:8b)
3. Creates embeddings for each summary using Ollama (embeddinggemma:latest)
4. Stores everything in Neo4j with embeddings as node properties

**Expected output:**
```
Connected to Neo4j database.
Processing Document: emergency_response...

Starting hierarchical summarization with Ollama...
   - Summary generated for text chunk.
   - Summary generated for text chunk.
Summarization complete.

Generating embeddings for summaries...
Processing batch 1/3 (10 texts)
Processing batch 2/3 (10 texts)
Processing batch 3/3 (8 texts)
Generated 28 embeddings.

Importing 'emergency_response' into Neo4j...
   - Executing 56 Cypher statements in a transaction...
   - Script executed successfully.

Data imported into Neo4j successfully!
```

### Step 3: Query the System

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

# Initialize
rag = GraphAwareRAG()

# Simple query (uses Neo4j embeddings)
results = rag.retrieve(
    "What are the emergency response protocols?",
    mode="summary",
    top_k=3
)

# Print results
for i, result in enumerate(results, 1):
    print(f"\n{i}. {result['title']}")
    print(f"   Score: {result['score']:.4f}")
    print(f"   Summary: {result['text'][:200]}...")

# Close connection
rag.close()
```

## 📊 Test the System

```bash
cd /storage03/Saboori/ActionPlan/Agents/held
python test_rag_with_embeddings.py
```

**This tests:**
- ✓ Embedding client connectivity
- ✓ Summary retrieval from Neo4j
- ✓ Hybrid retrieval (embeddings + graph)
- ✓ Expanded hybrid retrieval (with graph traversal)
- ✓ All retrieval modes

## 🔍 Usage Examples

### 1. Summary-Based Search (Fastest)

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

rag = GraphAwareRAG()

# Search using Neo4j-stored embeddings
results = rag.retrieve(
    "health emergency management guidelines",
    mode="summary",
    top_k=5
)

for r in results:
    print(f"{r['title']} (score: {r['score']:.2f})")
```

### 2. Hybrid Search (Balanced)

```python
# Combines embeddings + keyword matching + graph context
results = rag.hybrid_retrieve(
    "emergency operations center functions",
    top_k=5,
    graph_weight=0.3,    # Weight for keyword matching
    vector_weight=0.7    # Weight for embedding similarity
)

for r in results:
    print(f"\n{r['title']}")
    print(f"  Score: {r['combined_score']:.4f}")
    
    # Show graph context
    if 'parent' in r['metadata']:
        print(f"  Parent: {r['metadata']['parent']['title']}")
    
    if 'children' in r['metadata']:
        print(f"  Children: {len(r['metadata']['children'])} subsections")
```

### 3. Advanced Search with Graph Expansion (Most Comprehensive)

```python
# Retrieves nodes and expands to related sections
results = rag.hybrid_retrieve_with_graph_expansion(
    "disaster preparedness and response strategies",
    top_k=5,
    expansion_depth=2  # Expand up to 2 relationship hops
)

for r in results:
    print(f"\n{r['title']}")
    print(f"  Primary Score: {r['primary_score']:.4f}")
    print(f"  Related Boost: {r['related_boost']:.4f}")
    print(f"  Total Score: {r['score']:.4f}")
    print(f"  Related Nodes: {r['metadata']['related_count']}")
```

### 4. Automatic Mode Selection

```python
# Let the system choose the best mode
results = rag.retrieve(
    "emergency protocols",
    mode="automatic",  # Auto-selects based on query
    top_k=5
)
```

## 🎯 Retrieval Mode Comparison

| Mode | When to Use | Speed | Quality |
|------|-------------|-------|---------|
| `summary` | Conceptual/semantic search | ⚡⚡⚡ | 🎯🎯🎯 |
| `node_name` | Known section titles | ⚡⚡⚡⚡ | 🎯🎯 |
| `content` | Deep content search | ⚡⚡ | 🎯🎯🎯🎯 |
| `hybrid` | Balanced approach | ⚡⚡⚡ | 🎯🎯🎯🎯 |
| `hybrid_expanded` | Comprehensive search | ⚡⚡ | 🎯🎯🎯🎯🎯 |
| `automatic` | General use | ⚡⚡⚡ | 🎯🎯🎯 |

## 🔧 Verify Installation

### Check Neo4j has embeddings

```cypher
// In Neo4j Browser (http://localhost:7474)

// Count nodes with embeddings
MATCH (h:Heading)
WHERE h.summary_embedding IS NOT NULL
RETURN count(h) as nodes_with_embeddings

// View sample node with embedding
MATCH (h:Heading)
WHERE h.summary_embedding IS NOT NULL
RETURN h.title, h.summary, size(h.summary_embedding) as embedding_dim
LIMIT 1
```

Expected output:
```
nodes_with_embeddings: 28
embedding_dim: 3584
```

### Check Ollama Models

```bash
# List available models
ollama list

# Should see:
# embeddinggemma:latest
# cogito:8b
```

## 📁 Directory Structure

```
/storage03/Saboori/ActionPlan/Agents/held/
├── app.py                          # Document processor
├── docs/                           # Source markdown files
│   ├── emergency_response.md
│   └── ...
├── ref/                            # Reference documents
├── test_rag_with_embeddings.py    # Test suite
├── README.md                       # Full documentation
├── IMPLEMENTATION_SUMMARY.md       # Implementation details
└── QUICK_START.md                 # This file
```

## ⚡ Common Commands

```bash
# Process documents
cd /storage03/Saboori/ActionPlan/Agents/held
python app.py --clear  # Clear DB first
python app.py          # Incremental update

# Run tests
python test_rag_with_embeddings.py

# Check Ollama
curl http://localhost:11434/api/tags

# Check Neo4j
sudo systemctl status neo4j

# Clear embedding cache (if needed)
python -c "from utils.ollama_embeddings import OllamaEmbeddingsClient; c = OllamaEmbeddingsClient(); c.clear_cache()"
```

## 🐛 Troubleshooting

### "Connection refused" error
```bash
# Start Ollama
ollama serve

# Start Neo4j
sudo systemctl start neo4j
```

### "No embeddings found" in results
```bash
# Reprocess documents to generate embeddings
cd /storage03/Saboori/ActionPlan/Agents/held
python app.py --clear
```

### Embedding dimension mismatch
```python
# The system auto-detects dimension, but you can check:
from utils.ollama_embeddings import OllamaEmbeddingsClient
client = OllamaEmbeddingsClient()
print(client.embedding_dim)  # Should be 3584 for embeddinggemma
```

### Graph relationships not showing
```cypher
// Check relationships in Neo4j Browser
MATCH (d:Document)-[r:HAS_SUBSECTION*]->(h:Heading)
RETURN d, r, h
LIMIT 25
```

## 📚 Learn More

- **Full Documentation**: See `README.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Strategy Guide**: See `/Agents/docs/RAG_EMBEDDING_STRATEGY.md`
- **Graph-Aware RAG**: See `/Agents/docs/GRAPH_AWARE_RAG.md`

## 🎉 You're Ready!

Your RAG system now:
- ✅ Stores embeddings in Neo4j nodes
- ✅ Combines vector similarity with graph structure
- ✅ Enriches results with graph context
- ✅ Supports multiple retrieval strategies

**Start querying!** 🚀

