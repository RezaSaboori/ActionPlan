"""Database initialization utilities for Neo4j and ChromaDB."""

import logging
from typing import Tuple
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import chromadb
from config.settings import get_settings

logger = logging.getLogger(__name__)


def initialize_neo4j() -> Tuple[bool, str]:
    """
    Initialize and verify Neo4j database connection.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    settings = get_settings()
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        # Verify connectivity
        driver.verify_connectivity()
        
        # Create indexes for better performance
        with driver.session() as session:
            # Index on Heading ID
            session.run("""
                CREATE INDEX heading_id IF NOT EXISTS 
                FOR (h:Heading) ON (h.id)
            """)
            
            # Index on Document name
            session.run("""
                CREATE INDEX document_name IF NOT EXISTS 
                FOR (d:Document) ON (d.name)
            """)
            
            # Check database statistics
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()['node_count']
        
        driver.close()
        
        logger.info("Neo4j database initialized successfully")
        return True, f"Neo4j connected successfully ({node_count} nodes in database)"
        
    except AuthError:
        msg = "Neo4j authentication failed - check NEO4J_USER and NEO4J_PASSWORD in .env"
        logger.error(msg)
        return False, msg
        
    except ServiceUnavailable:
        msg = "Neo4j service unavailable - is it running on {settings.neo4j_uri}?"
        logger.error(msg)
        return False, msg
        
    except Exception as e:
        msg = f"Neo4j initialization failed: {e}"
        logger.error(msg)
        return False, msg


def initialize_chromadb() -> Tuple[bool, str]:
    """
    Initialize and verify ChromaDB connection.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    from utils.chroma_client import get_chroma_client
    
    try:
        client = get_chroma_client()
        
        # Test by listing collections
        collections = client.list_collections()
        
        logger.info("ChromaDB initialized successfully")
        return True, f"ChromaDB connected successfully ({len(collections)} collections)"
        
    except Exception as e:
        msg = f"ChromaDB initialization failed: {e}"
        logger.error(msg)
        return False, msg


def clear_neo4j_database() -> Tuple[bool, str]:
    """
    Clear all data from Neo4j database.
    USE WITH CAUTION!
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    settings = get_settings()
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            # Get count before deletion
            result = session.run("MATCH (n) RETURN count(n) as count")
            before_count = result.single()['count']
            
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")
            
            # Verify deletion
            result = session.run("MATCH (n) RETURN count(n) as count")
            after_count = result.single()['count']
        
        driver.close()
        
        msg = f"Neo4j database cleared: {before_count} nodes deleted"
        logger.info(msg)
        return True, msg
        
    except Exception as e:
        msg = f"Failed to clear Neo4j database: {e}"
        logger.error(msg)
        return False, msg


def clear_chromadb() -> Tuple[bool, str]:
    """
    Clear all collections from ChromaDB.
    USE WITH CAUTION!
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    from utils.chroma_client import get_chroma_client
    
    try:
        client = get_chroma_client()
        
        collections = client.list_collections()
        count = len(collections)
        
        for collection in collections:
            client.delete_collection(collection.name)
        
        msg = f"ChromaDB cleared: {count} collections deleted"
        logger.info(msg)
        return True, msg
        
    except Exception as e:
        msg = f"Failed to clear ChromaDB: {e}"
        logger.error(msg)
        return False, msg


