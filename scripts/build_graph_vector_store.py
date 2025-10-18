#!/usr/bin/env python3
"""
Standalone script to build dual-embedding vector store from Neo4j graph and markdown documents.

This script reads graph nodes from Neo4j (created by HELD/app.py), extracts content from
markdown files, generates both summary and content embeddings using Ollama's embeddinggemma:latest,
and stores them in ChromaDB with a dual-collection configuration.

Usage:
    python scripts/build_graph_vector_store.py --docs-dir /path/to/docs --clear
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow INFO and WARNING messages

import sys
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data_ingestion.graph_vector_builder import GraphVectorBuilder
from utils.ollama_embeddings import OllamaEmbeddingsClient
from config.settings import get_settings


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def check_prerequisites():
    """Check if all required services are running."""
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    logger.info("Checking prerequisites...")
    
    # Check Ollama
    logger.info("  Checking Ollama connection...")
    try:
        embedding_client = OllamaEmbeddingsClient()
        if embedding_client.check_connection():
            logger.info(f"  ✓ Ollama connected (model: {settings.ollama_embedding_model})")
        else:
            logger.error("  ✗ Ollama connection failed")
            return False
    except Exception as e:
        logger.error(f"  ✗ Ollama error: {e}")
        return False
    
    # Check Neo4j
    logger.info("  Checking Neo4j connection...")
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        driver.verify_connectivity()
        driver.close()
        logger.info("  ✓ Neo4j connected")
    except Exception as e:
        logger.error(f"  ✗ Neo4j error: {e}")
        return False
    
    # Check ChromaDB
    logger.info("  Checking ChromaDB connection...")
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
        client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        collections = client.list_collections()
        logger.info(f"  ✓ ChromaDB connected ({len(collections)} collections)")
    except Exception as e:
        logger.error(f"  ✗ ChromaDB error: {e}")
        return False
    
    return True


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Build ChromaDB vector store from Neo4j graph and markdown documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build vector store with default collection names (summaries, documents)
  python scripts/build_graph_vector_store.py --docs-dir /storage03/Saboori/ActionPlan/HELD/docs/
  
  # Clear existing data and rebuild
  python scripts/build_graph_vector_store.py --docs-dir /storage03/Saboori/ActionPlan/HELD/docs/ --clear
  
  # Use custom collection names
  python scripts/build_graph_vector_store.py --docs-dir /path/to/docs/ --summary-collection protocol_summaries --content-collection protocol_content
  
  # Verbose output
  python scripts/build_graph_vector_store.py --docs-dir /path/to/docs/ --verbose
        """
    )
    
    parser.add_argument(
        "--summary-collection",
        default="summaries",
        help="ChromaDB collection name for summaries (default: summaries)"
    )
    parser.add_argument(
        "--content-collection",
        default="documents",
        help="ChromaDB collection name for content (default: documents)"
    )
    parser.add_argument(
        "--docs-dir",
        default="/storage03/Saboori/ActionPlan/HELD/docs/",
        help="Directory containing markdown source files"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collections before building"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip prerequisite checks"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("="*80)
    logger.info("Graph-Aware Vector Store Builder")
    logger.info("="*80)
    logger.info(f"Summary Collection: {args.summary_collection}")
    logger.info(f"Content Collection: {args.content_collection}")
    logger.info(f"Documents: {args.docs_dir}")
    logger.info(f"Clear existing: {args.clear}")
    logger.info("="*80)
    
    # Check if docs directory exists
    if not os.path.exists(args.docs_dir):
        logger.error(f"Documents directory not found: {args.docs_dir}")
        return 1
    
    # Check prerequisites
    if not args.skip_check:
        if not check_prerequisites():
            logger.error("\n✗ Prerequisite checks failed. Please ensure all services are running.")
            logger.error("  - Neo4j: Graph database with document nodes")
            logger.error("  - Ollama: Embedding service with embeddinggemma:latest model")
            logger.error("  - ChromaDB: Vector database path is writable")
            return 1
        logger.info("\n✓ All prerequisites satisfied\n")
    
    # Build vector store
    builder = GraphVectorBuilder(
        summary_collection=args.summary_collection,
        content_collection=args.content_collection
    )
    
    try:
        logger.info("Starting vector store build process...\n")
        
        builder.build_from_graph(
            docs_dir=args.docs_dir,
            clear_existing=args.clear
        )
        
        # Show final statistics
        logger.info("\n" + "="*80)
        logger.info("Build Complete - Statistics")
        logger.info("="*80)
        
        stats = builder.get_stats()
        if stats:
            logger.info(f"Summary Collection: {stats.get('summary_collection', {}).get('name')} ({stats.get('summary_collection', {}).get('count', 0):,} points)")
            logger.info(f"Content Collection: {stats.get('content_collection', {}).get('name')} ({stats.get('content_collection', {}).get('count', 0):,} points)")
        
        logger.info("="*80)
        logger.info("✓ Vector store build completed successfully!")
        logger.info("="*80)
        
        logger.info("\nYou can now use the GraphAwareRAG module to query with different modes:")
        logger.info("  - node_name: Fast keyword/title matching")
        logger.info("  - summary: Search using summary embeddings")
        logger.info("  - content: Search using content embeddings")
        logger.info("  - automatic: Dynamic mode selection based on query")
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\n\nBuild interrupted by user")
        return 130
        
    except Exception as e:
        logger.error(f"\n\n✗ Build failed with error: {e}", exc_info=args.verbose)
        return 1
        
    finally:
        builder.close()
        logger.info("\nConnections closed.")


if __name__ == "__main__":
    sys.exit(main())

