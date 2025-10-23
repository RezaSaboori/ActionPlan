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
        graph_weight: float = 0.3,
        vector_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval combining graph structure with Neo4j-stored embeddings.
        
        This method:
        1. Uses embedding similarity from Neo4j-stored summary embeddings
        2. Combines with graph structure (node relationships)
        3. Optionally boosts scores based on graph proximity
        
        Args:
            query: Search query
            top_k: Number of results
            graph_weight: Weight for graph-based keyword results
            vector_weight: Weight for embedding similarity results
            
        Returns:
            Reranked combined results
        """
        # Get results from both approaches
        graph_results = self._retrieve_by_node_name(query, top_k=top_k * 2)
        # Use Neo4j-stored embeddings for summary retrieval
        embedding_results = self._retrieve_by_summary(query, top_k=top_k * 2)
        
        # Combine and rerank using weighted scores
        combined_scores = {}
        
        for idx, result in enumerate(graph_results):
            key = result['node_id']
            # Graph results get inverse rank score
            score = graph_weight * (1.0 / (idx + 1))
            combined_scores[key] = {
                'result': result,
                'score': score
            }
        
        for idx, result in enumerate(embedding_results):
            key = result['node_id']
            # Embedding results use actual similarity score
            score = vector_weight * result['score']
            
            if key in combined_scores:
                combined_scores[key]['score'] += score
            else:
                combined_scores[key] = {
                    'result': result,
                    'score': score
                }
        
        # Sort by combined score
        ranked = sorted(
            combined_scores.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        # Format results and enrich with graph context
        final_results = []
        for key, data in ranked[:top_k]:
            result = data['result'].copy()
            result['combined_score'] = data['score']
            result['retrieval_mode'] = 'hybrid'
            
            # Add parent/child context from graph
            context = self.get_node_context(key, include_parent=True, include_children=True)
            if context.get('parent'):
                result['metadata']['parent'] = context['parent']
            if context.get('children'):
                result['metadata']['children'] = context['children']
            
            final_results.append(result)
        
        logger.info(f"Hybrid retrieval returned {len(final_results)} results with graph context")
        return final_results
    
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

