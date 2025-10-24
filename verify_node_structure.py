"""
Verification script to check that nodes from phase3 contain the 'source' field.

This script:
1. Runs a simple phase3 query
2. Inspects the returned node structure
3. Verifies that each node has the required fields including 'source'
"""

import logging
import sys
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_node_structure():
    """Verify that phase3 nodes contain all required fields including 'source'."""
    
    logger.info("=" * 80)
    logger.info("VERIFYING phase3 NODE STRUCTURE")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import LLMClient
        from rag_tools.hybrid_rag import HybridRAG
        from rag_tools.graph_rag import GraphRAG
        from agents.phase3 import Phase3Agent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize components
        logger.info("Initializing components...")
        llm_client = LLMClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        hybrid_rag = HybridRAG(
            graph_collection=settings.graph_prefix,
            vector_collection=settings.documents_collection
        )
        
        phase3 = Phase3Agent(llm_client, hybrid_rag, graph_rag)
        
        # Test with a simple subject
        test_subject = "triage classification systems"
        logger.info(f"\nTesting with subject: '{test_subject}'")
        
        context = {
            "identified_subjects": [test_subject]
        }
        
        logger.info("Running phase3...")
        result = phase3.execute(context)
        
        subject_nodes = result.get('subject_nodes', [])
        logger.info(f"\nphase3 returned {len(subject_nodes)} subject groups")
        
        # Verify node structure
        required_fields = ['id', 'title', 'level', 'start_line', 'end_line', 'summary', 'source']
        
        verification_passed = True
        
        for subject_data in subject_nodes:
            subject = subject_data.get('subject', 'Unknown')
            nodes = subject_data.get('nodes', [])
            
            logger.info(f"\n{'='*80}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Number of nodes: {len(nodes)}")
            logger.info(f"{'='*80}")
            
            if not nodes:
                logger.warning(f"  ⚠ No nodes found for subject '{subject}'")
                continue
            
            # Check first 3 nodes in detail
            for idx, node in enumerate(nodes[:3], 1):
                logger.info(f"\n  Node {idx}:")
                logger.info(f"    ID: {node.get('id', 'MISSING')}")
                logger.info(f"    Title: {node.get('title', 'MISSING')}")
                logger.info(f"    Level: {node.get('level', 'MISSING')}")
                logger.info(f"    Start Line: {node.get('start_line', 'MISSING')}")
                logger.info(f"    End Line: {node.get('end_line', 'MISSING')}")
                logger.info(f"    Summary: {node.get('summary', 'MISSING')}")
                logger.info(f"    Source: {node.get('source', 'MISSING')}")
                logger.info(f"    Relevance Score: {node.get('relevance_score', 'MISSING')}")
                
                # Check for missing required fields
                missing_fields = [field for field in required_fields if field not in node or node[field] is None]
                
                if missing_fields:
                    logger.error(f"    ✗ MISSING REQUIRED FIELDS: {missing_fields}")
                    verification_passed = False
                else:
                    logger.info(f"    ✓ All required fields present")
                
                # Verify source is a valid path
                source = node.get('source')
                if source:
                    import os
                    if os.path.exists(source):
                        logger.info(f"    ✓ Source file exists: {source}")
                    else:
                        logger.warning(f"    ⚠ Source file NOT FOUND: {source}")
                        # This might not be an error if the path is relative
            
            # Summary for remaining nodes
            if len(nodes) > 3:
                logger.info(f"\n  ... and {len(nodes) - 3} more nodes")
                
                # Check all nodes for source field
                nodes_without_source = [n.get('id', 'Unknown') for n in nodes if 'source' not in n or not n['source']]
                if nodes_without_source:
                    logger.error(f"  ✗ {len(nodes_without_source)} nodes missing 'source' field:")
                    for node_id in nodes_without_source[:5]:
                        logger.error(f"      - {node_id}")
                    if len(nodes_without_source) > 5:
                        logger.error(f"      ... and {len(nodes_without_source) - 5} more")
                    verification_passed = False
                else:
                    logger.info(f"  ✓ All {len(nodes)} nodes have 'source' field")
        
        graph_rag.close()
        
        logger.info(f"\n{'='*80}")
        if verification_passed:
            logger.info("✓ VERIFICATION PASSED: All nodes contain required fields including 'source'")
            logger.info("The Extractor Agent should be able to read content from these nodes.")
        else:
            logger.error("✗ VERIFICATION FAILED: Some nodes are missing required fields")
            logger.error("This will cause the Extractor Agent to fail when trying to read content.")
        logger.info(f"{'='*80}")
        
        return verification_passed
        
    except Exception as e:
        logger.error(f"✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_node_structure()
    sys.exit(0 if success else 1)

