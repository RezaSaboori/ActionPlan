#!/usr/bin/env python3
"""
Verify that the local environment is set up correctly.
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow INFO and WARNING messages

import click
from urllib.parse import urlparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.llm_client import LLMClient
from utils.ollama_embeddings import OllamaEmbeddingsClient
from config.settings import get_settings


def test_imports():
    """Test if all modules can be imported."""
    print("Testing imports...")
    
    try:
        from config.settings import get_settings
        print("  ✓ config.settings")
        
        from config.prompts import get_prompt
        print("  ✓ config.prompts")
        
        from utils.llm_client import OllamaClient
        print("  ✓ utils.llm_client")
        
        from utils.document_parser import DocumentParser
        print("  ✓ utils.document_parser")
        
        from rag_tools.graph_rag import GraphRAG
        print("  ✓ rag_tools.graph_rag")
        
        from rag_tools.vector_rag import VectorRAG
        print("  ✓ rag_tools.vector_rag")
        
        from rag_tools.hybrid_rag import HybridRAG
        print("  ✓ rag_tools.hybrid_rag")
        
        from agents.orchestrator import OrchestratorAgent
        from agents.analyzer import AnalyzerAgent
        from agents.extractor import ExtractorAgent
        from agents.prioritizer import PrioritizerAgent
        from agents.assigner import AssignerAgent
        from agents.quality_checker import QualityCheckerAgent
        from agents.formatter import FormatterAgent
        print("  ✓ All 7 agents")
        
        from workflows.graph_state import ActionPlanState
        print("  ✓ workflows.graph_state")
        
        from workflows.orchestration import create_workflow
        print("  ✓ workflows.orchestration")
        
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False


def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")
    
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        print(f"  ✓ Ollama URL: {settings.ollama_base_url}")
        print(f"  ✓ Ollama Model: {settings.ollama_model}")
        print(f"  ✓ Neo4j URI: {settings.neo4j_uri}")
        print(f"  ✓ Rules Dir: {settings.rules_docs_dir}")
        print(f"  ✓ Protocols Dir: {settings.protocols_docs_dir}")
        
        return True
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return False


def test_ollama():
    """Test Ollama connection."""
    print("\nTesting Ollama connection...")
    
    try:
        from utils.llm_client import OllamaClient
        client = OllamaClient()
        
        if client.check_connection():
            print("  ✓ Ollama is accessible")
            
            # Try a simple generation
            try:
                result = client.generate("Say 'test'", temperature=0.1, max_tokens=10)
                print(f"  ✓ LLM generation works: '{result[:50]}'")
                return True
            except Exception as e:
                print(f"  ⚠ Connection OK but generation failed: {e}")
                return False
        else:
            print("  ✗ Cannot connect to Ollama")
            print("    Make sure Ollama is running: ollama serve")
            return False
    except Exception as e:
        print(f"  ✗ Ollama test failed: {e}")
        return False


def test_neo4j():
    """Test Neo4j connection."""
    print("\nTesting Neo4j connection...")
    
    try:
        from neo4j import GraphDatabase
        from config.settings import get_settings
        
        settings = get_settings()
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        # Test connection
        driver.verify_connectivity()
        print("  ✓ Neo4j is accessible")
        
        driver.close()
        return True
    except Exception as e:
        print(f"  ✗ Neo4j connection failed: {e}")
        print("    Make sure Neo4j is running and credentials are correct")
        return False


def test_chromadb():
    """Test ChromaDB connection."""
    print("\nTesting ChromaDB connection...")
    
    try:
        import chromadb
        from config.settings import get_settings
        from chromadb.config import Settings as ChromaSettings
        
        settings = get_settings()
        
        client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        print(f"  ✓ ChromaDB initialized (path: {settings.chroma_path})")
        
        # Try to get collections
        collections = client.list_collections()
        print(f"  ✓ Collections: {len(collections)}")
        
        return True
    except Exception as e:
        print(f"  ✗ ChromaDB connection failed: {e}")
        print("    Check that the chroma_path directory is writable")
        return False


def test_prompts():
    """Test prompt loading."""
    print("\nTesting prompts...")
    
    try:
        from config.prompts import get_prompt
        
        agents = ["orchestrator", "analyzer", "extractor", "prioritizer", 
                  "assigner", "quality_checker", "formatter"]
        
        for agent in agents:
            prompt = get_prompt(agent)
            if prompt:
                print(f"  ✓ {agent}: {len(prompt)} chars")
            else:
                print(f"  ✗ {agent}: Empty prompt")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Prompt test failed: {e}")
        return False


def test_workflow():
    """Test workflow creation."""
    print("\nTesting workflow creation...")
    
    try:
        from workflows.orchestration import create_workflow
        
        workflow = create_workflow()
        print("  ✓ Workflow created successfully")
        print("  ✓ All agents initialized")
        print("  ✓ Graph compiled")
        
        return True
    except Exception as e:
        print(f"  ✗ Workflow creation failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("LLM Agent Orchestration - Setup Verification")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Ollama", test_ollama),
        ("Neo4j", test_neo4j),
        ("ChromaDB", test_chromadb),
        ("Prompts", test_prompts),
        ("Workflow", test_workflow)
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ {name} test crashed: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("Verification Summary")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! System is ready.")
        print("\nNext steps:")
        print("  1. Set document paths in .env")
        print("  2. Run: python main.py ingest --type both")
        print("  3. Run: python main.py generate --subject 'your subject'")
        return 0
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Start Ollama: ollama serve")
        print("  - Start Neo4j: docker start neo4j")
        print("  - Install dependencies: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())

