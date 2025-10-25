#!/usr/bin/env python3
"""
Add Embeddings to Neo4j Script

Generates embeddings for all Heading nodes and stores them in Neo4j
as the summary_embedding property for use with GraphAwareRAG.
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from neo4j import GraphDatabase
from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient
from tqdm import tqdm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def add_embeddings_to_neo4j():
    """Add summary embeddings to all Heading nodes in Neo4j."""
    settings = get_settings()
    
    logger.info("=" * 70)
    logger.info("ADDING EMBEDDINGS TO NEO4J NODES")
    logger.info("=" * 70)
    
    # Initialize connections
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    embedding_client = OllamaEmbeddingsClient()
    
    try:
        # Get all heading nodes
        with driver.session() as session:
            result = session.run("""
                MATCH (h:Heading)
                RETURN h.id as node_id, h.title as title, h.summary as summary
            """)
            nodes = list(result)
        
        total_nodes = len(nodes)
        logger.info(f"Found {total_nodes} heading nodes to process")
        
        if total_nodes == 0:
            logger.warning("No heading nodes found in Neo4j. Run ingestion first!")
            return False
        
        # Process each node
        success_count = 0
        error_count = 0
        
        for node in tqdm(nodes, desc="Generating embeddings"):
            node_id = node['node_id']
            title = node['title'] or ''
            summary = node['summary'] or ''
            
            # Use summary if available, otherwise use title
            text_to_embed = summary if summary else title
            
            if not text_to_embed:
                logger.warning(f"Node {node_id} has no text to embed, skipping")
                error_count += 1
                continue
            
            try:
                # Generate embedding
                embedding = embedding_client.embed(text_to_embed)
                
                # Store in Neo4j
                with driver.session() as session:
                    session.run("""
                        MATCH (h:Heading {id: $node_id})
                        SET h.summary_embedding = $embedding
                    """, node_id=node_id, embedding=embedding)
                
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error processing node {node_id}: {e}")
                error_count += 1
        
        logger.info("=" * 70)
        logger.info("EMBEDDING GENERATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Total nodes: {total_nodes}")
        logger.info(f"Successfully embedded: {success_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Success rate: {(success_count/total_nodes)*100:.2f}%")
        
        return success_count > 0
        
    finally:
        driver.close()


if __name__ == "__main__":
    try:
        success = add_embeddings_to_neo4j()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

