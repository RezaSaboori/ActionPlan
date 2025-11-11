"""Document hierarchy loader for Special Protocols feature."""

import logging
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from config.settings import get_settings

logger = logging.getLogger(__name__)


class DocumentHierarchyLoader:
    """
    Utility class for querying Neo4j to retrieve document hierarchy.
    
    Used by Special Protocols feature to fetch document sections
    and their nested subsections.
    """
    
    def __init__(self):
        """Initialize Neo4j connection."""
        self.settings = get_settings()
        self.driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        logger.info("Initialized DocumentHierarchyLoader")
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
    
    def get_all_documents(self) -> List[Dict[str, str]]:
        """
        Get all documents from Neo4j.
        
        Returns:
            List of document dictionaries with 'name' and 'source' fields
        """
        query = """
        MATCH (doc:Document)
        RETURN doc.name as name, doc.source as source
        ORDER BY doc.name
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            documents = []
            for record in result:
                documents.append({
                    'name': record['name'],
                    'source': record['source']
                })
            
            logger.info(f"Retrieved {len(documents)} documents from Neo4j")
            return documents
    
    def get_document_sections(self, doc_name: str) -> List[Dict[str, Any]]:
        """
        Get all sections (headings) for a specific document.
        
        Args:
            doc_name: Document name
            
        Returns:
            List of section dictionaries with hierarchical metadata
        """
        query = """
        MATCH (doc:Document {name: $doc_name})-[:HAS_SUBSECTION*]->(h:Heading)
        RETURN h.id as node_id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary
        ORDER BY h.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, doc_name=doc_name)
            sections = []
            for record in result:
                sections.append({
                    'node_id': record['node_id'],
                    'title': record['title'],
                    'level': record['level'],
                    'start_line': record['start_line'],
                    'end_line': record['end_line'],
                    'summary': record['summary'] or ''
                })
            
            logger.info(f"Retrieved {len(sections)} sections for document '{doc_name}'")
            return sections
    
    def get_nested_subsections(self, node_id: str) -> List[str]:
        """
        Get all nested subsections (descendants) of a given node.
        
        Args:
            node_id: Parent node ID
            
        Returns:
            List of descendant node IDs
        """
        query = """
        MATCH (parent:Heading {id: $node_id})-[:HAS_SUBSECTION*]->(child:Heading)
        RETURN child.id as node_id
        ORDER BY child.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            subsection_ids = [record['node_id'] for record in result]
            
            logger.info(f"Found {len(subsection_ids)} nested subsections for node '{node_id}'")
            return subsection_ids
    
    def expand_node_ids_with_subsections(self, node_ids: List[str]) -> List[str]:
        """
        Expand a list of node IDs to include all nested subsections.
        
        Args:
            node_ids: List of parent node IDs
            
        Returns:
            Expanded list including originals + all descendants
        """
        expanded = set(node_ids)  # Start with originals
        
        for node_id in node_ids:
            subsections = self.get_nested_subsections(node_id)
            expanded.update(subsections)
        
        expanded_list = sorted(list(expanded))
        logger.info(f"Expanded {len(node_ids)} nodes to {len(expanded_list)} (including subsections)")
        return expanded_list
    
    def format_for_extractor(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieve full node data formatted for Extractor agent.
        
        Args:
            node_ids: List of node IDs to retrieve
            
        Returns:
            List of node dictionaries with complete metadata
        """
        if not node_ids:
            return []
        
        # Build query with parameter list
        query = """
        MATCH (h:Heading)
        WHERE h.id IN $node_ids
        MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h)
        RETURN h.id as node_id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary, doc.name as document, doc.source as source
        ORDER BY h.start_line
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_ids=node_ids)
            nodes = []
            for record in result:
                nodes.append({
                    'id': record['node_id'],
                    'title': record['title'],
                    'level': record['level'],
                    'start_line': record['start_line'],
                    'end_line': record['end_line'],
                    'summary': record['summary'] or '',
                    'source': record['source'],
                    'document': record['document']
                })
            
            logger.info(f"Formatted {len(nodes)} nodes for Extractor")
            return nodes
    
    def validate_node_ids(self, node_ids: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that node IDs exist in Neo4j.
        
        Args:
            node_ids: List of node IDs to validate
            
        Returns:
            Tuple of (all_valid: bool, missing_ids: List[str])
        """
        if not node_ids:
            return True, []
        
        query = """
        MATCH (h:Heading)
        WHERE h.id IN $node_ids
        RETURN h.id as node_id
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_ids=node_ids)
            found_ids = set(record['node_id'] for record in result)
            
            missing_ids = [nid for nid in node_ids if nid not in found_ids]
            
            if missing_ids:
                logger.warning(f"Missing node IDs: {missing_ids}")
                return False, missing_ids
            else:
                logger.info(f"All {len(node_ids)} node IDs validated successfully")
                return True, []

