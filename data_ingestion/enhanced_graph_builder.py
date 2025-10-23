"""Enhanced Neo4j graph builder with hierarchical summarization from app.py."""

import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
from config.settings import get_settings
from utils.llm_client import OllamaClient

logger = logging.getLogger(__name__)


class EnhancedGraphBuilder:
    """
    Build Neo4j graph from markdown documents with hierarchical summarization.
    
    Features:
    - Bottom-up hierarchical summarization (children inform parents)
    - Proper document tree structure
    - Transaction-based execution for atomicity
    - Source file tracking
    """
    
    def __init__(self, collection_name: str = "rules"):
        """
        Initialize EnhancedGraphBuilder.
        
        Args:
            collection_name: Collection identifier (rules or protocols)
        """
        self.settings = get_settings()
        self.collection_name = collection_name
        self.driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        self.llm_client = OllamaClient()
        
        # Ensure database exists and is accessible
        self._initialize_database()
        
        logger.info(f"Initialized EnhancedGraphBuilder for: {collection_name}")
    
    def _initialize_database(self):
        """Initialize Neo4j database and verify connectivity."""
        try:
            with self.driver.session() as session:
                # Verify connectivity
                result = session.run("RETURN 1 as test")
                result.single()
                
                # Create indexes for better performance
                session.run("""
                    CREATE INDEX heading_id IF NOT EXISTS 
                    FOR (h:Heading) ON (h.id)
                """)
                session.run("""
                    CREATE INDEX document_name IF NOT EXISTS 
                    FOR (d:Document) ON (d.name)
                """)
                session.run("""
                    CREATE INDEX document_type IF NOT EXISTS 
                    FOR (d:Document) ON (d.type)
                """)
                
                logger.info("Neo4j database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def build_from_directory(self, docs_dir: str, clear_existing: bool = False) -> None:
        """
        Build graph from all markdown files in directory.
        
        Args:
            docs_dir: Path to directory containing markdown files
            clear_existing: Whether to clear existing data first
        """
        if not os.path.exists(docs_dir):
            logger.error(f"Directory not found: {docs_dir}")
            return
        
        if clear_existing:
            self.clear_collection()
        
        # Get all markdown files
        md_files = list(Path(docs_dir).glob("**/*.md"))
        logger.info(f"Found {len(md_files)} markdown files in {docs_dir}")
        
        for md_file in md_files:
            logger.info(f"Processing: {md_file.name}")
            try:
                self.build_from_file(str(md_file))
            except Exception as e:
                logger.error(f"Error processing {md_file}: {e}")
                continue
    
    def build_from_file(self, file_path: str) -> None:
        """
        Build graph from a single markdown file with hierarchical summarization.
        
        Args:
            file_path: Path to markdown file
        """
        doc_name = Path(file_path).stem
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract hierarchy
        headings = self._extract_hierarchy(content)
        
        if not headings:
            logger.warning(f"No headings found in {file_path}")
            return
        
        # Build document tree
        doc_tree = self._build_document_tree(headings, doc_name)
        
        # Generate summaries hierarchically (bottom-up)
        logger.info(f"Generating hierarchical summaries for {doc_name}...")
        self._summarize_nodes_recursively(doc_tree, content.split('\n'))
        
        # Generate and execute Cypher commands
        cypher_commands = self._generate_cypher_statements(doc_tree, file_path)
        self._execute_cypher_transaction(cypher_commands)
        
        logger.info(f"Successfully built graph for {doc_name} ({len(headings)} headings)")
    
    def _extract_hierarchy(self, content: str) -> List[Dict]:
        """Extract heading hierarchy from markdown content."""
        lines = content.split('\n')
        headings = []
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        
        # Find all headings with their line numbers
        for i, line in enumerate(lines):
            match = re.match(heading_pattern, line.strip())
            if match:
                headings.append({
                    'level': len(match.group(1)),
                    'title': match.group(2).strip(),
                    'start_line': i,
                    'end_line': 0,
                    'type': 'heading',
                    'children': [],
                    'content': '',
                    'summary': ''
                })
        
        # Determine content range and end line for each heading
        for i, heading in enumerate(headings):
            start_line_content = heading['start_line'] + 1
            
            if i + 1 < len(headings):
                end_line_content = headings[i + 1]['start_line']
                heading['end_line'] = headings[i + 1]['start_line'] - 1
            else:
                end_line_content = len(lines)
                heading['end_line'] = len(lines) - 1
            
            heading['content'] = "\n".join(lines[start_line_content:end_line_content]).strip()
        
        return headings
    
    def _build_document_tree(self, headings: List[Dict], doc_name: str) -> Dict:
        """Build hierarchical tree from flat list of headings."""
        root = {
            'level': 0,
            'children': [],
            'title': doc_name,
            'type': 'root',
            'summary': ''
        }
        parent_stack = [root]
        
        for heading in headings:
            while parent_stack[-1]['level'] >= heading['level']:
                parent_stack.pop()
            
            parent_stack[-1]['children'].append(heading)
            parent_stack.append(heading)
        
        return root
    
    def _summarize_nodes_recursively(self, node: Dict, lines: List[str]):
        """
        Recursively generate summaries from bottom up.
        Child summaries are used as context for parent summaries.
        """
        # First, summarize all children
        child_summaries = []
        for child in node.get('children', []):
            self._summarize_nodes_recursively(child, lines)
            if child.get('summary'):
                child_summaries.append(
                    f"Subsection '{child['title']}': {child['summary']}"
                )
        
        # Build context from child summaries
        context_for_summary = ""
        if child_summaries:
            context_for_summary = (
                "Use the following summaries of subsections as context:\n\n" +
                "\n".join(child_summaries)
            )
        
        # Don't summarize the root node
        if node['level'] > 0:
            # Only summarize if there's content or children
            if node.get('content') or child_summaries:
                logger.info(f"  Summarizing: {node['title']} (Level {node['level']})")
                text_to_summarize = node.get('content', '')
                node['summary'] = self._generate_summary_with_context(
                    text_to_summarize,
                    context_for_summary
                )
    
    def _generate_summary_with_context(self, text: str, context: str = "") -> str:
        """Generate summary using LLM with optional context from children."""
        system_prompt = """You are a highly skilled summarization expert for health policy documents.

Guidelines:
- Be concise: Keep summaries short while retaining core information
- List guidelines and tables mentioned in the text
- No introductions: Provide only the summary
- Use context: If subsection summaries are provided, synthesize them with the main text
- Stay neutral: Be objective, no personal opinions
- Focus on actionable information for health managers and policymakers"""
        
        user_prompt = f"**Text to Summarize:**\n{text}\n\n"
        if context:
            user_prompt += f"**Context from Subsections:**\n{context}"
        
        try:
            summary = self.llm_client.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=200
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
            # Fallback to first few sentences
            sentences = text.split('.')[:3]
            return '.'.join(sentences)[:300] + '...'
    
    def _is_rule_document(self, doc_name: str) -> bool:
        """Determine if document is a rule/guideline document based on name."""
        doc_lower = doc_name.lower()
        rule_keywords = self.settings.rule_document_names
        return any(keyword in doc_lower for keyword in rule_keywords)
    
    def _generate_cypher_statements(self, doc_tree: Dict, file_path: str) -> List[str]:
        """Generate Neo4j Cypher commands including summaries."""
        cypher_commands = []
        
        # Create Document node with is_rule flag
        doc_name = self._escape_cypher_string(doc_tree['title'])
        doc_prefix = doc_tree['title'].lower().replace(' ', '_').replace('.', '_').replace('-', '_')
        source_file = self._escape_cypher_string(str(file_path))
        is_rule = str(self._is_rule_document(doc_tree['title'])).lower()
        
        cypher_commands.append(
            f"MERGE (d:Document {{name: '{doc_name}', type: '{self.collection_name}', source: '{source_file}', is_rule: {is_rule}}})"
        )
        
        # Flatten tree to list for processing
        flat_nodes = []
        nodes_to_visit = list(reversed(doc_tree.get('children', [])))
        
        while nodes_to_visit:
            node = nodes_to_visit.pop()
            flat_nodes.append(node)
            children = node.get('children', [])
            for child in reversed(children):
                nodes_to_visit.append(child)
        
        # Phase 1: Create all heading nodes with unique IDs
        for i, item in enumerate(flat_nodes):
            node_id = f"{doc_prefix}_h{i + 1}"
            title = self._escape_cypher_string(item['title'])
            summary = self._escape_cypher_string(item.get('summary', ''))
            item['id'] = node_id  # Store for relationship phase
            
            cypher_commands.append(
                f"CREATE (h:Heading {{id: '{node_id}', title: '{title}', level: {item['level']}, "
                f"start_line: {item['start_line']}, end_line: {item['end_line']}, summary: '{summary}'}})"
            )
        
        # Phase 2: Create relationships
        parent_stack = [{'id': 'doc', 'level': 0}]
        
        for item in flat_nodes:
            while parent_stack[-1]['level'] >= item['level']:
                parent_stack.pop()
            
            parent_id = parent_stack[-1]['id']
            
            if parent_id == 'doc':
                cypher_commands.append(
                    f"MATCH (p:Document {{name: '{doc_name}'}}), (c:Heading {{id: '{item['id']}'}}) "
                    f"CREATE (p)-[:HAS_SUBSECTION]->(c)"
                )
            else:
                cypher_commands.append(
                    f"MATCH (p:Heading {{id: '{parent_id}'}}), (c:Heading {{id: '{item['id']}'}}) "
                    f"CREATE (p)-[:HAS_SUBSECTION]->(c)"
                )
            
            parent_stack.append(item)
        
        return cypher_commands
    
    def _escape_cypher_string(self, value: str) -> str:
        """Escape string for use in Cypher query."""
        if not value:
            return ""
        return value.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    
    def _execute_cypher_transaction(self, statements: List[str]):
        """Execute list of Cypher statements in a single transaction."""
        with self.driver.session() as session:
            logger.debug(f"Executing {len(statements)} Cypher statements in transaction")
            
            with session.begin_transaction() as tx:
                for statement in statements:
                    if statement:
                        try:
                            tx.run(statement)
                        except Exception as e:
                            logger.error(f"Error in statement: {e}")
                            logger.debug(f"Statement: {statement}...")
                            raise
            
            logger.debug("Transaction completed successfully")
    
    def clear_collection(self) -> None:
        """Clear all nodes for this collection."""
        logger.info(f"Clearing collection: {self.collection_name}")
        
        query = f"""
        MATCH (d:Document {{type: $collection_type}})
        OPTIONAL MATCH (d)-[:HAS_SUBSECTION*]->(h:Heading)
        DETACH DELETE d, h
        """
        
        with self.driver.session() as session:
            session.run(query, collection_type=self.collection_name)
        
        logger.info(f"Collection cleared: {self.collection_name}")
    
    def clear_database(self) -> None:
        """Clear all nodes and relationships from the entire database."""
        logger.warning("Clearing ENTIRE Neo4j database...")
        
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        logger.info("Database cleared")
    
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the graph."""
        with self.driver.session() as session:
            # Count documents
            doc_result = session.run(
                "MATCH (d:Document {type: $type}) RETURN count(d) as count",
                type=self.collection_name
            )
            doc_count = doc_result.single()['count']
            
            # Count headings
            heading_result = session.run("""
                MATCH (d:Document {type: $type})-[:HAS_SUBSECTION*]->(h:Heading)
                RETURN count(DISTINCT h) as count
            """, type=self.collection_name)
            heading_count = heading_result.single()['count']
            
            # Count relationships
            rel_result = session.run("""
                MATCH (d:Document {type: $type})-[r:HAS_SUBSECTION*]->(h:Heading)
                RETURN count(r) as count
            """, type=self.collection_name)
            rel_count = rel_result.single()['count']
        
        return {
            'documents': doc_count,
            'headings': heading_count,
            'relationships': rel_count
        }
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()
        logger.info("Neo4j connection closed")


def main():
    """Main function for standalone execution."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description="Build Neo4j graph from markdown documents with hierarchical summarization"
    )
    parser.add_argument(
        "--collection",
        choices=["rules", "protocols", "protocol"],
        required=True,
        help="Collection type"
    )
    parser.add_argument(
        "--docs-dir",
        required=True,
        help="Directory containing markdown files"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collection data first"
    )
    parser.add_argument(
        "--clear-all",
        action="store_true",
        help="Clear entire database (use with caution!)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        builder = EnhancedGraphBuilder(collection_name=args.collection)
        
        if args.clear_all:
            response = input("Are you sure you want to clear the ENTIRE database? (yes/no): ")
            if response.lower() == 'yes':
                builder.clear_database()
            else:
                logger.info("Database clear cancelled")
                sys.exit(0)
        
        builder.build_from_directory(args.docs_dir, clear_existing=args.clear)
        
        # Print statistics
        stats = builder.get_statistics()
        print("\n" + "="*60)
        print("Graph Build Statistics:")
        print(f"  Documents: {stats['documents']}")
        print(f"  Headings: {stats['headings']}")
        print(f"  Relationships: {stats['relationships']}")
        print("="*60)
        
        builder.close()
        logger.info("Graph building complete!")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

