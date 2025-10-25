#!/usr/bin/env python3
"""
Test Analyzer Fix Script

Tests the analyzer with the problematic query that previously returned
irrelevant reproductive health nodes, and validates that the fix works.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from config.settings import get_settings
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_analyzer_fix():
    """Test the analyzer fix with the problematic query."""
    settings = get_settings()
    
    print("=" * 80)
    print("TESTING ANALYZER FIX - EMERGENCY TRIAGE QUERY")
    print("=" * 80)
    print()
    
    # Initialize RAG tools
    hybrid_rag = HybridRAG(
        graph_collection=settings.graph_prefix,
        vector_collection=settings.documents_collection,
        use_graph_aware=True
    )
    
    # The problematic query that returned reproductive health nodes
    test_query = """Identify the triage categories, decision-making criteria, and resource-allocation 
matrix described in the 'Emergency Logistics and Supply Chain Management in Urban 
Warfare and Disaster Conditions' guideline, and outline how these can be operationalized 
in a Code Orange triage protocol."""
    
    print("TEST QUERY:")
    print(f'"{test_query}"')
    print()
    print("-" * 80)
    print()
    
    # Execute query using hybrid strategy (same as analyzer uses)
    try:
        results = hybrid_rag.query(
            test_query,
            strategy="hybrid",
            top_k=10
        )
        
        print(f"RESULTS: Found {len(results)} nodes")
        print()
        
        # Analyze results
        reproductive_health_count = 0
        relevant_count = 0
        scores = []
        
        for i, result in enumerate(results, 1):
            metadata = result.get('metadata', {})
            node_id = metadata.get('node_id', 'unknown')
            title = metadata.get('title', 'Unknown')
            score = result.get('score', 0.0)
            scores.append(score)
            
            # Check if it's a reproductive health node
            is_reproductive = 'reproductive_health' in node_id.lower()
            
            if is_reproductive:
                reproductive_health_count += 1
                status = "❌ IRRELEVANT (Reproductive Health)"
            else:
                relevant_count += 1
                status = "✓ Potentially Relevant"
            
            print(f"{i}. {status}")
            print(f"   Node ID: {node_id}")
            print(f"   Title: {title}")
            print(f"   Score: {score:.4f}")
            print()
        
        print("=" * 80)
        print("TEST RESULTS SUMMARY")
        print("=" * 80)
        print()
        
        # Score analysis
        if scores:
            min_score = min(scores)
            max_score = max(scores)
            avg_score = sum(scores) / len(scores)
            all_same = all(s == scores[0] for s in scores)
            
            print(f"Score Analysis:")
            print(f"  Min Score: {min_score:.4f}")
            print(f"  Max Score: {max_score:.4f}")
            print(f"  Avg Score: {avg_score:.4f}")
            print(f"  All scores identical: {'Yes (BAD - no semantic ranking)' if all_same else 'No (GOOD - semantic ranking working)'}")
            print()
        
        # Relevance analysis
        print(f"Relevance Analysis:")
        print(f"  Relevant nodes: {relevant_count}")
        print(f"  Irrelevant (reproductive health): {reproductive_health_count}")
        print()
        
        # Final verdict
        print("=" * 80)
        print("FINAL VERDICT")
        print("=" * 80)
        print()
        
        passed = True
        
        # Check 1: No reproductive health nodes
        if reproductive_health_count > 0:
            print(f"❌ FAIL: Found {reproductive_health_count} reproductive health nodes")
            passed = False
        else:
            print("✓ PASS: No reproductive health nodes found")
        
        # Check 2: Varied scores (not all 1.0)
        if scores and not all(s == scores[0] for s in scores):
            print("✓ PASS: Scores are varied (semantic ranking working)")
        else:
            print("❌ FAIL: All scores identical (semantic ranking not working)")
            passed = False
        
        # Check 3: Reasonable score range
        if scores and max(scores) <= 1.0 and min(scores) >= 0.0:
            print("✓ PASS: Scores in valid range [0.0, 1.0]")
        else:
            print("❌ FAIL: Scores outside valid range")
            passed = False
        
        print()
        
        if passed:
            print("🎉 ALL TESTS PASSED - Fix is working correctly!")
            return True
        else:
            print("⚠️  SOME TESTS FAILED - Fix needs adjustment")
            return False
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = test_analyzer_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

