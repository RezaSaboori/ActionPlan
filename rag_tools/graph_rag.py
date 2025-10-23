"""Graph-based RAG using Neo4j for structural document retrieval."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from config.settings import get_settings
from utils.document_parser import DocumentParser

logger = logging.getLogger(__name__)


class GraphRAG:
    """Structural graph-based RAG using Neo4j."""
    
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
        # Extract keywords from query (simple approach)
        keywords = [word.lower() for word in query.split() if len(word) > 3]
        
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
        RETURN doc.name as name, doc.type as type, 
               doc.source as source, doc.is_rule as is_rule
        """
        
        with self.driver.session() as session:
            result = session.run(query, pattern=topic_pattern)
            documents = [dict(record) for record in result]
        
        logger.info(f"Found {len(documents)} documents matching topics: {topics}")
        return documents
    
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
               doc.type as type, doc.source as source,
               doc.is_rule as is_rule
        ORDER BY doc.name
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            documents = [dict(record) for record in result]
        
        logger.info(f"Retrieved {len(documents)} document nodes from knowledge graph")
        return documents
    
    def query_introduction_nodes(
        self,
        query_text: str,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query only introduction-level nodes (level 1 headings) based on query text.
        
        This is used in Analyzer Phase 1 to perform initial targeted queries
        while staying at the high-level document structure.
        
        Args:
            query_text: Search query string
            top_k: Maximum number of results to return
            
        Returns:
            List of matching level-1 heading nodes with metadata
        """
        import re as regex_module
        
        # Extract keywords from query (simple tokenization)
        # Clean up markdown and special characters first
        clean_text = query_text.replace('**', '').replace('*', '').replace('_', ' ')
        keywords = [word.lower() for word in clean_text.split() if len(word) >= 3]
        
        if not keywords:
            logger.warning("No valid keywords in query, returning empty results")
            return []
        
        # Escape regex special characters and limit to top keywords
        escaped_keywords = [regex_module.escape(kw) for kw in keywords[:50]]  # Limit to 50 keywords
        
        # Build pattern for keyword matching (case-insensitive)
        keyword_pattern = '|'.join([f"(?i).*{kw}.*" for kw in escaped_keywords])
        
        query = """
        MATCH (doc:Document)-[:HAS_SUBSECTION]->(h:Heading)
        WHERE h.level = 1 
          AND (h.title =~ $pattern OR h.summary =~ $pattern)
        RETURN h.id as id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, doc.name as document_name,
               doc.source as source
        ORDER BY h.start_line
        LIMIT $top_k
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, pattern=keyword_pattern, top_k=top_k)
                nodes = [dict(record) for record in result]
            
            logger.info(f"Found {len(nodes)} introduction-level nodes matching query: '{query_text}'")
            return nodes
        except Exception as e:
            logger.error(f"Error querying introduction nodes: {e}")
            logger.error(f"Query text: '{query_text}'")
            logger.error(f"Pattern: '{keyword_pattern}'")
            return []

