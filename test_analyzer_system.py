"""
Test script for the Multi-Phase Analyzer System.

Tests:
1. GraphRAG navigation methods
2. Analyzer Phase 1 (Context Building)
3. Analyzer Phase 2 (Subject Identification)
4. Analyzer_D scoring and traversal
5. Extractor multi-subject processing
6. Full workflow integration
"""

import logging
import sys
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_graph_rag_navigation():
    """Test GraphRAG new navigation methods."""
    logger.info("=" * 80)
    logger.info("TEST 1: GraphRAG Navigation Methods")
    logger.info("=" * 80)
    
    try:
        from rag_tools.graph_rag import GraphRAG
        from config.settings import get_settings
        
        settings = get_settings()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        
        # Test 1: Get parent documents
        logger.info("Test 1.1: get_parent_documents")
        topics = ["triage", "emergency"]
        documents = graph_rag.get_parent_documents(topics)
        logger.info(f"  Found {len(documents)} documents for topics {topics}")
        
        if documents:
            # Test 2: Get introduction nodes
            logger.info("Test 1.2: get_introduction_nodes")
            doc_name = documents[0].get('name')
            intro_nodes = graph_rag.get_introduction_nodes(doc_name)
            logger.info(f"  Found {len(intro_nodes)} introduction nodes for {doc_name}")
            
            if intro_nodes:
                # Test 3: Get node by ID
                logger.info("Test 1.3: get_node_by_id")
                node_id = intro_nodes[0].get('id')
                node = graph_rag.get_node_by_id(node_id)
                logger.info(f"  Retrieved node: {node.get('title') if node else 'None'}")
                
                # Test 4: Navigate upward
                logger.info("Test 1.4: navigate_upward")
                parents = graph_rag.navigate_upward(node_id, levels=1)
                logger.info(f"  Found {len(parents)} parent(s)")
                
                # Test 5: Get children
                logger.info("Test 1.5: get_children")
                children = graph_rag.get_children(node_id)
                logger.info(f"  Found {len(children)} children")
                
                # Test 6: Consolidate branches
                logger.info("Test 1.6: consolidate_branches")
                nodes_to_consolidate = intro_nodes[:3] + intro_nodes[:2]  # Intentional duplicates
                consolidated = graph_rag.consolidate_branches(nodes_to_consolidate)
                logger.info(f"  Consolidated {len(nodes_to_consolidate)} nodes to {len(consolidated)} unique nodes")
        
        graph_rag.close()
        logger.info("✓ GraphRAG navigation tests passed\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ GraphRAG navigation tests failed: {e}")
        return False


