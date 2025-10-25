#!/usr/bin/env python3
"""Main entry point for LLM Agent Orchestration System."""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow INFO and WARNING messages

import logging
import argparse
import sys
from datetime import datetime
from pathlib import Path

from config.settings import get_settings
from utils.llm_client import LLMClient
# Lazy imports to avoid loading sentence-transformers unnecessarily
# from workflows.orchestration import create_workflow
# from workflows.graph_state import ActionPlanState


def setup_logging(log_level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('action_plan_orchestration.log')
        ]
    )


def check_prerequisites():
    """Check if all prerequisites are met."""
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # Check Ollama connection
    logger.info("Checking LLM client connection...")
    llm_client = LLMClient()
    if not llm_client.check_connection():
        logger.error("Cannot connect to LLM server. Please ensure it's running and configured.")
        return False
    
    logger.info(f"✓ {llm_client.provider.capitalize()} client connection successful")
    
    # Check document directory
    if not os.path.exists(settings.docs_dir):
        logger.warning(f"Documents directory not found: {settings.docs_dir}")
        logger.warning("Please set DOCS_DIR in .env file")
        return False
    
    logger.info(f"✓ Documents directory found: {settings.docs_dir}")
    return True


def run_ingestion(docs_dir: str, use_enhanced: bool = True):
    """Run unified data ingestion for all documents."""
    from data_ingestion.enhanced_graph_builder import EnhancedGraphBuilder
    from data_ingestion.graph_vector_builder import GraphVectorBuilder
    
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    logger.info(f"Starting unified document ingestion from {docs_dir}")
    
    # Step 1: Build graph with enhanced hierarchical summarization
    logger.info("Building Neo4j graph with hierarchical summarization...")
    graph_builder = EnhancedGraphBuilder(collection_name=settings.graph_prefix)
    graph_builder.build_from_directory(docs_dir, clear_existing=True)
    stats = graph_builder.get_statistics()
    logger.info(f"Graph statistics: {stats['documents']} documents, {stats['headings']} headings")
    graph_builder.close()
    
    # Step 2: Build vector store from the newly created graph
    # This also automatically adds embeddings to Neo4j nodes
    logger.info("Building ChromaDB vector store from graph (includes Neo4j embedding generation)...")
    vector_builder = GraphVectorBuilder(
        summary_collection=settings.summary_collection_name,
        content_collection=settings.content_collection_name
    )
    vector_builder.build_from_graph(docs_dir, clear_existing=True)
    stats = vector_builder.get_stats()
    
    # Display comprehensive statistics
    logger.info(f"\n{'='*70}")
    logger.info(f"INGESTION STATISTICS")
    logger.info(f"{'='*70}")
    if 'summary_collection' in stats:
        logger.info(f"Summary Collection: {stats['summary_collection']['name']} ({stats['summary_collection']['count']} points)")
    if 'content_collection' in stats:
        logger.info(f"Content Collection: {stats['content_collection']['name']} ({stats['content_collection']['count']} points)")
    if 'neo4j_embeddings' in stats and 'total_nodes' in stats['neo4j_embeddings']:
        neo4j_stats = stats['neo4j_embeddings']
        logger.info(f"Neo4j Embeddings: {neo4j_stats['nodes_with_embeddings']}/{neo4j_stats['total_nodes']} nodes ({neo4j_stats['coverage_percentage']}% coverage)")
    logger.info(f"{'='*70}\n")
    
    vector_builder.close()
    
    logger.info(f"✓ Unified ingestion complete with automatic Neo4j embedding generation")


