"""Build Neo4j knowledge graph from markdown documents."""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any
from neo4j import GraphDatabase
from config.settings import get_settings
from utils.document_parser import DocumentParser
from utils.llm_client import OllamaClient

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Build Neo4j graph from markdown documents."""
    
    def __init__(self, collection_name: str = "rules"):
        """
        Initialize GraphBuilder.
        
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
        self.parser = DocumentParser()
        logger.info(f"Initialized GraphBuilder for: {collection_name}")
    
    def build_from_directory(self, docs_dir: str) -> None:
        """
        Build graph from all markdown files in directory.
        
        Args:
            docs_dir: Path to directory containing markdown files
        """
        if not os.path.exists(docs_dir):
            logger.error(f"Directory not found: {docs_dir}")
            return
        
        # Get all markdown files
        md_files = list(Path(docs_dir).glob("**/*.md"))
        logger.info(f"Found {len(md_files)} markdown files in {docs_dir}")
        
        for md_file in md_files:
            logger.info(f"Processing: {md_file}")
            self.build_from_file(str(md_file))
    
    def build_from_file(self, file_path: str) -> None:
        """
        Build graph from a single markdown file.
        
        Args:
            file_path: Path to markdown file
        """
        doc_name = Path(file_path).stem
        
        # Extract headings
        headings = self.parser.extract_headings(file_path)
        
        if not headings:
            logger.warning(f"No headings found in {file_path}")
            return
        
        # Generate summaries for headings
        logger.info(f"Generating summaries for {len(headings)} headings...")
        for heading in headings:
            content = self.parser.get_content_by_lines(
                file_path,
                heading['line_start'],
                heading['line_end']
            )
            
            # Generate summary using LLM (limit content length)
            content_preview = content[:1000] if len(content) > 1000 else content
            
            if content_preview.strip():
                try:
                    summary = self._generate_summary(heading['title'], content_preview)
                    heading['summary'] = summary
                except Exception as e:
                    logger.warning(f"Error generating summary for {heading['id']}: {e}")
                    heading['summary'] = content_preview[:200]
            else:
                heading['summary'] = heading['title']
        
        # Build hierarchy
        edges = self.parser.build_hierarchy(headings)
        
        # Create Cypher commands
        cypher_commands = self._create_cypher_commands(doc_name, headings, edges)
        
        # Execute in Neo4j
        self._execute_cypher_commands(cypher_commands)
        
        logger.info(f"Successfully built graph for {doc_name}")
    
    def _generate_summary(self, title: str, content: str) -> str:
        """Generate summary using LLM."""
        prompt = f"""Summarize the following section in 50-100 words. Focus on key points, guidelines, and actionable information.

Section Title: {title}

Content:
{content}

Provide a concise summary:"""
        
        try:
            summary = self.llm_client.generate(
                prompt=prompt,
                system_prompt="You are a technical summarizer. Create concise, informative summaries.",
                temperature=0.3,
                max_tokens=150
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            # Fallback to first few sentences
            sentences = content.split('.')[:2]
            return '.'.join(sentences) + '.'
    
    def _create_cypher_commands(
        self,
        doc_name: str,
        headings: List[Dict[str, Any]],
        edges: List[tuple]
    ) -> List[str]:
        """Create Cypher commands for Neo4j."""
        commands = []
        
        # Create Document node
        commands.append(
            f"MERGE (d:Document {{name: '{doc_name}', type: '{self.collection_name}'}})"
        )
        
        # Create Heading nodes
        for heading in headings:
            # Escape single quotes in text
            title = heading['title'].replace("'", "\\'")
            summary = heading.get('summary', '').replace("'", "\\'")
            
            line_range = f"{heading['line_start']}-{heading['line_end']}"
            
            command = f"""
            MERGE (h:Heading {{
                id: '{heading['id']}',
                title: '{title}',
                level: {heading['level']},
                line: '{line_range}',
                summary: '{summary}'
            }})
            """
            commands.append(command)
        
        # Create edges (HAS_SUBSECTION relationships)
        for parent_id, child_id in edges:
            command = f"""
            MATCH (p:Heading {{id: '{parent_id}'}}), (c:Heading {{id: '{child_id}'}})
            MERGE (p)-[:HAS_SUBSECTION]->(c)
            """
            commands.append(command)
        
        # Link document to top-level headings
        top_level_headings = [h for h in headings if h['level'] == 1]
        for heading in top_level_headings:
            command = f"""
            MATCH (d:Document {{name: '{doc_name}'}}), (h:Heading {{id: '{heading['id']}'}})
            MERGE (d)-[:HAS_SUBSECTION]->(h)
            """
            commands.append(command)
        
        return commands
    
    def _execute_cypher_commands(self, commands: List[str]) -> None:
        """Execute Cypher commands in Neo4j."""
        with self.driver.session() as session:
            for command in commands:
                try:
                    session.run(command)
                except Exception as e:
                    logger.error(f"Error executing command: {e}")
                    logger.debug(f"Command: {command[:200]}...")
    
    def clear_collection(self) -> None:
        """Clear all nodes for this collection."""
        query = f"""
        MATCH (d:Document {{type: '{self.collection_name}'}})
        OPTIONAL MATCH (d)-[:HAS_SUBSECTION*]->(h:Heading)
        DETACH DELETE d, h
        """
        
        with self.driver.session() as session:
            session.run(query)
        
        logger.info(f"Cleared collection: {self.collection_name}")
    
    def close(self):
        """Close Neo4j connection."""
        self.driver.close()


def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Neo4j graph from markdown documents")
    parser.add_argument("--collection", choices=["rules", "protocols"], required=True)
    parser.add_argument("--docs-dir", required=True, help="Directory containing markdown files")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    builder = GraphBuilder(collection_name=args.collection)
    
    if args.clear:
        logger.info("Clearing existing data...")
        builder.clear_collection()
    
    builder.build_from_directory(args.docs_dir)
    builder.close()
    
    logger.info("Graph building complete!")


if __name__ == "__main__":
    main()

