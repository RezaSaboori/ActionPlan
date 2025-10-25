"""Advanced Graph-Aware RAG with multiple retrieval modes and dual embeddings."""

import logging
import re
from typing import List, Dict, Any, Optional, Literal
import chromadb
from chromadb.config import Settings as ChromaSettings
from neo4j import GraphDatabase
from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient

logger = logging.getLogger(__name__)

RetrievalMode = Literal["node_name", "summary", "content", "automatic"]


class GraphAwareRAG:
    """
    Advanced RAG combining graph structure with dual vector embeddings in ChromaDB.
    
    Supports multiple retrieval modes:
    - node_name: Fast keyword/title matching via Neo4j
    - summary: Search using summary embeddings (lighter, faster)
    - content: Search using content embeddings (comprehensive)
    - automatic: Dynamically select based on query complexity
    """
    
    def __init__(self, summary_collection: str = "summaries", content_collection: str = "documents", markdown_logger=None):
        """
        Initialize GraphAwareRAG with optional logging.
        
        Args:
            summary_collection: ChromaDB collection for summary embeddings
            content_collection: ChromaDB collection for content embeddings  
            markdown_logger: Optional MarkdownLogger instance
        """
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.summary_collection_name = summary_collection
        self.content_collection_name = content_collection
        
        # Initialize Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        
        # Initialize ChromaDB client with telemetry disabled
        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.summary_collection = self.chroma_client.get_or_create_collection(self.summary_collection_name)
        self.content_collection = self.chroma_client.get_or_create_collection(self.content_collection_name)
        
        # Initialize embedding client
        self.embedding_client = OllamaEmbeddingsClient()
        
        logger.info(f"Initialized GraphAwareRAG with collections: summary='{summary_collection}', content='{content_collection}'")
    
    def close(self):
        """Close database connections."""
        self.neo4j_driver.close()
    
    def create_collection(self):
        """Create ChromaDB collections (already handled in __init__)."""
        # ChromaDB collections are automatically created in __init__ via get_or_create_collection
        logger.info(f"ChromaDB collections ready: summary='{self.summary_collection_name}', content='{self.content_collection_name}'")
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score [0.0, 1.0]
        """
        import math
        
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def retrieve(
        self,
        query: str,
        mode: RetrievalMode = "automatic",
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents using specified mode.
        
        Args:
            query: Search query
            mode: Retrieval mode (node_name, summary, content, automatic)
            top_k: Number of results
            filter_metadata: Optional metadata filters
            
        Returns:
            List of retrieved documents with metadata
        """
        logger.info(f"Retrieving with mode: {mode}, query: {query}...")
        
        # Automatic mode selection
        if mode == "automatic":
            mode = self._select_mode(query)
            logger.info(f"Automatic mode selected: {mode}")
        
        # Route to appropriate retrieval method
        if mode == "node_name":
            return self._retrieve_by_node_name(query, top_k)
        elif mode == "summary":
            return self._retrieve_by_summary(query, top_k, filter_metadata)
        elif mode == "content":
            return self._retrieve_by_content(query, top_k, filter_metadata)
        else:
            logger.warning(f"Unknown mode: {mode}, falling back to content")
            return self._retrieve_by_content(query, top_k, filter_metadata)
    
    def _select_mode(self, query: str) -> RetrievalMode:
        """
        Automatically select retrieval mode based on query complexity.
        
        Args:
            query: Search query
            
        Returns:
            Selected retrieval mode
        """
        query_lower = query.lower()
        word_count = len(query.split())
        
        # Check for specific keywords that indicate node name search
        node_keywords = [
            "section", "chapter", "guideline", "protocol",
            "table", "figure", "appendix", "definition"
        ]
        has_node_keyword = any(kw in query_lower for kw in node_keywords)
        
        # Simple queries with keywords -> node name search
        if word_count < 10 and has_node_keyword:
            return "node_name"
        
        # Short queries or questions -> summary search
        if word_count < 15 or query_lower.startswith(("what", "which", "where", "who")):
            return "summary"
        
        # Complex queries or detailed questions -> content search
        return "content"
    
    def _retrieve_by_node_name(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve by matching node titles/names in Neo4j graph.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of matching nodes
        """
        # Extract keywords from query
        keywords = self._extract_keywords(query)
        
        # Build regex pattern for case-insensitive matching
        keyword_pattern = '|'.join([f"(?i).*{re.escape(kw)}.*" for kw in keywords])
        
        cypher_query = """
        MATCH (h:Heading)
        WHERE h.title =~ $pattern OR h.summary =~ $pattern
        RETURN h.id as node_id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary
        LIMIT $top_k
        """
        
        with self.neo4j_driver.session() as session:
            result = session.run(cypher_query, pattern=keyword_pattern, top_k=top_k)
            nodes = []
            
            for record in result:
                nodes.append({
                    'node_id': record['node_id'],
                    'title': record['title'],
                    'level': record['level'],
                    'start_line': record['start_line'],
                    'end_line': record['end_line'],
                    'text': record['summary'] or record['title'],
                    'score': 1.0,  # Graph search doesn't provide similarity scores
                    'retrieval_mode': 'node_name',
                    'metadata': {
                        'node_id': record['node_id'],
                        'title': record['title'],
                        'line_range': f"{record['start_line']}-{record['end_line']}"
                    }
                })
        
        logger.info(f"Node name retrieval found {len(nodes)} results")
        return nodes
    
    def _retrieve_by_summary(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using summary embeddings stored in Neo4j (lighter, faster).
        
        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Optional metadata filters (currently not used with Neo4j)
            
        Returns:
            List of results from summary embeddings
        """
        query_embedding = self.embedding_client.embed(query)
        
        try:
            # Query Neo4j for nodes with embeddings and compute cosine similarity
            cypher_query = """
            MATCH (h:Heading)
            WHERE h.summary_embedding IS NOT NULL
            RETURN h.id as node_id, h.title as title, h.level as level,
                   h.start_line as start_line, h.end_line as end_line,
                   h.summary as summary, h.summary_embedding as embedding
            """
            
            with self.neo4j_driver.session() as session:
                result = session.run(cypher_query)
                nodes_with_scores = []
                
                for record in result:
                    # Compute cosine similarity
                    stored_embedding = record['embedding']
                    similarity = self.embedding_client.cosine_similarity(
                        query_embedding,
                        stored_embedding
                    )
                    
                    nodes_with_scores.append({
                        'node_id': record['node_id'],
                        'title': record['title'],
                        'level': record['level'],
                        'start_line': record['start_line'],
                        'end_line': record['end_line'],
                        'text': record['summary'] or record['title'],
                        'score': similarity,
                        'retrieval_mode': 'summary',
                        'metadata': {
                            'node_id': record['node_id'],
                            'title': record['title'],
                            'line_range': f"{record['start_line']}-{record['end_line']}",
                            'summary': record['summary']
                        }
                    })
                
                # Sort by similarity score and return top_k
                nodes_with_scores.sort(key=lambda x: x['score'], reverse=True)
                formatted_results = nodes_with_scores[:top_k]
            
            logger.info(f"Summary retrieval found {len(formatted_results)} results from Neo4j embeddings")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in summary retrieval from Neo4j: {e}")
            return []
    
    def _retrieve_by_content(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using content embeddings (comprehensive).
        
        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Optional metadata filters
            
        Returns:
            List of results from content embeddings
        """
        query_embedding = self.embedding_client.embed(query)
        
        try:
            results = self.content_collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_metadata
            )
            
            formatted_results = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    metadata = results['metadatas'][0][i]
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'score': 1 - results['distances'][0][i] if results['distances'] else 0,
                        'text': metadata.get('content', ''),
                        'node_id': metadata.get('node_id', ''),
                        'title': metadata.get('title', ''),
                        'retrieval_mode': 'content',
                        'metadata': metadata
                    })
            
            logger.info(f"Content retrieval found {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in content retrieval: {e}")
            return []
    
    def _build_filter(self, filter_metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Build ChromaDB where filter from metadata dictionary."""
        return filter_metadata # ChromaDB uses the dict directly
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query."""
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'what',
            'which', 'where', 'when', 'who', 'how', 'why'
        }
        
        words = query.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        return keywords[:5]  # Limit to top 5 keywords
    
    def get_node_context(
        self,
        node_id: str,
        include_parent: bool = True,
        include_children: bool = False
    ) -> Dict[str, Any]:
        """
        Get contextual information for a node from the graph.
        
        Args:
            node_id: Node identifier
            include_parent: Include parent node information
            include_children: Include children nodes
            
        Returns:
            Dictionary with node and context information
        """
        context = {'node': None, 'parent': None, 'children': []}
        
        with self.neo4j_driver.session() as session:
            # Get node itself
            node_query = """
            MATCH (h:Heading {id: $node_id})
            RETURN h.id as id, h.title as title, h.level as level,
                   h.start_line as start_line, h.end_line as end_line,
                   h.summary as summary
            """
            result = session.run(node_query, node_id=node_id)
            record = result.single()
            if record:
                context['node'] = dict(record)
            
            # Get parent if requested (can be a Heading or a Document)
            if include_parent:
                parent_query = """
                MATCH (parent:Heading)-[:HAS_SUBSECTION]->(child:Heading {id: $node_id})
                RETURN parent.id as id, parent.title as title,
                       parent.level as level, parent.summary as summary
                UNION
                MATCH (parent:Document)-[:HAS_SUBSECTION]->(child:Heading {id: $node_id})
                RETURN parent.name as id, parent.name as title,
                       0 as level, "" as summary
                """
                result = session.run(parent_query, node_id=node_id)
                record = result.single()
                if record:
                    context['parent'] = dict(record)
            
            # Get children if requested
            if include_children:
                children_query = """
                MATCH (parent:Heading {id: $node_id})-[:HAS_SUBSECTION]->(child)
                RETURN child.id as id, child.title as title,
                       child.level as level, child.summary as summary
                """
                result = session.run(children_query, node_id=node_id)
                context['children'] = [dict(record) for record in result]
        
        return context
    
    def hybrid_retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_rrf: bool = True,
        use_mmr: bool = True,
        graph_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Advanced hybrid retrieval with RRF and MMR.
        
        Combines:
        1. Semantic search (summary embeddings from Neo4j)
        2. Keyword matching (graph structure)
        3. RRF fusion for optimal ranking (default, recommended)
        4. MMR for diversity (optional)
        
        Best practice: Multi-strategy retrieval with fusion outperforms
        any single approach. RRF is more robust than weighted combination.
        
        Args:
            query: Search query
            top_k: Number of results
            use_rrf: Use Reciprocal Rank Fusion (recommended: True)
            use_mmr: Apply MMR for diversity (recommended: True for varied results)
            graph_weight: Weight for graph-based keyword results (legacy mode)
            vector_weight: Weight for embedding similarity results (legacy mode)
            
        Returns:
            Reranked combined results with optional diversity
        """
        logger.info(f"Hybrid retrieval (RRF={use_rrf}, MMR={use_mmr})")
        
        # Get results from multiple strategies
        semantic_results = self._retrieve_by_summary(query, top_k=top_k * 2)
        keyword_results = self._retrieve_by_node_name(query, top_k=top_k * 2)
        
        # Apply RRF fusion (recommended)
        if use_rrf:
            combined = self.reciprocal_rank_fusion(
                [semantic_results, keyword_results],
                k=60
            )
        else:
            # Legacy weighted combination
            logger.info("Using legacy weighted combination (consider using RRF)")
            combined = self._legacy_weighted_combine(
                semantic_results, keyword_results,
                graph_weight, vector_weight
            )
        
        # Apply MMR for diversity
        if use_mmr and len(combined) > top_k:
            query_embedding = self.embedding_client.embed(query)
            combined = self.maximal_marginal_relevance(
                query_embedding,
                combined[:top_k * 2],  # Work with top candidates
                top_k=top_k,
                lambda_param=0.7  # Favor relevance over diversity (70/30)
            )
        else:
            combined = combined[:top_k]
        
        logger.info(f"Hybrid retrieval returned {len(combined)} results")
        return combined
    
    def _legacy_weighted_combine(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        graph_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Legacy weighted combination method (deprecated, use RRF instead).
        
        Kept for backward compatibility.
        """
        combined_scores = {}
        
        for idx, result in enumerate(keyword_results):
            key = result.get('node_id') or result.get('id')
            if not key:
                continue
            # Graph results get inverse rank score
            score = graph_weight * (1.0 / (idx + 1))
            combined_scores[key] = {
                'result': result,
                'score': score
            }
        
        for idx, result in enumerate(semantic_results):
            key = result.get('node_id') or result.get('id')
            if not key:
                continue
            # Embedding results use actual similarity score
            score = vector_weight * result.get('score', 0.0)
            
            if key in combined_scores:
                combined_scores[key]['score'] += score
            else:
                combined_scores[key] = {
                    'result': result,
                    'score': score
                }
        
        # Sort by combined score
        ranked = sorted(
            combined_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )
        
        return [item['result'] for item in ranked]
    
    def hybrid_retrieve_with_graph_expansion(
        self,
        query: str,
        top_k: int = 5,
        expansion_depth: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Advanced hybrid retrieval with graph expansion.
        
        This method:
        1. Retrieves initial nodes using embedding similarity
        2. Expands to related nodes via graph relationships
        3. Re-ranks based on combined embedding + graph distance
        
        Args:
            query: Search query
            top_k: Number of results
            expansion_depth: How many hops to expand in the graph (1-2 recommended)
            
        Returns:
            Expanded and reranked results
        """
        query_embedding = self.embedding_client.embed(query)
        
        # Cypher query that retrieves nodes and their relationships
        cypher_query = """
        MATCH (h:Heading)
        WHERE h.summary_embedding IS NOT NULL
        WITH h, h.summary_embedding as embedding
        OPTIONAL MATCH (h)-[:HAS_SUBSECTION*0..{depth}]-(related:Heading)
        WHERE related.summary_embedding IS NOT NULL
        RETURN DISTINCT h.id as node_id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, h.summary_embedding as embedding,
               collect(DISTINCT {{id: related.id, title: related.title, 
                       embedding: related.summary_embedding}}) as related_nodes
        """.replace('{depth}', str(expansion_depth))
        
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(cypher_query)
                nodes_with_scores = []
                
                for record in result:
                    # Compute primary similarity
                    stored_embedding = record['embedding']
                    primary_similarity = self.embedding_client.cosine_similarity(
                        query_embedding,
                        stored_embedding
                    )
                    
                    # Compute related nodes similarity (boost factor)
                    related_boost = 0.0
                    related_nodes = record.get('related_nodes', [])
                    if related_nodes:
                        related_similarities = []
                        for related in related_nodes:
                            if related.get('embedding'):
                                rel_sim = self.embedding_client.cosine_similarity(
                                    query_embedding,
                                    related['embedding']
                                )
                                related_similarities.append(rel_sim)
                        
                        if related_similarities:
                            # Use max similarity from related nodes as boost
                            related_boost = max(related_similarities) * 0.3
                    
                    # Combined score: primary similarity + related boost
                    combined_score = primary_similarity + related_boost
                    
                    nodes_with_scores.append({
                        'node_id': record['node_id'],
                        'title': record['title'],
                        'level': record['level'],
                        'start_line': record['start_line'],
                        'end_line': record['end_line'],
                        'text': record['summary'] or record['title'],
                        'score': combined_score,
                        'primary_score': primary_similarity,
                        'related_boost': related_boost,
                        'retrieval_mode': 'hybrid_expanded',
                        'metadata': {
                            'node_id': record['node_id'],
                            'title': record['title'],
                            'line_range': f"{record['start_line']}-{record['end_line']}",
                            'summary': record['summary'],
                            'related_count': len([r for r in related_nodes if r.get('id')])
                        }
                    })
                
                # Sort by combined score and return top_k
                nodes_with_scores.sort(key=lambda x: x['score'], reverse=True)
                final_results = nodes_with_scores[:top_k]
            
            logger.info(f"Hybrid expanded retrieval found {len(final_results)} results")
            return final_results
            
        except Exception as e:
            logger.error(f"Error in hybrid expanded retrieval: {e}")
            # Fallback to standard summary retrieval
            return self._retrieve_by_summary(query, top_k)
    
    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict[str, Any]]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Combine multiple ranked result lists using Reciprocal Rank Fusion.
        
        RRF is a proven method for combining results from multiple retrieval strategies.
        It's more robust than weighted combination as it doesn't require score calibration.
        
        RRF Formula: RRF(d) = Σ(1 / (k + rank(d)))
        
        Args:
            result_lists: List of ranked result lists from different strategies
            k: Constant to prevent division by zero (default: 60, from literature)
        
        Returns:
            Fused and re-ranked results with RRF scores
        """
        logger.info(f"Applying Reciprocal Rank Fusion to {len(result_lists)} result lists")
        scores = {}
        
        for list_idx, result_list in enumerate(result_lists):
            for rank, result in enumerate(result_list, start=1):
                node_id = result.get('node_id') or result.get('id')
                if not node_id:
                    continue
                    
                rrf_score = 1.0 / (k + rank)
                
                if node_id not in scores:
                    scores[node_id] = {
                        'result': result,
                        'rrf_score': 0.0,
                        'appeared_in': []
                    }
                scores[node_id]['rrf_score'] += rrf_score
                scores[node_id]['appeared_in'].append(list_idx)
        
        # Sort by RRF score
        fused = sorted(scores.values(), key=lambda x: x['rrf_score'], reverse=True)
        
        # Add RRF metadata to results
        final_results = []
        for item in fused:
            result = item['result'].copy()
            result['rrf_score'] = item['rrf_score']
            result['fusion_sources'] = len(item['appeared_in'])
            final_results.append(result)
        
        logger.info(f"RRF produced {len(final_results)} unique results")
        return final_results
    
    def maximal_marginal_relevance(
        self,
        query_embedding: List[float],
        results: List[Dict[str, Any]],
        top_k: int = 5,
        lambda_param: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Re-rank results using MMR to balance relevance and diversity.
        
        MMR prevents returning redundant/similar documents by penalizing
        documents that are too similar to already selected ones.
        
        MMR = λ * Sim(q, d) - (1-λ) * max(Sim(d, d_i)) for d_i in selected
        
        Args:
            query_embedding: Query embedding vector
            results: Initial retrieval results (must have embeddings or node_ids)
            top_k: Number of results to return
            lambda_param: Tradeoff between relevance (1.0) and diversity (0.0)
        
        Returns:
            Diverse, re-ranked results
        """
        if len(results) <= top_k:
            logger.info(f"MMR: Result count ({len(results)}) <= top_k ({top_k}), returning all")
            return results
        
        logger.info(f"Applying MMR with λ={lambda_param} to select {top_k} from {len(results)} results")
        
        selected = []
        remaining = results.copy()
        
        # Select first result (highest relevance)
        if remaining:
            first = remaining.pop(0)
            selected.append(first)
        
        while len(selected) < top_k and remaining:
            mmr_scores = []
            
            for result in remaining:
                # Get embedding for this result
                try:
                    result_embedding = self._get_embedding_from_result(result)
                    if not result_embedding:
                        continue
                    
                    # Relevance to query
                    relevance = self._cosine_similarity(query_embedding, result_embedding)
                    
                    # Max similarity to already selected docs
                    max_similarity = 0.0
                    for sel in selected:
                        sel_embedding = self._get_embedding_from_result(sel)
                        if sel_embedding:
                            sim = self._cosine_similarity(result_embedding, sel_embedding)
                            max_similarity = max(max_similarity, sim)
                    
                    # MMR score
                    mmr = lambda_param * relevance - (1 - lambda_param) * max_similarity
                    mmr_scores.append((result, mmr))
                    
                except Exception as e:
                    logger.warning(f"Error computing MMR for result: {e}")
                    continue
            
            if not mmr_scores:
                break
            
            # Select result with highest MMR
            best = max(mmr_scores, key=lambda x: x[1])
            selected.append(best[0])
            remaining.remove(best[0])
        
        logger.info(f"MMR selected {len(selected)} diverse results")
        return selected
    
    def _get_embedding_from_result(self, result: Dict[str, Any]) -> Optional[List[float]]:
        """
        Extract embedding from a result dictionary.
        
        Tries multiple strategies:
        1. Direct 'embedding' field
        2. Fetch from Neo4j by node_id
        3. Generate from text content
        
        Args:
            result: Result dictionary
            
        Returns:
            Embedding vector or None
        """
        # Strategy 1: Direct embedding field
        if 'embedding' in result:
            return result['embedding']
        
        # Strategy 2: Fetch from Neo4j
        node_id = result.get('node_id') or result.get('id')
        if node_id:
            try:
                with self.neo4j_driver.session() as session:
                    neo4j_result = session.run("""
                        MATCH (h:Heading {id: $node_id})
                        WHERE h.summary_embedding IS NOT NULL
                        RETURN h.summary_embedding as embedding
                    """, node_id=node_id)
                    record = neo4j_result.single()
                    if record and record['embedding']:
                        return record['embedding']
            except Exception as e:
                logger.debug(f"Could not fetch embedding from Neo4j: {e}")
        
        # Strategy 3: Generate from summary/text
        text = result.get('summary') or result.get('text') or result.get('content')
        if text:
            try:
                return self.embedding_client.embed(text)
            except Exception as e:
                logger.debug(f"Could not generate embedding: {e}")
        
        return None
    
    def graph_expanded_retrieve(
        self,
        query: str,
        top_k: int = 5,
        expansion_depth: int = 1,
        expansion_boost: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve with graph expansion - boosts scores based on related nodes.
        
        Best practice: Leverage graph structure to improve semantic retrieval.
        If a parent/child section is highly relevant, boost the current section's score.
        
        Args:
            query: Search query
            top_k: Number of final results
            expansion_depth: How many relationship hops to expand (1-2 recommended)
            expansion_boost: Score boost multiplier from related node matches (0.0-1.0)
        
        Returns:
            Results with graph-boosted scores
        """
        logger.info(f"Graph-expanded retrieval with depth={expansion_depth}, boost={expansion_boost}")
        
        query_embedding = self.embedding_client.embed(query)
        
        # Cypher query with graph expansion
        cypher = f"""
        MATCH (h:Heading)
        WHERE h.summary_embedding IS NOT NULL
        OPTIONAL MATCH (h)-[:HAS_SUBSECTION*1..{expansion_depth}]-(related:Heading)
        WHERE related.summary_embedding IS NOT NULL
        RETURN h.id as id, h.title as title, h.summary as summary, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary_embedding as embedding,
               collect({{id: related.id, title: related.title, embedding: related.summary_embedding}}) as related
        """
        
        results = []
        try:
            with self.neo4j_driver.session() as session:
                for record in session.run(cypher):
                    # Primary similarity
                    primary_score = self._cosine_similarity(
                        query_embedding,
                        record['embedding']
                    )
                    
                    # Boost from related nodes
                    boost = 0.0
                    related_matches = []
                    if record['related']:
                        related_scores = []
                        for r in record['related']:
                            if r and r.get('embedding'):
                                rel_score = self._cosine_similarity(query_embedding, r['embedding'])
                                related_scores.append(rel_score)
                                if rel_score > 0.5:  # Track high-scoring related nodes
                                    related_matches.append({
                                        'id': r.get('id'),
                                        'title': r.get('title'),
                                        'score': rel_score
                                    })
                        
                        if related_scores:
                            boost = max(related_scores) * expansion_boost
                    
                    final_score = primary_score + boost
                    
                    results.append({
                        'node_id': record['id'],
                        'title': record['title'],
                        'summary': record['summary'],
                        'level': record['level'],
                        'start_line': record['start_line'],
                        'end_line': record['end_line'],
                        'score': final_score,
                        'primary_score': primary_score,
                        'graph_boost': boost,
                        'related_matches': related_matches,
                        'retrieval_mode': 'graph_expanded'
                    })
            
            # Sort and return top_k
            results.sort(key=lambda x: x['score'], reverse=True)
            top_results = results[:top_k]
            
            logger.info(f"Graph-expanded retrieval found {len(top_results)} results")
            if top_results:
                avg_boost = sum(r['graph_boost'] for r in top_results) / len(top_results)
                logger.info(f"Average graph boost: {avg_boost:.4f}")
            
            return top_results
            
        except Exception as e:
            logger.error(f"Error in graph-expanded retrieval: {e}")
            # Fallback to standard retrieval
            return self._retrieve_by_summary(query, top_k)
    
    def retrieve_with_context_window(
        self,
        query: str,
        top_k: int = 5,
        include_parents: bool = True,
        include_children: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks with expanded context windows.
        
        Best practice: Return larger context than just the matched chunk
        for better LLM understanding. Includes parent section overview
        and child section details.
        
        Args:
            query: Search query
            top_k: Number of primary results
            include_parents: Include parent section summaries
            include_children: Include child section summaries
        
        Returns:
            Results with expanded context (parent/children summaries)
        """
        logger.info(f"Retrieving with context window (parents={include_parents}, children={include_children})")
        
        # Get primary results using hybrid retrieval
        results = self.hybrid_retrieve(query, top_k=top_k)
        
        # Expand each result with graph context
        expanded_results = []
        for result in results:
            node_id = result.get('node_id')
            if not node_id:
                expanded_results.append(result)
                continue
            
            # Get graph context
            context = self.get_node_context(
                node_id,
                include_parent=include_parents,
                include_children=include_children
            )
            
            # Enrich result with context
            result_copy = result.copy()
            result_copy['context'] = {
                'parent': context.get('parent'),
                'children': context.get('children', []),
                'has_context': bool(context.get('parent') or context.get('children'))
            }
            expanded_results.append(result_copy)
        
        logger.info(f"Context window expansion complete for {len(expanded_results)} results")
        return expanded_results