def generate_action_plan(
    name: str,
    timing: str,
    level: str,
    phase: str,
    subject: str,
    output_path: str = None,
    document_filter: list = None,
    trigger: str = None,
    responsible_party: str = None,
    process_owner: str = None
):
    """
    Generate action plan using template-based orchestration.
    
    Args:
        name: Action plan title
        timing: Time period and/or trigger
        level: One of: ministry, university, center
        phase: One of: preparedness, response
        subject: One of: war, sanction
        output_path: Optional output file path
        document_filter: Optional list of documents to query
        trigger: Optional activation trigger
        responsible_party: Optional responsible party
        process_owner: Optional process owner
    """
    logger = logging.getLogger(__name__)
    
    logger.info(f"Generating action plan: {name}")
    
    # Lazy import to avoid sentence-transformers issues
    from workflows.orchestration import create_workflow
    from workflows.graph_state import ActionPlanState
    from utils.markdown_logger import MarkdownLogger
    from utils.input_validator import InputValidator
    from config.settings import get_settings
    
    # Build user configuration dict
    user_config = {
        "name": name,
        "timing": timing,
        "level": level,
        "phase": phase,
        "subject": subject
    }
    
    # Validate configuration
    is_valid, errors = InputValidator.validate_user_config(user_config)
    if not is_valid:
        logger.error(f"Invalid configuration: {'; '.join(errors)}")
        print(f"Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        print(InputValidator.get_validation_help())
        return None
    
    # Normalize configuration
    user_config = InputValidator.normalize_config(user_config)
    logger.info(f"Configuration validated: level={level}, phase={phase}, subject={subject}")
    
    # No separate guideline documents - treat all documents equally
    guideline_documents = []
    
    # Generate output paths
    if output_path is None:
        # Generate default output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)
        safe_name = safe_name.replace(' ', '_')[:50]
        output_path = f"action_plans/{safe_name}_{timestamp}.md"
    
    # Generate log path
    log_path = output_path.replace('.md', '_log.md')
    
    # Initialize markdown logger
    markdown_logger = MarkdownLogger(log_path)
    markdown_logger.log_workflow_start(name)
    logger.info(f"Logging to: {log_path}")
    
    # Create workflow with logger (dynamic_settings=None uses defaults from .env)
    workflow = create_workflow(markdown_logger=markdown_logger, dynamic_settings=None)
    
    # Initialize state with new parameters
    initial_state: ActionPlanState = {
        "user_config": user_config,
        "subject": name,  # For backward compatibility
        "current_stage": "start",
        "retry_count": {},
        "errors": [],
        "metadata": {},
        "documents_to_query": document_filter,
        "guideline_documents": guideline_documents,
        "timing": timing,
        "trigger": trigger,
        "responsible_party": responsible_party,
        "process_owner": process_owner
    }
    
    # Execute workflow
    logger.info("Executing workflow...")
    try:
        final_state = workflow.invoke(initial_state, config={"recursion_limit": 50})
        
        # Check for errors
        if final_state.get("errors"):
            logger.warning("Workflow completed with errors:")
            for error in final_state["errors"]:
                logger.warning(f"  - {error}")
                markdown_logger.log_error("Workflow", error)
        
        # Get final plans (English and Persian)
        final_plan = final_state.get("final_plan", "")
        final_persian_plan = final_state.get("final_persian_plan", "")
        
        if not final_plan:
            logger.error("No action plan generated")
            markdown_logger.log_workflow_end(success=False, error_msg="No action plan generated")
            markdown_logger.close()
            return None
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save English plan
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_plan)
        
        logger.info(f"✓ English action plan saved to: {output_path}")
        
        # Save Persian plan
        if final_persian_plan:
            persian_path = output_path.replace('.md', '_fa.md')
            with open(persian_path, 'w', encoding='utf-8') as f:
                f.write(final_persian_plan)
            logger.info(f"✓ Persian action plan saved to: {persian_path}")
        
        # Log completion
        markdown_logger.log_workflow_end(success=True)
        markdown_logger.close()
        logger.info(f"✓ Workflow log saved to: {log_path}")
        
        return output_path
    
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        markdown_logger.log_workflow_end(success=False, error_msg=str(e))
        markdown_logger.close()
        return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="LLM Agent Orchestration for Action Plan Development"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Init-db command
    subparsers.add_parser("init-db", help="Initialize Neo4j and ChromaDB databases")
    
    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")
    
    # Clear-db command
    clear_parser = subparsers.add_parser("clear-db", help="Clear database (use with caution!)")
    clear_parser.add_argument(
        "--database",
        choices=["neo4j", "chromadb", "both"],
        required=True,
        help="Which database to clear"
    )
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents into RAG stores")
    ingest_parser.add_argument(
        "--docs-dir",
        help="Directory containing all documents (rules and protocols)"
    )
    
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate action plan")
    generate_parser.add_argument(
        "--name",
        required=True,
        help="Action plan title (e.g., 'Emergency Triage Protocol for Mass Casualty Events')"
    )
    generate_parser.add_argument(
        "--timing",
        required=True,
        help="Time period and/or trigger (e.g., 'Immediate activation upon Code Orange declaration')"
    )
    generate_parser.add_argument(
        "--level",
        required=True,
        choices=["ministry", "university", "center"],
        help="Organizational level: ministry, university, or center"
    )
    generate_parser.add_argument(
        "--phase",
        required=True,
        choices=["preparedness", "response"],
        help="Plan phase: preparedness or response"
    )
    generate_parser.add_argument(
        "--subject",
        required=True,
        choices=["war", "sanction"],
        help="Crisis subject: war or sanction"
    )
    generate_parser.add_argument(
        "--output",
        help="Output file path (default: auto-generated in action_plans/)"
    )
    generate_parser.add_argument(
        "--trigger",
        help="Optional activation trigger"
    )
    generate_parser.add_argument(
        "--responsible-party",
        help="Optional responsible party"
    )
    generate_parser.add_argument(
        "--process-owner",
        help="Optional process owner"
    )
    
    # Check command
    subparsers.add_parser("check", help="Check prerequisites and connections")
    
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Execute command
    if args.command == "init-db":
        from utils.db_init import initialize_all_databases
        if initialize_all_databases():
            return 0
        else:
            return 1
    
    elif args.command == "stats":
        from utils.db_init import get_database_statistics
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
        return 0
    
    elif args.command == "clear-db":
        from utils.db_init import clear_neo4j_database, clear_chromadb
        
        response = input(f"Are you sure you want to clear {args.database}? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Operation cancelled")
            return 0
        
        if args.database in ["neo4j", "both"]:
            success, msg = clear_neo4j_database()
            logger.info(msg)
            if not success:
                return 1
        
        if args.database in ["chromadb", "both"]:
            success, msg = clear_chromadb()
            logger.info(msg)
            if not success:
                return 1
        
        return 0
    
    elif args.command == "check":
        if check_prerequisites():
            logger.info("✓ All prerequisites checked")
            return 0
        else:
            logger.error("✗ Prerequisites check failed")
            return 1
    
    elif args.command == "ingest":
        settings = get_settings()
        
        docs_dir = args.docs_dir or settings.docs_dir
        if os.path.exists(docs_dir):
            run_ingestion(docs_dir)
        else:
            logger.error(f"Documents directory not found: {docs_dir}")
            return 1
        
        return 0
    
    elif args.command == "generate":
        if not check_prerequisites():
            logger.error("Prerequisites check failed. Run 'python main.py check' for details.")
            return 1
        
        result = generate_action_plan(
            name=args.name,
            timing=args.timing,
            level=args.level,
            phase=args.phase,
            subject=args.subject,
            output_path=args.output,
            trigger=args.trigger if hasattr(args, 'trigger') else None,
            responsible_party=getattr(args, 'responsible_party', None),
            process_owner=getattr(args, 'process_owner', None)
        )
        if result:
            return 0
        else:
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

