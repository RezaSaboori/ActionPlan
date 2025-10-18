"""Test script for RAG with Neo4j-stored embeddings."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_tools.graph_aware_rag import GraphAwareRAG
from utils.ollama_embeddings import OllamaEmbeddingsClient
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_embedding_client():
    """Test that the embedding client is working."""
    logger.info("Testing Ollama Embedding Client...")
    client = OllamaEmbeddingsClient()
    
    # Check connection
    if not client.check_connection():
        logger.error("Failed to connect to Ollama. Make sure Ollama is running.")
        return False
    
    logger.info("✓ Ollama connection successful")
    
    # Test single embedding
    test_text = "This is a test summary for health emergency response."
    embedding = client.embed(test_text)
    logger.info(f"✓ Generated embedding with dimension: {len(embedding)}")
    
    # Test batch embeddings
    test_texts = [
        "Emergency response protocols",
        "Health system preparedness",
        "Disaster management guidelines"
    ]
    embeddings = client.embed_batch(test_texts)
    logger.info(f"✓ Generated {len(embeddings)} embeddings in batch")
    
    return True


def test_summary_retrieval():
    """Test retrieval using Neo4j-stored summary embeddings."""
    logger.info("\nTesting Summary Retrieval from Neo4j...")
    
    rag = GraphAwareRAG()
    
    # Test queries
    test_queries = [
        "What are the emergency response protocols?",
        "Health system preparedness guidelines",
        "Disaster management procedures",
        "How to handle mass casualty incidents?",
        "Strategic coordination in emergencies"
    ]
    
    for query in test_queries:
        logger.info(f"\n--- Query: {query} ---")
        results = rag.retrieve(query, mode="summary", top_k=3)
        
        if results:
            logger.info(f"Found {len(results)} results:")
            for i, result in enumerate(results, 1):
                logger.info(f"{i}. {result['title']}")
                logger.info(f"   Score: {result['score']:.4f}")
                logger.info(f"   Summary: {result['text'][:100]}...")
        else:
            logger.warning("No results found")
    
    rag.close()
    return True


def test_hybrid_retrieval():
    """Test hybrid retrieval combining embeddings and graph structure."""
    logger.info("\nTesting Hybrid Retrieval...")
    
    rag = GraphAwareRAG()
    
    test_query = "emergency response coordination and preparedness"
    
    logger.info(f"\n--- Query: {test_query} ---")
    results = rag.hybrid_retrieve(test_query, top_k=5)
    
    if results:
        logger.info(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. {result['title']}")
            logger.info(f"   Combined Score: {result.get('combined_score', 0):.4f}")
            logger.info(f"   Node ID: {result['node_id']}")
            logger.info(f"   Level: {result.get('level', 'N/A')}")
            
            # Show parent context if available
            if 'parent' in result.get('metadata', {}):
                parent = result['metadata']['parent']
                logger.info(f"   Parent: {parent.get('title', 'N/A')}")
            
            # Show children if available
            children = result.get('metadata', {}).get('children', [])
            if children:
                logger.info(f"   Children: {len(children)} subsections")
    else:
        logger.warning("No results found")
    
    rag.close()
    return True


def test_expanded_hybrid_retrieval():
    """Test advanced hybrid retrieval with graph expansion."""
    logger.info("\nTesting Hybrid Retrieval with Graph Expansion...")
    
    rag = GraphAwareRAG()
    
    test_query = "health emergency management in disasters"
    
    logger.info(f"\n--- Query: {test_query} ---")
    results = rag.hybrid_retrieve_with_graph_expansion(test_query, top_k=5, expansion_depth=1)
    
    if results:
        logger.info(f"Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. {result['title']}")
            logger.info(f"   Total Score: {result.get('score', 0):.4f}")
            logger.info(f"   Primary Score: {result.get('primary_score', 0):.4f}")
            logger.info(f"   Related Boost: {result.get('related_boost', 0):.4f}")
            logger.info(f"   Related Nodes: {result.get('metadata', {}).get('related_count', 0)}")
            logger.info(f"   Summary: {result['text'][:150]}...")
    else:
        logger.warning("No results found")
    
    rag.close()
    return True


def test_all_retrieval_modes():
    """Test all retrieval modes."""
    logger.info("\nTesting All Retrieval Modes...")
    
    rag = GraphAwareRAG()
    test_query = "emergency operations center functions"
    
    modes = ["node_name", "summary", "content", "automatic"]
    
    for mode in modes:
        logger.info(f"\n--- Mode: {mode} ---")
        try:
            results = rag.retrieve(test_query, mode=mode, top_k=3)
            logger.info(f"✓ {mode} retrieval: {len(results)} results")
            if results:
                logger.info(f"   Top result: {results[0]['title']}")
        except Exception as e:
            logger.error(f"✗ {mode} retrieval failed: {e}")
    
    rag.close()
    return True


def main():
    """Run all tests."""
    logger.info("="*80)
    logger.info("RAG with Neo4j Embeddings - Test Suite")
    logger.info("="*80)
    
    tests = [
        ("Embedding Client", test_embedding_client),
        ("Summary Retrieval", test_summary_retrieval),
        ("Hybrid Retrieval", test_hybrid_retrieval),
        ("Expanded Hybrid Retrieval", test_expanded_hybrid_retrieval),
        ("All Retrieval Modes", test_all_retrieval_modes),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            logger.info(f"\n{'='*80}")
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            logger.error(f"Test '{test_name}' failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("Test Summary:")
    logger.info("="*80)
    for test_name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} tests passed")


if __name__ == "__main__":
    main()

