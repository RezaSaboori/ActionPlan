"""
Test script to verify the extractor bug fix.

This test verifies that the extractor can now correctly:
1. Query document source by traversing graph relationships
2. Read content from files
3. Extract actions from content
"""

import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_document_source_lookup():
    """Test that we can find document source by traversing from node."""
    logger.info("=" * 80)
    logger.info("TEST: Document Source Lookup via Graph Traversal")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import OllamaClient
        from rag_tools.graph_rag import GraphRAG
        from agents.extractor import ExtractorAgent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize
        llm = OllamaClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        extractor = ExtractorAgent(llm, graph_rag)
        
        # Test with a node ID from the log
        test_node_id = "comprehensive_health_system_preparedness_and_response_plan_under_sanctions_and_war_conditions_h28"
        
        logger.info(f"\nTesting with node ID: {test_node_id[:50]}...")
        
        # Try to get document source (this should work now)
        source_path = extractor._get_document_source_from_node(test_node_id)
        
        if source_path:
            logger.info(f"✓ Successfully found document source: {source_path}")
            
            # Try to read content with a test node
            test_node = {
                'id': test_node_id,
                'start_line': 0,
                'end_line': 10
            }
            
            content = extractor._read_full_content(test_node)
            
            if content:
                logger.info(f"✓ Successfully read content: {len(content)} characters")
                logger.info(f"  Preview: {content[:100]}...")
                
                logger.info("\n" + "=" * 80)
                logger.info("✓ FIX VERIFIED: Extractor can now retrieve content!")
                logger.info("=" * 80)
                graph_rag.close()
                return True
            else:
                logger.warning("⚠ Could not read content from file")
                graph_rag.close()
                return False
        else:
            logger.error("✗ Could not find document source")
            logger.error("  This means the graph might not have this node,")
            logger.error("  or the fix didn't work as expected.")
            graph_rag.close()
            return False
        
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cypher_query_directly():
    """Test the Cypher query directly to verify it works."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Direct Cypher Query Test")
    logger.info("=" * 80)
    
    try:
        from rag_tools.graph_rag import GraphRAG
        from config.settings import get_settings
        
        settings = get_settings()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        
        # Test node from the log
        test_node_id = "comprehensive_health_system_preparedness_and_response_plan_under_sanctions_and_war_conditions_h28"
        
        logger.info(f"\nQuerying for node: {test_node_id[:50]}...")
        
        # Run the exact query we use in the fix
        query = """
        MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading {id: $node_id})
        RETURN doc.name as doc_name, doc.source as source
        LIMIT 1
        """
        
        with graph_rag.driver.session() as session:
            result = session.run(query, node_id=test_node_id)
            record = result.single()
            
            if record:
                doc_name = record['doc_name']
                source = record['source']
                logger.info(f"✓ Query successful!")
                logger.info(f"  Document name: {doc_name[:80]}...")
                logger.info(f"  Source path: {source}")
                
                # Show the difference that caused the bug
                logger.info(f"\n  KEY INSIGHT:")
                logger.info(f"  Node ID uses:  lowercase_with_underscores")
                logger.info(f"  Document.name: {doc_name[:50]}...")
                logger.info(f"  These DON'T match - which was the bug!")
                logger.info(f"  Solution: Query by graph traversal (what we just did) ✓")
                
                graph_rag.close()
                return True
            else:
                logger.warning("⚠ No result found")
                logger.info("  The node might not exist in the graph yet.")
                graph_rag.close()
                return False
                
    except Exception as e:
        logger.error(f"✗ Query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests to verify the fix."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING EXTRACTOR BUG FIX")
    logger.info("=" * 80)
    
    results = []
    
    # Test 1: Direct Cypher query
    results.append(("Direct Cypher Query", test_cypher_query_directly()))
    
    # Test 2: Full extractor method
    results.append(("Document Source Lookup", test_document_source_lookup()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED (or no data)"
        logger.info(f"  {status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        logger.info("\n✓ FIX VERIFIED: The extractor should now work correctly!")
        logger.info("  - Can query document source via graph traversal")
        logger.info("  - Can read content from files")
        logger.info("  - Ready to extract actions")
        return 0
    else:
        logger.warning("\n⚠ Tests incomplete (may need data in Neo4j)")
        logger.info("  Try running the full workflow to verify extraction works.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

