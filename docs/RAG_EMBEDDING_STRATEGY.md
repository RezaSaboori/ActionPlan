# RAG Embedding Strategy - Neo4j Native Storage

## Overview

This document describes the updated RAG strategy where **summary embeddings are stored directly in Neo4j nodes** rather than in a separate ChromaDB collection.

## Strategy

### Summary Storage and Retrieval

**Previous Approach:**
```
Summary → Embedding → ChromaDB Collection
Query → ChromaDB Search → Results
```

**New Approach:**
```
Summary → Embedding → Neo4j Node Property
Query → Embedding → Neo4j Query + Cosine Similarity → Results
```

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Document Processing                  │
├─────────────────────────────────────────────────────┤
│  1. Parse Markdown                                   │
│  2. Generate Hierarchical Summaries (Ollama)         │
│  3. Embed Summaries (OllamaEmbeddingsClient)        │
│  4. Store in Neo4j with Embeddings                   │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              Neo4j Graph + Embeddings                │
├─────────────────────────────────────────────────────┤
│  Nodes:                                              │
│    (:Heading {                                       │
│      id, title, summary,                             │
│      summary_embedding: [float, ...]  ← NEW!        │
│    })                                                │
│  Relationships:                                      │
│    (:Document)-[:HAS_SUBSECTION]->(:Heading)        │
│    (:Heading)-[:HAS_SUBSECTION]->(:Heading)         │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│             Hybrid Retrieval Strategy                │
├─────────────────────────────────────────────────────┤
│  1. Embedding Similarity (from Neo4j)                │
│  2. Graph Structure (relationships)                  │
│  3. Context Enrichment (parent/children)             │
│  4. Graph Expansion (related nodes)                  │
└─────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Document Processing (held/app.py)

```python
class DocumentAnalyzer:
    def __init__(self, content: str, doc_name: str = "Document"):
        self.embedding_client = OllamaEmbeddingsClient()
    
    def generate_cypher_statements(self):
        # ... existing summary generation ...
        
        # NEW: Generate embeddings for summaries
        summaries = [item['summary'] for item in flat_nodes if item['summary']]
        embeddings = self.embedding_client.embed_batch(summaries)
        
        # Store nodes with embeddings
        for item, embedding in zip(flat_nodes, embeddings):
            cypher = f"""
            CREATE (:Heading {{
                id: '{node_id}',
                title: '{title}',
                summary: '{summary}',
                summary_embedding: {embedding}  # ← Stored as array
            }})
            """
```

### 2. Retrieval (rag_tools/graph_aware_rag.py)

#### Summary Retrieval with Neo4j Embeddings

```python
def _retrieve_by_summary(self, query: str, top_k: int):
    query_embedding = self.embedding_client.embed(query)
    
    # Query all nodes with embeddings
    cypher = """
    MATCH (h:Heading)
    WHERE h.summary_embedding IS NOT NULL
    RETURN h.id, h.summary, h.summary_embedding
    """
    
    # Compute cosine similarity
    for record in results:
        similarity = self.embedding_client.cosine_similarity(
            query_embedding,
            record['summary_embedding']
        )
        scores.append((record, similarity))
    
    # Sort and return top_k
    return sorted(scores, key=lambda x: x[1], reverse=True)[:top_k]
```

#### Hybrid Retrieval

```python
def hybrid_retrieve(self, query: str, top_k: int):
    # Combine three approaches:
    # 1. Graph keyword matching
    graph_results = self._retrieve_by_node_name(query, top_k*2)
    
    # 2. Embedding similarity (from Neo4j)
    embedding_results = self._retrieve_by_summary(query, top_k*2)
    
    # 3. Combine and enrich with graph context
    combined = merge_and_rank(graph_results, embedding_results)
    
    # Add parent/children context
    for result in combined:
        context = self.get_node_context(result['node_id'])
        result['metadata']['parent'] = context['parent']
        result['metadata']['children'] = context['children']
    
    return combined[:top_k]
```

#### Graph-Expanded Retrieval

```python
def hybrid_retrieve_with_graph_expansion(self, query: str, expansion_depth: int = 1):
    query_embedding = self.embedding_client.embed(query)
    
    # Single Cypher query that:
    # 1. Retrieves nodes with embeddings
    # 2. Expands to related nodes
    # 3. Returns both primary and related embeddings
    cypher = """
    MATCH (h:Heading)
    WHERE h.summary_embedding IS NOT NULL
    OPTIONAL MATCH (h)-[:HAS_SUBSECTION*0..{depth}]-(related:Heading)
    WHERE related.summary_embedding IS NOT NULL
    RETURN h, collect(related) as related_nodes
    """
    
    # Compute combined score:
    # - Primary similarity
    # - Max similarity from related nodes (as boost)
    for record in results:
        primary_score = cosine_similarity(query_embedding, record.h.summary_embedding)
        related_scores = [
            cosine_similarity(query_embedding, r.summary_embedding) 
            for r in record.related_nodes
        ]
        boost = max(related_scores) * 0.3 if related_scores else 0
        combined_score = primary_score + boost
```

## Advantages

### 1. **Unified Data Model**
- Embeddings stored alongside graph data
- Single source of truth
- Simplified architecture

### 2. **Graph-Enhanced Retrieval**
- Leverage relationships for context
- Parent/child enrichment
- Multi-hop expansion

### 3. **Flexible Querying**
- Combine Cypher with vector similarity
- Filter by graph properties
- Traverse relationships during retrieval

### 4. **Reduced Dependencies**
- No separate vector database
- Fewer moving parts
- Easier deployment

