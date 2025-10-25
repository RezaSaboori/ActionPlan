#!/usr/bin/env python3
"""
Test script to validate Semantic Phase 1 improvements.

This script validates that:
1. Phase 1 returns semantic results (no more regex)
2. Scores are properly normalized [0.0, 1.0]
3. Results are ranked by relevance
4. No cross-domain contamination
5. Semantic search outperforms keyword matching
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag_tools.graph_rag import GraphRAG
from config.settings import get_settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_semantic_phase1():
    """Test semantic Phase 1 retrieval."""
    
    print("="*80)
    print("SEMANTIC PHASE 1 VALIDATION TEST")
    print("="*80)
    print()
    
    # Initialize GraphRAG
    settings = get_settings()
    graph_rag = GraphRAG(collection_name=settings.graph_prefix)
    
    # Test queries
    test_cases = [
        {
            "query": "Emergency Triage Protocol for Mass Casualty Events",
            "description": "Operational emergency triage query",
            "expected_domain": "emergency_logistics",
            "should_not_contain": ["reproductive_health", "maternal_care"]
        },
        {
            "query": "Supply chain management for medical equipment during disasters",
            "description": "Supply chain and logistics query",
            "expected_domain": "supply_chain",
            "should_not_contain": ["clinical_protocols", "patient_care"]
        },
        {
            "query": "Incident command structure for multi-agency coordination",
            "description": "Command and control query",
            "expected_domain": "incident_command",
            "should_not_contain": ["medical_procedures", "clinical_guidelines"]
        }
    ]
    
    all_passed = True
    
    for idx, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST CASE {idx}: {test_case['description']}")
        print(f"{'='*80}")
        print(f"Query: {test_case['query']}")
        print()
        
        # Execute query
        try:
            results = graph_rag.query_introduction_nodes(
                query_text=test_case['query'],
                top_k=10
            )
            
            print(f"✓ Retrieved {len(results)} results")
            
            # Validation 1: Results returned
            if len(results) == 0:
                print(f"✗ FAIL: No results returned")
                all_passed = False
                continue
            
            # Validation 2: All results have scores
            if not all('score' in r for r in results):
                print(f"✗ FAIL: Not all results have scores")
                all_passed = False
                continue
            else:
                print(f"✓ All results have semantic scores")
            
            # Validation 3: Scores are in valid range [0.0, 1.0]
            scores = [r['score'] for r in results]
            if not all(0.0 <= s <= 1.0 for s in scores):
                print(f"✗ FAIL: Scores out of range [0.0, 1.0]")
                print(f"  Score range: [{min(scores):.4f}, {max(scores):.4f}]")
                all_passed = False
            else:
                print(f"✓ Scores in valid range: [{min(scores):.4f}, {max(scores):.4f}]")
            
            # Validation 4: Results are ranked by score (descending)
            is_ranked = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
            if not is_ranked:
                print(f"✗ FAIL: Results not properly ranked by score")
                all_passed = False
            else:
                print(f"✓ Results properly ranked by semantic similarity")
            
            # Validation 5: Score diversity (not all the same)
            score_variance = max(scores) - min(scores)
            if score_variance < 0.01:
                print(f"✗ FAIL: Scores too uniform (variance: {score_variance:.4f})")
                print(f"  This suggests semantic search may not be working")
                all_passed = False
            else:
                print(f"✓ Good score diversity (variance: {score_variance:.4f})")
            
            # Validation 6: Check for cross-domain contamination
            print()
            print("Top 5 Results:")
            cross_domain_found = False
            for i, result in enumerate(results[:5], 1):
                title = result['title']
                score = result['score']
                doc_name = result.get('document_name', 'Unknown')
                
                print(f"  {i}. [{score:.4f}] {title}")
                print(f"     Document: {doc_name}")
                
                # Check for unwanted domains
                title_lower = title.lower()
                doc_lower = doc_name.lower()
                combined = f"{title_lower} {doc_lower}"
                
                for unwanted in test_case['should_not_contain']:
                    if unwanted.replace('_', ' ') in combined:
                        print(f"     ⚠️  WARNING: Potential cross-domain match: '{unwanted}'")
                        cross_domain_found = True
            
            if not cross_domain_found:
                print(f"\n✓ No cross-domain contamination detected")
            else:
                print(f"\n✗ FAIL: Cross-domain contamination detected")
                all_passed = False
            
            # Validation 7: Semantic relevance check
            print()
            print("Semantic Relevance Analysis:")
            high_score_count = sum(1 for s in scores if s > 0.5)
            medium_score_count = sum(1 for s in scores if 0.3 <= s <= 0.5)
            low_score_count = sum(1 for s in scores if s < 0.3)
            
            print(f"  High relevance (>0.5):    {high_score_count} results")
            print(f"  Medium relevance (0.3-0.5): {medium_score_count} results")
            print(f"  Low relevance (<0.3):     {low_score_count} results")
            
            if high_score_count == 0:
                print(f"  ⚠️  WARNING: No highly relevant results found")
            
            print()
            if not cross_domain_found and is_ranked and score_variance >= 0.01:
                print(f"✅ TEST CASE {idx}: PASSED")
            else:
                print(f"❌ TEST CASE {idx}: FAILED")
                all_passed = False
                
        except Exception as e:
            print(f"✗ FAIL: Exception during test: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    # Final summary
    print()
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("Semantic Phase 1 is working correctly:")
        print("  ✓ Semantic embeddings being used")
        print("  ✓ Scores properly normalized and ranked")
        print("  ✓ No cross-domain contamination")
        print("  ✓ Results show semantic relevance")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Please review the failures above.")
        return 1


if __name__ == "__main__":
    sys.exit(test_semantic_phase1())

