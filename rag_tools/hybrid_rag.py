"""Hybrid RAG combining graph and vector approaches with dual embeddings support."""

import logging
from typing import List, Dict, Any, Optional, Literal
from .graph_rag import GraphRAG
from .vector_rag import VectorRAG
from .graph_aware_rag import GraphAwareRAG

logger = logging.getLogger(__name__)

RetrievalMode = Literal["node_name", "summary", "content", "automatic", "graph", "vector", "hybrid"]


class HybridRAG:
    """
    Hybrid RAG combining structural graph and semantic vector search.
    
    Now supports dual embeddings and multiple retrieval modes via GraphAwareRAG.
    """
    
    def __init__(
        self,
        graph_collection: str = "rules",
        vector_collection: str = "rules_documents",
        use_graph_aware: bool = False,  # Changed to False to avoid sentence-transformers SSL issues
        markdown_logger=None
    ):
        """
        Initialize HybridRAG.
        
        Args:
            graph_collection: Neo4j graph collection name
            vector_collection: ChromaDB collection name (legacy) or graph-aware collection
            use_graph_aware: Whether to use GraphAwareRAG (with dual embeddings)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.markdown_logger = markdown_logger
        self.graph_rag = GraphRAG(collection_name=graph_collection, markdown_logger=markdown_logger)
        self.use_graph_aware = use_graph_aware
        
        if use_graph_aware:
            # Use new GraphAwareRAG with dual embeddings
            # GraphAwareRAG expects summary_collection and content_collection
            from config.settings import get_settings
            settings = get_settings()
            self.graph_aware_rag = GraphAwareRAG(
                summary_collection=settings.summary_collection_name,
                content_collection=vector_collection,
                markdown_logger=markdown_logger
            )
            self.vector_rag = None
            logger.info(f"Initialized HybridRAG with GraphAwareRAG (dual embeddings): summary={settings.summary_collection_name}, content={vector_collection}")
        else:
            # Use legacy VectorRAG
            self.vector_rag = VectorRAG(collection_name=vector_collection, markdown_logger=markdown_logger)
            self.graph_aware_rag = None
            logger.info(f"Initialized HybridRAG with legacy VectorRAG: {vector_collection}")
    
    def query(
        self,
        query_text: str,
        strategy: RetrievalMode = "hybrid",
        mode: Optional[str] = None,
        top_k: int = 5,
        document_filter: Optional[List[str]] = None,
        guideline_documents: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query using specified strategy and mode.
        
        Args:
            query_text: Search query
            strategy: Overall strategy ("graph", "vector", "hybrid", or specific modes)
            mode: Specific retrieval mode for GraphAwareRAG (node_name, summary, content, automatic)
            top_k: Number of results
            document_filter: Optional list of document names to include (None = all documents)
            guideline_documents: List of guideline documents (always included regardless of filter)
            
        Returns:
            Combined and ranked results
        """
        if self.markdown_logger:
            self.markdown_logger.log_rag_query(query_text, strategy, top_k, "HybridRAG")
        
        # If using GraphAwareRAG, support all modes
        if self.use_graph_aware:
            if strategy in ["node_name", "summary", "content", "automatic"]:
                # Use GraphAwareRAG with specific mode
                results = self.graph_aware_rag.retrieve(query_text, mode=strategy, top_k=top_k)
            elif strategy == "graph":
                results = self._graph_only(query_text, top_k)
            elif strategy == "vector":
                # Use content mode for vector-only
                results = self.graph_aware_rag.retrieve(query_text, mode="content", top_k=top_k)
            else:
                # Hybrid: use GraphAwareRAG's hybrid method
                results = self.graph_aware_rag.hybrid_retrieve(query_text, top_k=top_k)
        else:
            # Legacy mode
            if strategy == "graph":
                results = self._graph_only(query_text, top_k)
            elif strategy == "vector":
                results = self._vector_only(query_text, top_k)
            else:
                results = self._hybrid_search(query_text, top_k)
        
        # Apply document filtering if specified
        if document_filter is not None or guideline_documents is not None:
            results = self._filter_by_documents(results, document_filter, guideline_documents)
        
        if self.markdown_logger:
            self.markdown_logger.log_rag_results(len(results), results[:3])
        
        return results
    
    def _graph_only(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Graph-only search."""
        results = self.graph_rag.hybrid_search(query, top_k=top_k)
        
        # Format results
        formatted = []
        for r in results:
            formatted.append({
                'text': r.get('summary', r.get('title', '')),
                'score': 1.0,  # Graph doesn't provide scores
                'source_type': 'graph',
                'metadata': {
                    'node_id': r['node_id'],
                    'title': r['title'],
                    'level': r['level'],
                    'line': r['line'],
                    'source': r['source']
                }
            })
        
        return formatted
    
    def _vector_only(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Vector-only search."""
        results = self.vector_rag.semantic_search(query, top_k=top_k)
        
        # Format results
        formatted = []
        for r in results:
            formatted.append({
                'text': r['text'],
                'score': r['score'],
                'source_type': 'vector',
                'metadata': r['metadata']
            })
        
        return formatted
    
    def _hybrid_search(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Combined hybrid search."""
        # Get results from both
        graph_results = self._graph_only(query, top_k=top_k)
        vector_results = self._vector_only(query, top_k=top_k)
        
        # Combine and rerank
        combined = self._rerank_results(graph_results, vector_results, top_k)
        
        logger.info(f"Hybrid search returned {len(combined)} results")
        return combined
    
    def _rerank_results(
        self,
        graph_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rerank combined results using reciprocal rank fusion.
        
        Args:
            graph_results: Results from graph search
            vector_results: Results from vector search
            top_k: Final number of results
            
        Returns:
            Reranked results
        """
        # Reciprocal Rank Fusion (RRF)
        k = 60  # RRF constant
        scores = {}
        
        # Score graph results
        for rank, result in enumerate(graph_results):
            key = result['metadata'].get('node_id', f"graph_{rank}")
            scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
            if key not in scores:
                scores[key] = {'result': result, 'score': 0}
            else:
                scores[key] = {'result': result, 'score': scores[key]}
        
        # Score vector results
        for rank, result in enumerate(vector_results):
            key = result['metadata'].get('node_id', f"vector_{rank}")
            rrf_score = 1 / (k + rank + 1)
            
            if key in scores:
                scores[key]['score'] += rrf_score
            else:
                scores[key] = {'result': result, 'score': rrf_score}
        
        # Sort by combined score
        ranked = sorted(
            scores.items(),
            key=lambda x: x[1]['score'] if isinstance(x[1], dict) else x[1],
            reverse=True
        )
        
        # Format output
        final_results = []
        for key, data in ranked[:top_k]:
            if isinstance(data, dict):
                result = data['result'].copy()
                result['combined_score'] = data['score']
                final_results.append(result)
        
        return final_results
    
    def graph_guided_vector_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Use graph to narrow scope, then vector search within.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            Filtered results
        """
        # Step 1: Get relevant sections from graph
        graph_results = self.graph_rag.hybrid_search(query, top_k=top_k * 2)
        
        if not graph_results:
            logger.warning("No graph results, falling back to vector search")
            return self._vector_only(query, top_k)
        
        # Step 2: Extract node IDs for filtering
        node_ids = [r['node_id'] for r in graph_results]
        
        # Step 3: Vector search filtered by node IDs
        # Note: This requires node_id to be stored in vector metadata
        vector_results = []
        for node_id in node_ids:
            results = self.vector_rag.semantic_search(
                query,
                top_k=2,
                filter_metadata={'node_id': node_id}
            )
            vector_results.extend(results)
        
        # Step 4: Sort by score and limit
        vector_results.sort(key=lambda x: x['score'], reverse=True)
        final_results = vector_results[:top_k]
        
        logger.info(f"Graph-guided search returned {len(final_results)} results")
        return final_results
    
    def _filter_by_documents(
        self,
        results: List[Dict[str, Any]],
        document_filter: Optional[List[str]],
        guideline_documents: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Filter results by document names.
        
        Args:
            results: Results to filter
            document_filter: List of allowed document names (None = all documents)
            guideline_documents: List of guideline documents (always included)
            
        Returns:
            Filtered results
        """
        if document_filter is None and guideline_documents is None:
            return results
        
        guideline_set = set(guideline_documents or [])
        filter_set = set(document_filter or [])
        
        # Combine: if document_filter is specified, use it + guidelines
        # If document_filter is None, allow all documents
        allowed_documents = filter_set | guideline_set if document_filter is not None else None
        
        filtered = []
        for result in results:
            metadata = result.get('metadata', {})
            doc_name = metadata.get('source', metadata.get('document', ''))
            
            # Always include if it's a guideline document
            if doc_name in guideline_set:
                filtered.append(result)
            # Include if no filter specified (allow all)
            elif allowed_documents is None:
                filtered.append(result)
            # Include if in the allowed set
            elif doc_name in allowed_documents:
                filtered.append(result)
        
        logger.info(f"Document filtering: {len(results)} -> {len(filtered)} results")
        return filtered
    
    def close(self):
        """Close connections."""
        self.graph_rag.close()
        if self.use_graph_aware and self.graph_aware_rag:
            self.graph_aware_rag.close()

