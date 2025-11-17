"""Graph-based RAG using Neo4j for structural document retrieval."""

import logging
import re
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from config.settings import get_settings
from utils.document_parser import DocumentParser
from utils.ollama_embeddings import OllamaEmbeddingsClient

logger = logging.getLogger(__name__)


class GraphRAG:
    """Structural graph-based RAG using Neo4j with semantic search support."""
    
    def __init__(self, collection_name: str = "rules", markdown_logger=None):
        """
        Initialize GraphRAG.
        
        Args:
            collection_name: Name prefix for the graph (rules or protocols)
            markdown_logger: Optional MarkdownLogger instance
        """
        self.settings = get_settings()
        self.collection_name = collection_name
        self.markdown_logger = markdown_logger
        self.driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        # Initialize embedding client for semantic search
        self.embedding_client = OllamaEmbeddingsClient()
        logger.info(f"Initialized GraphRAG for collection: {collection_name}")
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
    
    def traverse_by_keywords(
        self,
        keywords: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find nodes by keyword matching in title or summary.
        
        Args:
            keywords: List of keywords to search for
            top_k: Maximum number of results
            
        Returns:
            List of matching nodes with metadata
        """
        # Build keyword search pattern (case-insensitive)
        keyword_pattern = '|'.join([f"(?i).*{kw}.*" for kw in keywords])
        
        query = """
        MATCH (h:Heading)
        WHERE h.title =~ $pattern OR h.summary =~ $pattern
        RETURN h.id as id, h.title as title, h.level as level, 
               h.line as line, h.summary as summary
        LIMIT $top_k
        """
        
        with self.driver.session() as session:
            result = session.run(query, pattern=keyword_pattern, top_k=top_k)
            nodes = [dict(record) for record in result]
        
        logger.info(f"Found {len(nodes)} nodes matching keywords: {keywords}")
        return nodes
    
    def get_subsections(
        self,
        node_id: str,
        depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Traverse graph hierarchy to get subsections.
        
        Args:
            node_id: Starting node ID
            depth: How many levels deep to traverse
            
        Returns:
            List of subsection nodes
        """
        query = f"""
        MATCH path = (start:Heading {{id: $node_id}})-[:HAS_SUBSECTION*1..{depth}]->(sub:Heading)
        RETURN DISTINCT sub.id as id, sub.title as title, sub.level as level,
               sub.line as line, sub.summary as summary
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            subsections = [dict(record) for record in result]
        
        logger.debug(f"Found {len(subsections)} subsections for node {node_id}")
        return subsections
    
    def retrieve_content(
        self,
        node_id: str,
        file_path: str
    ) -> str:
        """
        Get document content for a specific node using line ranges.
        
        Args:
            node_id: Node ID to retrieve content for
            file_path: Path to source document
            
        Returns:
            Content text
        """
        # Get node metadata with start_line and end_line
        query = """
        MATCH (h:Heading {id: $node_id})
        RETURN h.start_line as start_line, h.end_line as end_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                logger.warning(f"Node {node_id} not found")
                return ""
            
            start_line = record['start_line']
            end_line = record['end_line']
            
            if start_line is None or end_line is None:
                logger.warning(f"Missing line info for node {node_id}")
                return ""
            
            # Retrieve content using line range
            content = DocumentParser.get_content_by_lines(file_path, start_line, end_line)
            return content
    
    def retrieve_content_by_lines(
        self,
        file_path: str,
        start_line: int,
        end_line: int
    ) -> str:
        """
        Retrieve content from markdown file by line range.
        
        Args:
            file_path: Path to markdown file
            start_line: Starting line (0-indexed)
            end_line: Ending line (0-indexed, inclusive)
            
        Returns:
            Content as string
        """
        return DocumentParser.get_content_by_lines(file_path, start_line, end_line)
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Combine keyword search with graph traversal.
        
        Args:
            query: Search query
            top_k: Number of results
            
        Returns:
            List of results with citations
        """
        # Define stop words to filter out generic terms
        stop_words = {
            'identify', 'locate', 'extract', 'find', 'review', 'determine',
            'describe', 'outline', 'explain', 'summarize', 'detail', 'they',
            'that', 'this', 'what', 'which', 'where', 'when', 'how', 'from',
            'with', 'have', 'been', 'will', 'can', 'should', 'must', 'the',
            'and', 'for', 'are', 'was', 'were', 'has', 'had', 'does', 'did'
        }
        
        # Extract keywords from query (improved approach)
        words = query.lower().split()
        keywords = [w for w in words if len(w) > 3 and w not in stop_words]
        
        # Limit to top 10 most distinctive keywords
        keywords = keywords[:10]
        
        # Find matching nodes
        nodes = self.traverse_by_keywords(keywords, top_k=top_k)
        
        results = []
        for node in nodes:
            result = {
                'node_id': node['id'],
                'title': node['title'],
                'level': node['level'],
                'line': node['line'],
                'summary': node.get('summary', ''),
                'source': self.collection_name
            }
            results.append(result)
        
        return results
    
    def get_parent_context(
        self,
        node_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get parent node for context.
        
        Args:
            node_id: Child node ID
            
        Returns:
            Parent node metadata or None
        """
        query = """
        MATCH (parent:Heading)-[:HAS_SUBSECTION]->(child:Heading {id: $node_id})
        RETURN parent.id as id, parent.title as title, 
               parent.level as level, parent.summary as summary
        LIMIT 1
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            return dict(record) if record else None
    
    def get_document_root(self, doc_name: str) -> Optional[Dict[str, Any]]:
        """Get root document node."""
        query = """
        MATCH (doc:Document {name: $doc_name})
        RETURN doc.name as name, doc.type as type
        """
        
        with self.driver.session() as session:
            result = session.run(query, doc_name=doc_name)
            record = result.single()
            return dict(record) if record else None
    
    # ========================================================================
    # NEW METHODS FOR MULTI-PHASE ANALYZER SYSTEM
    # ========================================================================
    
    def get_parent_documents(self, topics: List[str]) -> List[Dict[str, Any]]:
        """
        Find Document nodes matching topics from Orchestrator.
        
        Args:
            topics: List of topic keywords to search for
            
        Returns:
            List of matching Document nodes with metadata
        """
        if not topics:
            logger.warning("No topics provided to get_parent_documents")
            return []
        
        # Build pattern for topic matching (case-insensitive)
        topic_pattern = '|'.join([f"(?i).*{topic}.*" for topic in topics])
        
        query = """
        MATCH (doc:Document)
        WHERE doc.name =~ $pattern
        RETURN doc.name as name, doc.source as source
        """
        
        with self.driver.session() as session:
            result = session.run(query, pattern=topic_pattern)
            documents = [dict(record) for record in result]
        
        logger.info(f"Found {len(documents)} documents matching topics: {topics}")
        return documents
    
    def get_document_toc(self, document_name: str) -> List[Dict[str, Any]]:
        """
        Get direct children (Table of Contents) of a document - one level deep.
        
        These are the top-level headings directly connected to the Document node.
        
        Args:
            document_name: Name of the document
            
        Returns:
            List of direct child heading nodes (TOC entries)
        """
        query = """
        MATCH (doc:Document {name: $doc_name})-[:HAS_SUBSECTION]->(h:Heading)
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary
        ORDER BY h.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, doc_name=document_name)
            nodes = [dict(record) for record in result]
        
        logger.debug(f"Found {len(nodes)} TOC entries for document {document_name}")
        return nodes
    
    def find_nodes_by_section_title(self, document_name: str, section_title: str) -> List[Dict[str, Any]]:
        """
        Find nodes matching a section title within a specific document.
        
        Uses fuzzy matching to find sections with similar titles (case-insensitive,
        partial matching).
        
        Args:
            document_name: Name of the document to search in
            section_title: Section title to search for (can be partial match)
            
        Returns:
            List of matching heading nodes with metadata
        """
        # Create a pattern for case-insensitive partial matching
        # Escape special regex characters and allow partial matches
        pattern = f"(?i).*{re.escape(section_title)}.*"
        
        query = """
        MATCH (doc:Document {name: $doc_name})-[:HAS_SUBSECTION*]->(h:Heading)
        WHERE h.title =~ $pattern
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, doc.source as source, doc.name as document_name
        ORDER BY h.start_line
        LIMIT 10
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, doc_name=document_name, pattern=pattern)
                nodes = []
                for record in result:
                    nodes.append({
                        'id': record['id'],
                        'title': record['title'],
                        'level': record['level'],
                        'start_line': record['start_line'],
                        'end_line': record['end_line'],
                        'summary': record.get('summary', ''),
                        'source': record.get('source', ''),
                        'document_name': record.get('document_name', document_name)
                    })
                
                logger.debug(f"Found {len(nodes)} nodes matching '{section_title}' in document '{document_name}'")
                return nodes
        except Exception as e:
            logger.error(f"Error searching for section '{section_title}' in document '{document_name}': {e}")
            return []
    
    def get_introduction_nodes(self, document_name: str) -> List[Dict[str, Any]]:
        """
        Get first-level heading nodes (introductions) for a document.
        
        Args:
            document_name: Name of the document
            
        Returns:
            List of first-level heading nodes
        """
        query = """
        MATCH (doc:Document {name: $doc_name})-[:HAS_SUBSECTION]->(h:Heading)
        WHERE h.level = 1
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary
        ORDER BY h.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, doc_name=document_name)
            nodes = [dict(record) for record in result]
        
        logger.debug(f"Found {len(nodes)} introduction nodes for document {document_name}")
        return nodes
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve specific node with all metadata including source file path.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node metadata or None if not found
        """
        query = """
        MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: $node_id})
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, doc.source as source
        LIMIT 1
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                logger.warning(f"Node {node_id} not found")
                return None
            
            return dict(record)
    
    def navigate_upward(self, node_id: str, levels: int = 1) -> List[Dict[str, Any]]:
        """
        Navigate N levels up from a node, return parent nodes with source.
        
        Args:
            node_id: Starting node ID
            levels: Number of levels to navigate upward
            
        Returns:
            List of parent nodes (may be empty if at document root)
        """
        if levels < 1:
            logger.warning("levels must be >= 1")
            return []
        
        # Build dynamic query for upward navigation with document source
        query = f"""
        MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {{id: $node_id}})
        MATCH path = (ancestor)-[:HAS_SUBSECTION*1..{levels}]->(h)
        WITH doc, ancestor, length(path) as depth
        WHERE depth = {levels}
        RETURN ancestor.id as id, ancestor.title as title, 
               ancestor.level as level, ancestor.start_line as start_line,
               ancestor.end_line as end_line, ancestor.summary as summary,
               doc.source as source
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            parents = [dict(record) for record in result]
        
        logger.debug(f"Navigated {levels} levels up from {node_id}, found {len(parents)} parent(s)")
        return parents
    
    def consolidate_branches(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge nodes that share the same parent node to avoid redundant processing.
        
        Args:
            nodes: List of node dictionaries with 'id' field
            
        Returns:
            Deduplicated list of nodes (unique by node_id)
        """
        if not nodes:
            return []
        
        # Use dict to deduplicate by node_id
        unique_nodes = {}
        for node in nodes:
            node_id = node.get('id')
            if node_id and node_id not in unique_nodes:
                unique_nodes[node_id] = node
        
        consolidated = list(unique_nodes.values())
        logger.debug(f"Consolidated {len(nodes)} nodes to {len(consolidated)} unique nodes")
        return consolidated
    
    def get_children(self, node_id: str) -> List[Dict[str, Any]]:
        """
        Get direct child nodes of a given node with source file path.
        
        Args:
            node_id: Parent node ID
            
        Returns:
            List of direct child nodes
        """
        query = """
        MATCH (doc:Document)-[:HAS_SUBSECTION*]->(parent:Heading {id: $node_id})
        MATCH (parent)-[:HAS_SUBSECTION]->(child:Heading)
        RETURN child.id as id, child.title as title, child.level as level,
               child.start_line as start_line, child.end_line as end_line,
               child.summary as summary, doc.source as source
        ORDER BY child.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            children = [dict(record) for record in result]
        
        logger.debug(f"Found {len(children)} children for node {node_id}")
        return children
    
    def read_node_content(
        self,
        node_id: str,
        file_path: str,
        start_line: int,
        end_line: int
    ) -> str:
        """
        Read complete content for a node based on line numbers.
        
        Args:
            node_id: Node identifier (for logging)
            file_path: Path to source document
            start_line: Starting line number
            end_line: Ending line number
            
        Returns:
            Complete text content for the node
        """
        try:
            content = DocumentParser.get_content_by_lines(file_path, start_line, end_line)
            logger.debug(f"Read {len(content)} chars from {file_path} lines {start_line}-{end_line} for node {node_id}")
            return content
        except Exception as e:
            logger.error(f"Error reading content for node {node_id}: {e}")
            return ""
    
    def get_section_hierarchy_string(self, node_id: str) -> str:
        """
        Get hierarchical path string for a node (Document > Section > Subsection).
        
        Args:
            node_id: Node ID to get hierarchy for
            
        Returns:
            Hierarchical path as string
        """
        query = """
        MATCH path = (doc:Document)-[:HAS_SUBSECTION*]->(target:Heading {id: $node_id})
        WITH nodes(path) as pathNodes
        RETURN [n in pathNodes | COALESCE(n.name, n.title)] as hierarchy
        LIMIT 1
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, node_id=node_id)
                record = result.single()
                
                if record and record['hierarchy']:
                    hierarchy = record['hierarchy']
                    return ' > '.join(hierarchy)
                else:
                    return ""
        except Exception as e:
            logger.error(f"Error getting hierarchy for {node_id}: {e}")
            return ""
    
    # ========================================================================
    # NEW METHODS FOR REDESIGNED ANALYZER WORKFLOW
    # ========================================================================
    
    def get_all_document_nodes(self) -> List[Dict[str, Any]]:
        """
        Get ALL parent Document nodes from the knowledge graph.
        
        This provides global context for Analyzer Phase 1 to understand
        what documents are available, helping to prevent RAG gaps.
        
        Returns:
            List of all Document nodes with name and summary
        """
        query = """
        MATCH (doc:Document)
        RETURN doc.name as name, doc.summary as summary, 
               doc.source as source
        ORDER BY doc.name
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            documents = [dict(record) for record in result]
        
        logger.info(f"Retrieved {len(documents)} document nodes from knowledge graph")
        return documents
    
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
    
    def query_introduction_nodes(
        self,
        query_text: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query introduction-level nodes (level=1) using SEMANTIC SEARCH.
        
        Uses Neo4j-stored summary embeddings for precise retrieval.
        This method replaces keyword-based regex matching with semantic similarity,
        providing much better precision and recall.
        
        Args:
            query_text: Search query string
            top_k: Maximum number of results to return
            
        Returns:
            List of matching level-1 heading nodes with semantic scores
        """
        logger.info(f"Semantic search for introduction nodes: '{query_text[:100]}...'")
        
        # Generate query embedding
        try:
            query_embedding = self.embedding_client.embed(query_text)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return []
        
        # Cypher query to retrieve level 1 nodes with embeddings
        query = """
        MATCH (doc:Document)-[:HAS_SUBSECTION]->(h:Heading)
        WHERE h.level = 1 AND h.summary_embedding IS NOT NULL
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, h.summary_embedding as embedding,
               doc.name as document_name, doc.source as source
        """
        
        try:
            # Fetch all level 1 nodes and compute cosine similarity
            with self.driver.session() as session:
                result = session.run(query)
                nodes = []
                for record in result:
                    node = dict(record)
                    embedding = node.pop('embedding')
                    
                    # Compute cosine similarity
                    similarity = self._cosine_similarity(query_embedding, embedding)
                    node['score'] = similarity
                    nodes.append(node)
            
            # Sort by similarity and return top_k
            nodes.sort(key=lambda x: x['score'], reverse=True)
            top_nodes = nodes[:top_k]
            
            logger.info(f"Found {len(nodes)} introduction nodes, returning top {len(top_nodes)} by semantic similarity")
            if top_nodes:
                logger.info(f"Top score: {top_nodes[0]['score']:.4f}, Lowest score: {top_nodes[-1]['score']:.4f}")
            
            return top_nodes
            
        except Exception as e:
            logger.error(f"Error in semantic search for introduction nodes: {e}")
            return []

