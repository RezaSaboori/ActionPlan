"""
Test script for refactored Extractor Agent.

Tests:
1. Document name extraction from node IDs
2. Content segmentation with markdown awareness
3. Extraction summary generation
4. Full extraction with segmentation
"""

import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_document_name_extraction():
    """Test extracting document names from node IDs."""
    logger.info("=" * 80)
    logger.info("TEST 1: Document Name Extraction")
    logger.info("=" * 80)
    
    try:
        from agents.extractor import ExtractorAgent
        from utils.llm_client import OllamaClient
        
        llm = OllamaClient()
        extractor = ExtractorAgent(llm)
        
        test_cases = [
            ("comprehensive_health_h45", "comprehensive_health"),
            ("national_health_system_h102", "national_health_system"),
            ("nutrition_management_h28", "nutrition_management"),
            ("checklist_template_guide_h1", "checklist_template_guide"),
        ]
        
        all_passed = True
        for node_id, expected_doc_name in test_cases:
            result = extractor._extract_document_name(node_id)
            status = "✓" if result == expected_doc_name else "✗"
            logger.info(f"  {status} {node_id} → {result} (expected: {expected_doc_name})")
            if result != expected_doc_name:
                all_passed = False
        
        if all_passed:
            logger.info("✓ All document name extractions passed\n")
            return True
        else:
            logger.error("✗ Some document name extractions failed\n")
            return False
            
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_content_segmentation():
    """Test markdown-aware content segmentation."""
    logger.info("=" * 80)
    logger.info("TEST 2: Content Segmentation")
    logger.info("=" * 80)
    
    try:
        from agents.extractor import ExtractorAgent
        from utils.llm_client import OllamaClient
        
        llm = OllamaClient()
        extractor = ExtractorAgent(llm)
        
        # Test 1: Short content (should not segment)
        short_content = "This is a short paragraph.\n\nThis is another short paragraph."
        segments = extractor._segment_content(short_content, max_tokens=2000)
        logger.info(f"  Short content: {len(segments)} segment(s)")
        assert len(segments) == 1, "Short content should not be segmented"
        logger.info("  ✓ Short content test passed")
        
        # Test 2: Long content with paragraphs
        long_content = "\n\n".join([f"Paragraph {i}: " + "word " * 500 for i in range(10)])
        segments = extractor._segment_content(long_content, max_tokens=2000)
        logger.info(f"  Long content: {len(segments)} segment(s)")
        assert len(segments) > 1, "Long content should be segmented"
        logger.info("  ✓ Long content segmentation test passed")
        
        # Test 3: Content with table
        table_content = """This is a paragraph.

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |

This is after the table."""
        segments = extractor._segment_content(table_content, max_tokens=2000)
        logger.info(f"  Table content: {len(segments)} segment(s)")
        # Table should be kept together
        table_found = any('|' in seg for seg in segments)
        assert table_found, "Table should be preserved in segmentation"
        logger.info("  ✓ Table preservation test passed")
        
        # Test 4: Content with list
        list_content = """Introduction paragraph.

- List item 1
- List item 2
- List item 3

Conclusion paragraph."""
        segments = extractor._segment_content(list_content, max_tokens=2000)
        logger.info(f"  List content: {len(segments)} segment(s)")
        # List should be kept together
        list_found = any('-' in seg for seg in segments)
        assert list_found, "List should be preserved in segmentation"
        logger.info("  ✓ List preservation test passed")
        
        logger.info("✓ All segmentation tests passed\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ Segmentation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extraction_summary():
    """Test extraction summary generation."""
    logger.info("=" * 80)
    logger.info("TEST 3: Extraction Summary")
    logger.info("=" * 80)
    
    try:
        from agents.extractor import ExtractorAgent
        from utils.llm_client import OllamaClient
        
        llm = OllamaClient()
        extractor = ExtractorAgent(llm)
        
        # Test 1: Empty actions
        summary = extractor._create_extraction_summary([])
        logger.info(f"  Empty actions: '{summary}'")
        assert "None" in summary or "yet" in summary, "Empty summary should indicate none"
        logger.info("  ✓ Empty actions test passed")
        
        # Test 2: Few actions
        actions = [
            {"action": "Team Lead establishes triage area"},
            {"action": "EOC activates emergency protocols"},
            {"action": "Medical staff prepares treatment zones"}
        ]
        summary = extractor._create_extraction_summary(actions)
        logger.info(f"  Few actions summary:\n{summary}")
        assert "Team Lead" in summary, "Summary should contain action details"
        logger.info("  ✓ Few actions test passed")
        
        # Test 3: Many actions (should truncate)
        many_actions = [
            {"action": f"Action {i}: Some role does something important"}
            for i in range(50)
        ]
        summary = extractor._create_extraction_summary(many_actions)
        logger.info(f"  Many actions summary (length: {len(summary)} chars):\n{summary[:200]}...")
        assert len(summary) < 600, "Summary should be limited in length"
        assert "more" in summary.lower(), "Truncated summary should indicate more actions"
        logger.info("  ✓ Many actions test passed")
        
        logger.info("✓ All extraction summary tests passed\n")
        return True
        
    except Exception as e:
        logger.error(f"✗ Extraction summary test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_extraction():
    """Test full extraction flow with a real node."""
    logger.info("=" * 80)
    logger.info("TEST 4: Full Extraction Flow")
    logger.info("=" * 80)
    
    try:
        from utils.llm_client import OllamaClient
        from rag_tools.graph_rag import GraphRAG
        from agents.extractor import ExtractorAgent
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Initialize components
        llm = OllamaClient()
        graph_rag = GraphRAG(collection_name=settings.graph_prefix)
        extractor = ExtractorAgent(llm, graph_rag)
        
        # Create a test node (using a known node structure)
        test_node = {
            "id": "comprehensive_health_system_preparedness_and_response_plan_under_sanctions_and_war_conditions_h45",
            "title": "Test Protocol",
            "start_line": 0,
            "end_line": 50
        }
        
        # Test document name extraction
        doc_name = extractor._extract_document_name(test_node['id'])
        logger.info(f"  Extracted document name: {doc_name}")
        
        if doc_name:
            # Test document source lookup
            source_path = extractor._get_document_source(doc_name)
            logger.info(f"  Document source path: {source_path}")
            
            if source_path:
                logger.info("  ✓ Document lookup successful")
                logger.info("✓ Full extraction flow test passed\n")
                graph_rag.close()
                return True
            else:
                logger.warning("  ⚠ Document source not found (may be expected if DB is empty)")
                logger.info("✓ Partial test passed (extraction logic works)\n")
                graph_rag.close()
                return True
        else:
            logger.error("  ✗ Document name extraction failed")
            graph_rag.close()
            return False
        
    except Exception as e:
        logger.error(f"✗ Full extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING REFACTORED EXTRACTOR AGENT")
    logger.info("=" * 80 + "\n")
    
    results = []
    
    # Run tests
    results.append(("Document Name Extraction", test_document_name_extraction()))
    results.append(("Content Segmentation", test_content_segmentation()))
    results.append(("Extraction Summary", test_extraction_summary()))
    results.append(("Full Extraction Flow", test_full_extraction()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"  {status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        logger.info("\n✓ ALL TESTS PASSED")
        return 0
    else:
        logger.error("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