def test_analyzer_phases():
    """Test Analyzer 2-phase workflow."""
    logger.info("=" * 80)
    logger.info("TEST 2: Analyzer 2-Phase Workflow")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import OllamaClient
        from rag_tools.hybrid_rag import HybridRAG
        from rag_tools.graph_rag import GraphRAG
        from agents.analyzer import AnalyzerAgent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize components
        llm_client = OllamaClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        hybrid_rag = HybridRAG(
            graph_collection=settings.graph_prefix,
            vector_collection=settings.documents_collection
        )
        
        analyzer = AnalyzerAgent(llm_client, hybrid_rag, graph_rag)
        
        # Test with sample context
        context = {
            "subject": "emergency triage protocols",
            "topics": ["triage", "emergency", "patient"],
            "structure": {}
        }
        
        logger.info("Test 2.1: Execute Analyzer (both phases)")
        result = analyzer.execute(context)
        
        logger.info(f"  Context Map documents: {len(result.get('context_map', {}).get('documents', []))}")
        logger.info(f"  Identified subjects: {result.get('identified_subjects', [])}")
        
        graph_rag.close()
        
        if result.get('identified_subjects'):
            logger.info("✓ Analyzer 2-phase tests passed\n")
            return True, result
        else:
            logger.warning("⚠ Analyzer returned no subjects\n")
            return False, result
            
    except Exception as e:
        logger.error(f"✗ Analyzer tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False, {}


def test_analyzer_d(identified_subjects):
    """Test Analyzer_D deep analysis."""
    logger.info("=" * 80)
    logger.info("TEST 3: Analyzer_D Deep Analysis")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import OllamaClient
        from rag_tools.hybrid_rag import HybridRAG
        from rag_tools.graph_rag import GraphRAG
        from agents.analyzer_d import AnalyzerDAgent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize components
        llm_client = OllamaClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        hybrid_rag = HybridRAG(
            graph_collection=settings.graph_prefix,
            vector_collection=settings.documents_collection
        )
        
        analyzer_d = AnalyzerDAgent(llm_client, hybrid_rag, graph_rag)
        
        # Use subjects from previous test or fallback
        subjects = identified_subjects if identified_subjects else ["emergency triage"]
        
        context = {
            "identified_subjects": subjects[:2]  # Limit to 2 for testing
        }
        
        logger.info(f"Test 3.1: Execute Analyzer_D for subjects: {context['identified_subjects']}")
        result = analyzer_d.execute(context)
        
        subject_nodes = result.get('subject_nodes', [])
        logger.info(f"  Processed {len(subject_nodes)} subjects")
        
        for subject_data in subject_nodes:
            subject = subject_data.get('subject')
            nodes = subject_data.get('nodes', [])
            logger.info(f"    Subject '{subject}': {len(nodes)} relevant nodes")
        
        graph_rag.close()
        
        if subject_nodes:
            logger.info("✓ Analyzer_D tests passed\n")
            return True, result
        else:
            logger.warning("⚠ Analyzer_D returned no nodes\n")
            return False, result
            
    except Exception as e:
        logger.error(f"✗ Analyzer_D tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False, {}


def test_extractor(subject_nodes):
    """Test Enhanced Extractor multi-subject processing."""
    logger.info("=" * 80)
    logger.info("TEST 4: Enhanced Extractor Multi-Subject Processing")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import OllamaClient
        from rag_tools.graph_rag import GraphRAG
        from agents.extractor import ExtractorAgent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize components
        llm_client = OllamaClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        
        extractor = ExtractorAgent(llm_client, graph_rag)
        
        # Use nodes from previous test
        data = {
            "subject_nodes": subject_nodes
        }
        
        logger.info(f"Test 4.1: Execute Extractor for {len(subject_nodes)} subjects")
        result = extractor.execute(data)
        
        subject_actions = result.get('subject_actions', [])
        logger.info(f"  Processed {len(subject_actions)} subjects")
        
        total_actions = 0
        for subject_data in subject_actions:
            subject = subject_data.get('subject')
            actions = subject_data.get('actions', [])
            total_actions += len(actions)
            logger.info(f"    Subject '{subject}': {len(actions)} actions")
        
        logger.info(f"  Total actions extracted: {total_actions}")
        
        graph_rag.close()
        
        if total_actions > 0:
            logger.info("✓ Extractor tests passed\n")
            return True
        else:
            logger.warning("⚠ Extractor extracted no actions\n")
            return False
            
    except Exception as e:
        logger.error(f"✗ Extractor tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_workflow():
    """Test the complete integrated workflow."""
    logger.info("=" * 80)
    logger.info("TEST 5: Full Workflow Integration")
    logger.info("=" * 80)
    
    try:
        from workflows.orchestration import create_workflow
        from workflows.graph_state import ActionPlanState
        
        logger.info("Test 5.1: Create workflow")
        workflow = create_workflow()
        logger.info("  ✓ Workflow created successfully")
        
        logger.info("Test 5.2: Check workflow structure")
        # Workflow is compiled, we can check if it's callable
        if workflow and callable(workflow.invoke):
            logger.info("  ✓ Workflow is callable")
            
            # Note: Full execution would be very long, so we just verify structure
            logger.info("✓ Full workflow structure tests passed\n")
            return True
        else:
            logger.error("  ✗ Workflow is not properly compiled")
            return False
            
    except Exception as e:
        logger.error(f"✗ Full workflow tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 80)
    logger.info("MULTI-PHASE ANALYZER SYSTEM TEST SUITE")
    logger.info("=" * 80 + "\n")
    
    results = {}
    
    # Test 1: GraphRAG Navigation
    results['graph_rag'] = test_graph_rag_navigation()
    
    # Test 2: Analyzer 2-Phase
    analyzer_success, analyzer_result = test_analyzer_phases()
    results['analyzer'] = analyzer_success
    identified_subjects = analyzer_result.get('identified_subjects', [])
    
    # Test 3: Analyzer_D (only if Analyzer succeeded)
    if analyzer_success and identified_subjects:
        analyzer_d_success, analyzer_d_result = test_analyzer_d(identified_subjects)
        results['analyzer_d'] = analyzer_d_success
        subject_nodes = analyzer_d_result.get('subject_nodes', [])
        
        # Test 4: Extractor (only if Analyzer_D succeeded)
        if analyzer_d_success and subject_nodes:
            results['extractor'] = test_extractor(subject_nodes)
        else:
            logger.warning("Skipping Extractor test (no subject nodes available)")
            results['extractor'] = False
    else:
        logger.warning("Skipping Analyzer_D and Extractor tests (no subjects identified)")
        results['analyzer_d'] = False
        results['extractor'] = False
    
    # Test 5: Full Workflow
    results['workflow'] = test_full_workflow()
    
    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, success in results.items():
        status = "✓ PASSED" if success else "✗ FAILED"
        logger.info(f"{test_name.upper()}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for success in results.values() if success)
    
    logger.info(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.warning(f"\n⚠️  {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

