#!/usr/bin/env python3
"""
Embeddings Verification Script

Verifies that Neo4j Heading nodes have summary_embedding properties
and reports on embedding coverage.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from neo4j import GraphDatabase
from config.settings import get_settings


def verify_embeddings():
    """Verify Neo4j embeddings coverage and quality."""
    settings = get_settings()
    
    print("=" * 70)
    print("NEO4J EMBEDDINGS VERIFICATION REPORT")
    print("=" * 70)
    print()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    try:
        with driver.session() as session:
            # 1. Total Heading nodes
            result = session.run("MATCH (h:Heading) RETURN count(h) as total")
            total_headings = result.single()['total']
            print(f"1. Total Heading Nodes: {total_headings}")
            
            # 2. Nodes with embeddings
            result = session.run("""
                MATCH (h:Heading)
                WHERE h.summary_embedding IS NOT NULL
                RETURN count(h) as with_embeddings
            """)
            with_embeddings = result.single()['with_embeddings']
            print(f"2. Nodes with Embeddings: {with_embeddings}")
            
            # 3. Calculate coverage
            if total_headings > 0:
                coverage = (with_embeddings / total_headings) * 100
                print(f"3. Coverage: {coverage:.2f}%")
            else:
                coverage = 0
                print(f"3. Coverage: N/A (no heading nodes found)")
            
            print()
            
            # 4. Embedding dimension check
            result = session.run("""
                MATCH (h:Heading)
                WHERE h.summary_embedding IS NOT NULL
                RETURN size(h.summary_embedding) as dimension
                LIMIT 1
            """)
            record = result.single()
            if record:
                dimension = record['dimension']
                print(f"4. Embedding Dimension: {dimension}")
                expected_dim = settings.embedding_dimension
                if dimension == expected_dim:
                    print(f"   ✓ Matches expected dimension ({expected_dim})")
                else:
                    print(f"   ✗ WARNING: Expected {expected_dim}, got {dimension}")
            else:
                print(f"4. Embedding Dimension: N/A (no embeddings found)")
            
            print()
            
            # 5. Sample nodes with embeddings
            print("5. Sample Nodes WITH Embeddings:")
            result = session.run("""
                MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading)
                WHERE h.summary_embedding IS NOT NULL
                RETURN doc.name as document, h.title as title, h.id as node_id
                LIMIT 5
            """)
            for i, record in enumerate(result, 1):
                print(f"   {i}. [{record['document']}] {record['title']}")
                print(f"      Node ID: {record['node_id']}")
            
            print()
            
            # 6. Sample nodes WITHOUT embeddings (if any)
            result = session.run("""
                MATCH (doc:Document)-[:HAS_SUBSECTION*]->(h:Heading)
                WHERE h.summary_embedding IS NULL
                RETURN doc.name as document, h.title as title, h.id as node_id
                LIMIT 5
            """)
            nodes_without = list(result)
            if nodes_without:
                print("6. Sample Nodes WITHOUT Embeddings:")
                for i, record in enumerate(nodes_without, 1):
                    print(f"   {i}. [{record['document']}] {record['title']}")
                    print(f"      Node ID: {record['node_id']}")
            else:
                print("6. Sample Nodes WITHOUT Embeddings: None (all nodes have embeddings)")
            
            print()
            print("=" * 70)
            print("VERIFICATION SUMMARY")
            print("=" * 70)
            
            if coverage >= 95:
                print("✓ STATUS: EXCELLENT - Embeddings coverage is sufficient")
                print("  GraphAwareRAG can be safely enabled.")
                return True
            elif coverage >= 70:
                print("⚠ STATUS: ACCEPTABLE - Most nodes have embeddings")
                print("  GraphAwareRAG can be enabled, but consider re-ingesting")
                print("  documents to achieve full coverage.")
                return True
            elif coverage > 0:
                print("✗ STATUS: POOR - Low embedding coverage")
                print("  Action Required: Run data ingestion pipeline to generate")
                print("  embeddings for all nodes before enabling GraphAwareRAG.")
                return False
            else:
                print("✗ STATUS: CRITICAL - No embeddings found")
                print("  Action Required: Run data ingestion pipeline immediately.")
                print("  GraphAwareRAG cannot function without embeddings.")
                return False
    
    finally:
        driver.close()


if __name__ == "__main__":
    try:
        success = verify_embeddings()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