def initialize_all_databases() -> bool:
    """
    Initialize all databases (Neo4j and ChromaDB).
    
    Returns:
        True if all databases initialized successfully
    """
    print("\n" + "="*60)
    print("Database Initialization")
    print("="*60)
    
    # Initialize Neo4j
    print("\n1. Initializing Neo4j...")
    neo4j_success, neo4j_msg = initialize_neo4j()
    print(f"   {'✓' if neo4j_success else '✗'} {neo4j_msg}")
    
    # Initialize ChromaDB
    print("\n2. Initializing ChromaDB...")
    chroma_success, chroma_msg = initialize_chromadb()
    print(f"   {'✓' if chroma_success else '✗'} {chroma_msg}")
    
    print("\n" + "="*60)
    
    if neo4j_success and chroma_success:
        print("✓ All databases initialized successfully")
        return True
    else:
        print("✗ Some databases failed to initialize")
        if not neo4j_success:
            print("\nNeo4j troubleshooting:")
            print("  - Check if Neo4j is running: docker ps | grep neo4j")
            print("  - Start Neo4j: docker start neo4j")
            print("  - Verify credentials in .env file")
        
        if not chroma_success:
            print("\nChromaDB troubleshooting:")
            print("  - Check CHROMA_PATH in .env")
            print("  - Ensure directory is writable")
        
        return False


def get_database_statistics() -> dict:
    """
    Get statistics about all databases.
    
    Returns:
        Dictionary with database statistics
    """
    settings = get_settings()
    stats = {
        'neo4j': {'status': 'unknown', 'nodes': 0, 'relationships': 0},
        'chromadb': {'status': 'unknown', 'collections': 0, 'documents': 0}
    }
    
    # Neo4j stats
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN count(n) as count")
            stats['neo4j']['nodes'] = result.single()['count']
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['neo4j']['relationships'] = result.single()['count']
            
            stats['neo4j']['status'] = 'connected'
        
        driver.close()
        
    except Exception as e:
        stats['neo4j']['status'] = f'error: {str(e)[:50]}'
    
    # ChromaDB stats
    try:
        from utils.chroma_client import get_chroma_client
        client = get_chroma_client()
        
        collections = client.list_collections()
        stats['chromadb']['collections'] = len(collections)
        stats['chromadb']['status'] = 'connected'
        
        # Count total documents
        total_docs = 0
        for collection in collections:
            try:
                total_docs += collection.count()
            except:
                pass
        stats['chromadb']['documents'] = total_docs
        
    except Exception as e:
        stats['chromadb']['status'] = f'error: {str(e)[:50]}'
    
    return stats


if __name__ == "__main__":
    """Standalone database initialization."""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'init':
            success = initialize_all_databases()
            sys.exit(0 if success else 1)
            
        elif command == 'clear-neo4j':
            response = input("Are you sure you want to clear Neo4j? (yes/no): ")
            if response.lower() == 'yes':
                success, msg = clear_neo4j_database()
                print(msg)
                sys.exit(0 if success else 1)
            else:
                print("Cancelled")
                sys.exit(0)
                
        elif command == 'clear-chromadb':
            response = input("Are you sure you want to clear ChromaDB? (yes/no): ")
            if response.lower() == 'yes':
                success, msg = clear_chromadb()
                print(msg)
                sys.exit(0 if success else 1)
            else:
                print("Cancelled")
                sys.exit(0)
                
        elif command == 'stats':
            stats = get_database_statistics()
            print("\n" + "="*60)
            print("Database Statistics")
            print("="*60)
            print(f"\nNeo4j:")
            print(f"  Status: {stats['neo4j']['status']}")
            print(f"  Nodes: {stats['neo4j']['nodes']}")
            print(f"  Relationships: {stats['neo4j']['relationships']}")
            print(f"\nChromaDB:")
            print(f"  Status: {stats['chromadb']['status']}")
            print(f"  Collections: {stats['chromadb']['collections']}")
            print(f"  Documents: {stats['chromadb']['documents']}")
            print("="*60)
            sys.exit(0)
        else:
            print(f"Unknown command: {command}")
            print("\nUsage:")
            print("  python -m utils.db_init init          - Initialize databases")
            print("  python -m utils.db_init clear-neo4j   - Clear Neo4j database")
            print("  python -m utils.db_init clear-chromadb - Clear ChromaDB")
            print("  python -m utils.db_init stats         - Show database statistics")
            sys.exit(1)
    else:
        # Default: initialize
        success = initialize_all_databases()
        sys.exit(0 if success else 1)