### 5. **Context-Aware Results**
- Access to document hierarchy
- Related sections visible
- Better explainability

## Performance Considerations

### Current Implementation

**Pros:**
- Flexible and works with any Neo4j version
- Full control over similarity computation
- Easy to understand and debug

**Cons:**
- Cosine similarity computed in Python (not in database)
- All embeddings loaded into memory for each query
- May not scale to millions of nodes

### Future Optimization: Neo4j Vector Index (5.11+)

```cypher
-- Create vector index (Neo4j 5.11+)
CREATE VECTOR INDEX heading_embeddings
FOR (h:Heading)
ON (h.summary_embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 3584,
  `vector.similarity_function`: 'cosine'
}}

-- Query using vector index
CALL db.index.vector.queryNodes(
  'heading_embeddings',
  5,  -- top_k
  $query_embedding
)
YIELD node, score
RETURN node, score
```

This would:
- Perform similarity search in the database
- Use approximate nearest neighbors (ANN) for speed
- Scale to millions of nodes
- Reduce network transfer

## Retrieval Modes Comparison

| Mode | Data Source | Use Case | Speed | Quality |
|------|-------------|----------|-------|---------|
| `node_name` | Neo4j graph | Known sections | ⚡⚡⚡ | 🎯🎯 |
| `summary` | Neo4j embeddings | Conceptual search | ⚡⚡ | 🎯🎯🎯 |
| `content` | ChromaDB | Deep search | ⚡ | 🎯🎯🎯🎯 |
| `hybrid` | Neo4j graph + embeddings | Balanced | ⚡⚡ | 🎯🎯🎯🎯 |
| `hybrid_expanded` | Neo4j graph + embeddings + expansion | Comprehensive | ⚡ | 🎯🎯🎯🎯🎯 |
| `automatic` | Auto-select | General use | ⚡⚡ | 🎯🎯🎯 |

## Usage Examples

### Basic Summary Retrieval

```python
from rag_tools.graph_aware_rag import GraphAwareRAG

rag = GraphAwareRAG()

# Query using Neo4j embeddings
results = rag.retrieve(
    "emergency preparedness protocols",
    mode="summary",
    top_k=5
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Score: {result['score']:.4f}")
    print(f"Summary: {result['text'][:100]}...")
```

### Hybrid Retrieval with Context

```python
# Combine embeddings with graph structure
results = rag.hybrid_retrieve(
    "health emergency response coordination",
    top_k=5,
    graph_weight=0.3,    # Weight for keyword matching
    vector_weight=0.7    # Weight for embedding similarity
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Combined Score: {result['combined_score']:.4f}")
    
    # Graph context
    if 'parent' in result['metadata']:
        print(f"Parent: {result['metadata']['parent']['title']}")
    
    if 'children' in result['metadata']:
        print(f"Children: {len(result['metadata']['children'])}")
```

### Advanced Graph Expansion

```python
# Retrieve with graph expansion
results = rag.hybrid_retrieve_with_graph_expansion(
    "disaster management guidelines",
    top_k=5,
    expansion_depth=2  # Expand up to 2 hops
)

for result in results:
    print(f"Title: {result['title']}")
    print(f"Primary Score: {result['primary_score']:.4f}")
    print(f"Related Boost: {result['related_boost']:.4f}")
    print(f"Total Score: {result['score']:.4f}")
    print(f"Related Nodes: {result['metadata']['related_count']}")
```

## Migration from ChromaDB

### What Changed

**Before:**
```python
# Summary embeddings in ChromaDB
self.summary_collection.add(
    ids=[node_id],
    embeddings=[embedding],
    metadatas=[{"node_id": node_id, "summary": summary}]
)

# Query ChromaDB
results = self.summary_collection.query(
    query_embeddings=[query_embedding],
    n_results=top_k
)
```

**After:**
```python
# Summary embeddings in Neo4j
cypher = """
CREATE (:Heading {
    id: $node_id,
    summary: $summary,
    summary_embedding: $embedding
})
"""

# Query Neo4j
cypher = """
MATCH (h:Heading)
WHERE h.summary_embedding IS NOT NULL
RETURN h.id, h.summary, h.summary_embedding
"""
# Compute similarity in Python
```

### Backward Compatibility

- Content embeddings still in ChromaDB (for now)
- `mode="content"` still uses ChromaDB
- Gradual migration path available

## Testing

```bash
cd /storage03/Saboori/ActionPlan/Agents/held
python test_rag_with_embeddings.py
```

Tests include:
1. ✓ Embedding client connectivity
2. ✓ Summary retrieval from Neo4j
3. ✓ Hybrid retrieval with graph context
4. ✓ Expanded hybrid retrieval
5. ✓ All retrieval modes

## Future Enhancements

1. **Neo4j Native Vector Search**
   - Use `db.index.vector.queryNodes()` (Neo4j 5.11+)
   - 10-100x faster for large datasets
   - Approximate nearest neighbors

2. **Content Embeddings in Neo4j**
   - Move content chunks to Neo4j
   - Eliminate ChromaDB dependency
   - Unified vector + graph database

3. **Advanced Graph Patterns**
   - PageRank-based boosting
   - Community detection
   - Shortest path relevance

4. **Adaptive Weighting**
   - Learn optimal graph/vector weights
   - Query-specific adaptation
   - User feedback incorporation

## References

- [Neo4j Vector Search](https://neo4j.com/docs/cypher-manual/current/indexes-for-vector-search/)
- [Graph RAG Paper](https://arxiv.org/abs/2404.16130)
- [Ollama Embeddings](https://ollama.ai/blog/embedding-models)

