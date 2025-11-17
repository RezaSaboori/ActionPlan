"""LangGraph workflow orchestration."""

import logging
from typing import Dict, Any
import os
import json
from langgraph.graph import StateGraph, END
from config.settings import get_settings
from utils.llm_client import LLMClient
from utils.document_hierarchy_loader import DocumentHierarchyLoader
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from rag_tools.vector_rag import VectorRAG
from agents.orchestrator import OrchestratorAgent
from agents.analyzer import AnalyzerAgent
from agents.phase3 import Phase3Agent
from agents.extractor import ExtractorAgent
from agents.deduplicator import DeduplicatorAgent
from agents.selector import SelectorAgent
from agents.timing import TimingAgent
from agents.assigner import AssignerAgent
from agents.quality_checker import QualityCheckerAgent, ComprehensiveQualityValidator
from agents.formatter import FormatterAgent
from agents.translator import TranslatorAgent
from agents.segmentation import SegmentationAgent
from agents.term_identifier import TermIdentifierAgent
from agents.dictionary_lookup import DictionaryLookupAgent
from agents.translation_refinement import TranslationRefinementAgent
from agents.assigning_translator import AssigningTranslatorAgent
from .graph_state import ActionPlanState

logger = logging.getLogger(__name__)


def _save_agent_output(state: ActionPlanState, agent_name: str, output_data: Dict[str, Any]):
    """Save agent output to a file if debug mode is enabled."""
    if "agent_output_dir" in state and state["agent_output_dir"]:
        output_dir = state["agent_output_dir"]
        doc_name = state.get("user_config", {}).get("name", "untitled").replace(" ", "_")
        filename = os.path.join(output_dir, f"{doc_name}_{agent_name}_output.json")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Saved {agent_name} output to {filename}")
        except Exception as e:
            logger.error(f"Failed to save {agent_name} output: {e}")


def create_workflow(markdown_logger=None, dynamic_settings=None):
    """
    Create and compile the LangGraph workflow.
    
    Args:
        markdown_logger: Optional MarkdownLogger instance for comprehensive logging
        dynamic_settings: Optional DynamicSettingsManager for per-agent LLM configuration
    
    Returns:
        Compiled workflow graph
    """
    settings = get_settings()
    
    # Initialize main RAG tools (excludes Dictionary.md for main agents)
    main_graph_rag = GraphRAG(collection_name=settings.graph_prefix, markdown_logger=markdown_logger)
    main_vector_rag = VectorRAG(collection_name=settings.documents_collection, markdown_logger=markdown_logger)
    main_hybrid_rag = HybridRAG(
        graph_collection=settings.graph_prefix,
        vector_collection=settings.documents_collection,
        use_graph_aware=True,  # Enable semantic embedding search
        markdown_logger=markdown_logger
    )
    
    # Initialize dictionary RAG tools (for Dictionary Lookup agent only)
    dictionary_graph_rag = GraphRAG(collection_name=settings.dictionary_graph_prefix, markdown_logger=markdown_logger)
    dictionary_vector_rag = VectorRAG(collection_name=settings.dictionary_collection, markdown_logger=markdown_logger)
    dictionary_hybrid_rag = HybridRAG(
        graph_collection=settings.dictionary_graph_prefix,
        vector_collection=settings.dictionary_collection,
        markdown_logger=markdown_logger
    )
    
    # Initialize main agents with main RAG (no dictionary access)
    # NOTE: Orchestrator no longer uses RAG (template-based prompts)
    orchestrator = OrchestratorAgent("orchestrator", dynamic_settings, markdown_logger)
    analyzer = AnalyzerAgent("analyzer", dynamic_settings, main_hybrid_rag, main_graph_rag, markdown_logger)
    phase3 = Phase3Agent("phase3", dynamic_settings, main_hybrid_rag, main_graph_rag, markdown_logger)
    quality_checker = QualityCheckerAgent("quality_checker", dynamic_settings, main_hybrid_rag, markdown_logger)
    extractor = ExtractorAgent("extractor", dynamic_settings, main_graph_rag, quality_checker, orchestrator, markdown_logger)
    deduplicator = DeduplicatorAgent("deduplicator", dynamic_settings, markdown_logger)
    selector = SelectorAgent("selector", dynamic_settings, markdown_logger)
    timing = TimingAgent("timing", dynamic_settings, markdown_logger)
    assigner = AssignerAgent("assigner", dynamic_settings, markdown_logger)
    formatter = FormatterAgent("formatter", dynamic_settings, markdown_logger)
    
    # Initialize translation agents (Dictionary Lookup uses dictionary RAG)
    translator = TranslatorAgent("translator", dynamic_settings, markdown_logger)
    segmentation = SegmentationAgent("segmentation", dynamic_settings, markdown_logger)
    term_identifier = TermIdentifierAgent("term_identifier", dynamic_settings, markdown_logger)
    dictionary_lookup = DictionaryLookupAgent("dictionary_lookup", dynamic_settings, dictionary_hybrid_rag, markdown_logger)
    translation_refinement = TranslationRefinementAgent("translation_refinement", dynamic_settings, markdown_logger)
    assigning_translator = AssigningTranslatorAgent("assigning_translator", dynamic_settings, markdown_logger)
    
    # Define node functions
    def orchestrator_node(state: ActionPlanState) -> ActionPlanState:
        """Orchestrator node."""
        logger.info("Executing Orchestrator")
        
        # Get user config from state
        user_config = state.get("user_config", {})
        
        if markdown_logger:
            markdown_logger.log_agent_start("Orchestrator", {
                "name": user_config.get("name", "Unknown"),
                "level": user_config.get("level"),
                "phase": user_config.get("phase"),
                "subject": user_config.get("subject")
            })
        
        try:
            result = orchestrator.execute(user_config)
            
            # Store problem statement and config
            state["problem_statement"] = result.get("problem_statement", "")
            state["user_config"] = result.get("user_config", user_config)
            
            # Set subject for backward compatibility
            state["subject"] = user_config.get("name", "")
            
            # Store orchestrator context for comprehensive validator
            state["orchestrator_context"] = {
                "problem_statement": result.get("problem_statement", ""),
                "user_config": user_config
            }
            
            # Store original input parameters for comprehensive validator
            state["original_input"] = {
                "subject": user_config.get("name", ""),
                "timing": user_config.get("timing"),
                "trigger": state.get("trigger"),
                "responsible_party": state.get("responsible_party"),
                "process_owner": state.get("process_owner")
            }
            
            state["current_stage"] = "orchestrator"
            
            _save_agent_output(state, "orchestrator", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Orchestrator", {
                    "problem_statement": result.get("problem_statement", ""),
                    "config": user_config
                })
            
            return state
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Orchestrator", str(e))
            state.setdefault("errors", []).append(f"Orchestrator: {str(e)}")
            return state
    
    def analyzer_node(state: ActionPlanState) -> ActionPlanState:
        """Analyzer node (2-phase workflow)."""
        logger.info("Executing Analyzer (2-Phase)")
        
        # Pass problem statement to Analyzer
        context = {
            "problem_statement": state.get("problem_statement", "")
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Analyzer", {
                "problem_statement": context["problem_statement"]
            })
        
        try:
            result = analyzer.execute(context)
            
            # Phase 1 outputs
            state["all_document_summaries"] = result.get("all_documents", [])
            state["refined_queries"] = result.get("refined_queries", [])
            
            # Phase 2 output
            state["node_ids"] = result.get("node_ids", [])
            
            # Update problem statement if it was refined
            refined_problem_statement = result.get("problem_statement")
            if refined_problem_statement and refined_problem_statement.strip():
                logger.info("Updating problem statement with refined version from Analyzer")
                state["problem_statement"] = refined_problem_statement
            
            # DEPRECATED: Old Analyzer outputs
            state["context_map"] = result.get("context_map", {})
            state["identified_subjects"] = result.get("identified_subjects", [])
            
            state["current_stage"] = "analyzer"
            
            _save_agent_output(state, "analyzer", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Analyzer", {
                    "refined_queries": state["refined_queries"],
                    "node_ids": state["node_ids"],
                    "identified_subjects": state["identified_subjects"]
                })
            
            return state
        except Exception as e:
            logger.error(f"Analyzer error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Analyzer", str(e))
            state.setdefault("errors", []).append(f"Analyzer: {str(e)}")
            return state
    
    def phase3_node(state: ActionPlanState) -> ActionPlanState:
        """phase3 node (deep analysis via graph traversal)."""
        logger.info("Executing Phase3 (Deep Analysis via Graph Traversal)")
        
        # Pass node_ids from Analyzer Phase 2
        context = {
            "node_ids": state.get("node_ids", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Phase3", {
                "node_ids_count": len(context["node_ids"]),
                "sample_node_ids": context["node_ids"][:5]
            })
        
        try:
            result = phase3.execute(context)
            
            # Output: flat list of nodes with complete metadata
            phase3_nodes = result.get("nodes", [])
            state["phase3_nodes"] = phase3_nodes
            
            # BACKWARD COMPATIBILITY: Keep subject_nodes for downstream agents that expect it
            # Wrap nodes in a subject structure (using empty subject since we don't have subjects anymore)
            state["subject_nodes"] = [{
                "subject": "all",
                "nodes": phase3_nodes
            }]
            
            state["current_stage"] = "phase3"
            
            _save_agent_output(state, "phase3", result)

            if markdown_logger:
                # Log summary and sample of retrieved data
                output_data = {
                    "total_nodes_retrieved": len(phase3_nodes),
                    "sample_node_ids": [n.get("id", "Unknown") for n in phase3_nodes[:5]],
                    "sample_node_titles": [n.get("title", "Unknown") for n in phase3_nodes[:5]]
                }
                
                markdown_logger.log_agent_output("Phase3", output_data)
            
            return state
        except Exception as e:
            logger.error(f"Phase3 error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Phase3", str(e))
            state.setdefault("errors", []).append(f"Phase3: {str(e)}")
            return state
    
    def special_protocols_node(state: ActionPlanState) -> ActionPlanState:
        """Special Protocols node - bypass Analyzer/Phase3/Selector."""
        logger.info("Executing Special Protocols Processor")
        
        node_ids = state.get("special_protocols_node_ids", [])
        
        if markdown_logger:
            markdown_logger.log_agent_start("Special Protocols", {
                "node_ids_count": len(node_ids) if node_ids else 0
            })
        
        try:
            if not node_ids:
                # No special protocols selected
                logger.info("No special protocols selected, skipping")
                state["special_protocols_nodes"] = []
                
                if markdown_logger:
                    markdown_logger.log_agent_output("Special Protocols", {
                        "status": "skipped",
                        "reason": "No node IDs provided"
                    })
                
                return state
            
            # Initialize loader
            loader = DocumentHierarchyLoader()
            
            # Expand node IDs to include all nested subsections
            expanded_node_ids = loader.expand_node_ids_with_subsections(node_ids)
            logger.info(f"Expanded {len(node_ids)} node IDs to {len(expanded_node_ids)} (including subsections)")
            
            # Fetch node data formatted for Extractor
            nodes = loader.format_for_extractor(expanded_node_ids)
            state["special_protocols_nodes"] = nodes
            
            loader.close()
            
            logger.info(f"Special protocols processed: {len(nodes)} nodes ready for extraction")
            
            if markdown_logger:
                markdown_logger.log_agent_output("Special Protocols", {
                    "input_node_ids": len(node_ids),
                    "expanded_node_ids": len(expanded_node_ids),
                    "nodes_retrieved": len(nodes),
                    "sample_nodes": [
                        {
                            "id": n.get("id", "Unknown"),
                            "title": n.get("title", "Unknown"),
                            "document": n.get("document", "Unknown")
                        }
                        for n in nodes[:5]
                    ]
                })
            
            state["current_stage"] = "special_protocols"
            return state
            
        except Exception as e:
            logger.error(f"Special Protocols error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Special Protocols", str(e))
            state.setdefault("errors", []).append(f"Special Protocols: {str(e)}")
            state["special_protocols_nodes"] = []
            return state
    
    def extractor_node(state: ActionPlanState) -> ActionPlanState:
        """Extractor node (multi-subject processing with validation)."""
        logger.info("Executing Extractor (Multi-Subject)")
        
        # Get normal subject_nodes from Phase3
        normal_nodes = state.get("subject_nodes", [])
        
        # Get special protocol nodes
        special_nodes = state.get("special_protocols_nodes", [])
        
        # Merge flows: special protocols + normal nodes
        if special_nodes:
            logger.info(f"Merging {len(special_nodes)} special protocol nodes with {len(normal_nodes)} normal subject groups")
            
            # Wrap special nodes in subject structure
            special_subject = {
                "subject": "special_protocols",
                "nodes": special_nodes
            }
            
            # Prepend special protocols (higher priority)
            input_data = {
                "subject_nodes": [special_subject] + normal_nodes
            }
        else:
            # No special protocols, use normal nodes only
            input_data = {"subject_nodes": normal_nodes}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Extractor", {
                "subject_nodes_count": len(input_data["subject_nodes"]),
                "has_special_protocols": len(special_nodes) > 0,
                "sample_input": [{
                    "subject": s.get("subject"),
                    "nodes_count": len(s.get("nodes", []))
                } for s in input_data["subject_nodes"][:3]]
            })
        
        try:
            # Use multi-subject processing with validation
            result = extractor.execute(input_data)
            
            # Update state with refined actions
            state["actions_by_actor"] = result.get("actions_by_actor", {})
            state["tables"] = result.get("tables", [])
            state["extraction_metadata"] = result.get("metadata", {})
            
            # For backward compatibility and downstream agents
            state["complete_actions"] = result.get("complete_actions", [])
            state["flagged_actions"] = result.get("flagged_actions", [])
            state["subject_actions"] = result.get("subject_actions", [])
            
            state["current_stage"] = "extractor"
            
            _save_agent_output(state, "extractor", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Extractor", {
                    "complete_actions": len(state["complete_actions"]),
                    "flagged_actions": len(state["flagged_actions"]),
                    "total_actions": len(state["complete_actions"] + state["flagged_actions"]),
                    "tables_extracted": len(state.get("tables", [])),
                    "unique_actors": len(state.get("actions_by_actor", {})),
                    "subjects_processed": len(state["subject_actions"]),
                    "special_protocol_actions": len([a for a in state["complete_actions"] + state["flagged_actions"] if a.get("from_special_protocol")])
                })
                
                # Add extraction metadata if available
                if state.get("extraction_metadata"):
                    markdown_logger.add_text("### Extraction Metadata")
                    markdown_logger.add_text("")
                    for key, value in state["extraction_metadata"].items():
                        markdown_logger.add_text(f"**{key}:** {value}")
                        markdown_logger.add_text("")
                
                # Add sample complete actions
                if state["complete_actions"]:
                    markdown_logger.add_text("### Sample Complete Actions")
                    markdown_logger.add_text("")
                    for idx, action in enumerate(state["complete_actions"][:5], 1):
                        markdown_logger.add_text(f"**{idx}. {action.get('action', 'N/A')}**")
                        markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                        markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                        markdown_logger.add_list_item(f"WHAT: {action.get('what', 'N/A')}", level=1)
                        markdown_logger.add_text("")
                
                if state["flagged_actions"]:
                    markdown_logger.add_text("### Sample Flagged Actions")
                    markdown_logger.add_text("")
                    for idx, action in enumerate(state["flagged_actions"][:3], 1):
                        markdown_logger.add_text(f"**{idx}. {action.get('action', 'N/A')}**")
                        markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                        markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                        markdown_logger.add_list_item(f"Missing: {', '.join(action.get('missing_fields', []))}", level=1)
                        markdown_logger.add_list_item(f"Reason: {action.get('flag_reason', 'N/A')}", level=1)
                        markdown_logger.add_text("")
            
            return state
        except Exception as e:
            logger.error(f"Extractor error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Extractor", str(e))
            state.setdefault("errors", []).append(f"Extractor: {str(e)}")
            return state
    
    def deduplicator_node(state: ActionPlanState) -> ActionPlanState:
        """De-duplicator node for merging similar actions and passing through formulas/tables."""
        logger.info("Executing De-duplicator")
        input_data = {
            "complete_actions": state.get("complete_actions", []),
            "flagged_actions": state.get("flagged_actions", []),
            "tables": state.get("tables", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("De-duplicator", {
                "complete_actions_count": len(input_data["complete_actions"]),
                "flagged_actions_count": len(input_data["flagged_actions"]),
                "tables_count": len(input_data["tables"])
            })
        
        try:
            # Perform de-duplication and merging
            result = deduplicator.execute(input_data)
            
            # Update state with refined actions
            state["complete_actions"] = result.get("refined_complete_actions", [])
            state["flagged_actions"] = result.get("refined_flagged_actions", [])
            
            # Update tables (passed through)
            state["tables"] = result.get("tables", [])
            
            # Update refined_actions for downstream agents
            state["refined_actions"] = state["complete_actions"] + state["flagged_actions"]
            
            # Store merge summary
            state["merge_summary"] = result.get("merge_summary", {})
            
            state["current_stage"] = "deduplicator"
            
            _save_agent_output(state, "deduplicator", result)

            if markdown_logger:
                markdown_logger.log_agent_output("De-duplicator", {
                    "refined_complete_actions": len(state["complete_actions"]),
                    "refined_flagged_actions": len(state["flagged_actions"]),
                    "tables_count": len(state.get("tables", [])),
                    "merge_summary": result.get("merge_summary", {}),
                    "refined_actions_count": len(state.get("refined_actions", []))
                })
            
            return state
        except Exception as e:
            logger.error(f"De-duplicator error: {e}")
            if markdown_logger:
                markdown_logger.log_error("De-duplicator", str(e))
            state.setdefault("errors", []).append(f"De-duplicator: {str(e)}")
            return state
    
    def selector_node(state: ActionPlanState) -> ActionPlanState:
        """Selector node for filtering actions based on relevance."""
        logger.info("Executing Selector")
        
        complete_actions = state.get("complete_actions", [])
        flagged_actions = state.get("flagged_actions", [])
        
        # Separate special protocol actions (these bypass selector filtering)
        special_complete = [a for a in complete_actions if a.get("from_special_protocol")]
        special_flagged = [a for a in flagged_actions if a.get("from_special_protocol")]
        
        # Filter only normal actions (not from special protocols)
        normal_complete = [a for a in complete_actions if not a.get("from_special_protocol")]
        normal_flagged = [a for a in flagged_actions if not a.get("from_special_protocol")]
        
        logger.info(f"Selector: {len(special_complete + special_flagged)} special protocol actions will bypass filtering")
        logger.info(f"Selector: {len(normal_complete + normal_flagged)} normal actions will be filtered")
        
        input_data = {
            "problem_statement": state.get("problem_statement", ""),
            "user_config": state.get("user_config", {}),
            "complete_actions": normal_complete,
            "flagged_actions": normal_flagged,
            "tables": state.get("tables", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Selector", {
                "problem_statement": input_data["problem_statement"][:100] + "...",
                "user_config": input_data["user_config"],
                "complete_actions_count": len(normal_complete),
                "flagged_actions_count": len(normal_flagged),
                "tables_count": len(input_data["tables"]),
                "special_protocol_actions_bypassed": len(special_complete + special_flagged)
            })
        
        try:
            # Perform semantic selection on normal actions only
            result = selector.execute(input_data)
            
            # Merge: special protocols (always included) + selected normal actions
            state["complete_actions"] = special_complete + result.get("selected_complete_actions", [])
            state["flagged_actions"] = special_flagged + result.get("selected_flagged_actions", [])
            
            # Update tables (passed through)
            state["tables"] = result.get("tables", [])
            
            # Update refined_actions for downstream agents
            state["refined_actions"] = state["complete_actions"] + state["flagged_actions"]
            
            # Store selection summary and discarded actions
            state["selection_summary"] = result.get("selection_summary", {})
            state["discarded_actions"] = result.get("discarded_actions", [])
            
            state["current_stage"] = "selector"
            
            _save_agent_output(state, "selector", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Selector", {
                    "selected_complete_actions": len(state["complete_actions"]),
                    "selected_flagged_actions": len(state["flagged_actions"]),
                    "tables_count": len(state.get("tables", [])),
                    "selection_summary": result.get("selection_summary", {}),
                    "discarded_count": len(result.get("discarded_actions", [])),
                    "refined_actions_count": len(state.get("refined_actions", [])),
                    "special_protocol_actions_preserved": len(special_complete + special_flagged)
                })
            
            return state
        except Exception as e:
            logger.error(f"Selector error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Selector", str(e))
            state.setdefault("errors", []).append(f"Selector: {str(e)}")
            return state
    
    def timing_node(state: ActionPlanState) -> ActionPlanState:
        """Timing node to add triggers and timelines to actions and pass through formulas/tables."""
        logger.info("Executing Timing Agent")
        input_data = {
            "actions": state.get("refined_actions", []),
            "problem_statement": state.get("problem_statement", ""),
            "user_config": state.get("user_config", {}),
            "tables": state.get("tables", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Timing", {
                "actions_count": len(input_data["actions"]),
                "tables_count": len(input_data["tables"])
            })
        
        try:
            result = timing.execute(input_data)
            state["timed_actions"] = result.get("timed_actions", [])
            state["tables"] = result.get("tables", [])
            state["current_stage"] = "timing"
            
            _save_agent_output(state, "timing", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Timing", {
                    "timed_actions_count": len(state["timed_actions"]),
                    "tables_count": len(state["tables"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Timing error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Timing", str(e))
            state.setdefault("errors", []).append(f"Timing: {str(e)}")
            # Set timed_actions to input actions to allow pipeline to continue
            state["timed_actions"] = input_data.get("actions", [])
            return state
    
    def assigner_node(state: ActionPlanState) -> ActionPlanState:
        """Assigner node for refining WHO assignments and passing through tables."""
        logger.info("Executing Assigner Agent")
        input_data = {
            "prioritized_actions": state.get("timed_actions", []),
            "user_config": state.get("user_config", {}),
            "tables": state.get("tables", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Assigner", {
                "actions_count": len(state["timed_actions"]),
                "tables_count": len(input_data["tables"]),
                "organizational_level": state.get("user_config", {}).get("level", "unknown")
            })
        
        try:
            result = assigner.execute(input_data)
            state["assigned_actions"] = result.get("assigned_actions", [])
            state["tables"] = result.get("tables", [])
            state["current_stage"] = "assigner"
            
            _save_agent_output(state, "assigner", result)

            if markdown_logger:
                markdown_logger.log_agent_output("Assigner", {
                    "assigned_actions_count": len(state["assigned_actions"]),
                    "tables_count": len(state["tables"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Assigner error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Assigner", str(e))
            state.setdefault("errors", []).append(f"Assigner: {str(e)}")
            state.setdefault("assigned_actions", state.get("timed_actions", []))
            return state
    
    def quality_checker_node(state: ActionPlanState) -> ActionPlanState:
        """Quality checker node."""
        logger.info("Executing Quality Checker")
        stage = state.get("current_stage", "unknown")
        
        # Get appropriate data for stage
        if stage == "extractor":
            data = {"refined_actions": state.get("refined_actions", [])}
        elif stage == "timing":
            data = {"timed_actions": state.get("timed_actions", [])}
        elif stage == "assigner":
            data = {"assigned_actions": state.get("assigned_actions", [])}
        else:
            data = {}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Quality Checker", {
                "stage": stage,
                "data_items": len(list(data.values())[0]) if data and list(data.values()) else 0
            })
        
        try:
            feedback = quality_checker.execute(data, stage)
            state["quality_feedback"] = feedback
            
            _save_agent_output(state, "quality_checker", feedback)

            if markdown_logger:
                markdown_logger.log_quality_feedback(stage, feedback)
            
            return state
        except Exception as e:
            logger.error(f"Quality Checker error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Quality Checker", str(e))
            state["quality_feedback"] = {
                "status": "retry",
                "overall_score": 0.0,
                "feedback": f"Quality check failed: {str(e)}"
            }
            return state
    
    def formatter_node(state: ActionPlanState) -> ActionPlanState:
        """Formatter node with formula and table integration."""
        logger.info("Executing Formatter")
        data = {
            "subject": state["subject"],
            "assigned_actions": state.get("assigned_actions", []),
            "tables": state.get("tables", []),
            "formatted_output": state.get("formatted_output", ""),
            "rules_context": state.get("rules_context", {}),
            "problem_statement": state.get("problem_statement", ""),
            "trigger": state.get("trigger"),
            "responsible_party": state.get("responsible_party"),
            "process_owner": state.get("process_owner"),
            "user_config": state.get("user_config", {})
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Formatter", {
                "subject": state["subject"],
                "actions_count": len(state["assigned_actions"]),
                "tables_count": len(data["tables"]),
                "trigger": state.get("trigger"),
                "responsible_party": state.get("responsible_party"),
                "process_owner": state.get("process_owner")
            })
        
        try:
            plan = formatter.execute(data)
            state["final_plan"] = plan
            state["current_stage"] = "formatter"
            
            _save_agent_output(state, "formatter", {"final_plan": plan})

            if markdown_logger:
                markdown_logger.log_agent_output("Formatter", {
                    "plan_length": len(plan),
                    "tables_included": len(data["tables"]),
                    "status": "completed"
                })
            
            return state
        except Exception as e:
            logger.error(f"Formatter error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Formatter", str(e))
            state.setdefault("errors", []).append(f"Formatter: {str(e)}")
            return state
    
    def translator_node(state: ActionPlanState) -> ActionPlanState:
        """Translator node."""
        logger.info("Executing Translator")
        data = {"final_plan": state["final_plan"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Translator", {
                "plan_length": len(state["final_plan"])
            })
        
        try:
            translated_plan = translator.execute(data)
            state["translated_plan"] = translated_plan
            state["current_stage"] = "translator"
            
            _save_agent_output(state, "translator", {"translated_plan": translated_plan})

            if markdown_logger:
                markdown_logger.log_agent_output("Translator", {
                    "translated_length": len(translated_plan)
                })
            
            return state
        except Exception as e:
            logger.error(f"Translator error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Translator", str(e))
            state.setdefault("errors", []).append(f"Translator: {str(e)}")
            return state
    
    def segmentation_node(state: ActionPlanState) -> ActionPlanState:
        """Segmentation node."""
        logger.info("Executing Segmentation")
        data = {"translated_plan": state["translated_plan"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Segmentation", {
                "plan_length": len(state["translated_plan"])
            })
        
        try:
            segmented_chunks = segmentation.execute(data)
            state["segmented_chunks"] = segmented_chunks
            state["current_stage"] = "segmentation"
            
            _save_agent_output(state, "segmentation", {"segmented_chunks": segmented_chunks})

            if markdown_logger:
                markdown_logger.log_agent_output("Segmentation", {
                    "chunks_count": len(segmented_chunks) if isinstance(segmented_chunks, list) else 0
                })
            
            return state
        except Exception as e:
            logger.error(f"Segmentation error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Segmentation", str(e))
            state.setdefault("errors", []).append(f"Segmentation: {str(e)}")
            return state
    
    def term_identifier_node(state: ActionPlanState) -> ActionPlanState:
        """Term identifier node."""
        logger.info("Executing Term Identifier")
        data = {"segmented_chunks": state["segmented_chunks"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Term Identifier", {
                "chunks_count": len(state["segmented_chunks"]) if isinstance(state["segmented_chunks"], list) else 0
            })
        
        try:
            identified_terms = term_identifier.execute(data)
            state["identified_terms"] = identified_terms
            state["current_stage"] = "term_identifier"
            
            _save_agent_output(state, "term_identifier", {"identified_terms": identified_terms})

            if markdown_logger:
                markdown_logger.log_agent_output("Term Identifier", {
                    "terms_count": len(identified_terms) if isinstance(identified_terms, list) else 0
                })
            
            return state
        except Exception as e:
            logger.error(f"Term Identifier error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Term Identifier", str(e))
            state.setdefault("errors", []).append(f"Term Identifier: {str(e)}")
            return state
    
    def dictionary_lookup_node(state: ActionPlanState) -> ActionPlanState:
        """Dictionary lookup node."""
        logger.info("Executing Dictionary Lookup")
        data = {"identified_terms": state["identified_terms"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Dictionary Lookup", {
                "terms_count": len(state["identified_terms"]) if isinstance(state["identified_terms"], list) else 0
            })
        
        try:
            dictionary_corrections = dictionary_lookup.execute(data)
            state["dictionary_corrections"] = dictionary_corrections
            state["current_stage"] = "dictionary_lookup"
            
            _save_agent_output(state, "dictionary_lookup", {"dictionary_corrections": dictionary_corrections})

            if markdown_logger:
                markdown_logger.log_agent_output("Dictionary Lookup", {
                    "corrections_count": len(dictionary_corrections) if isinstance(dictionary_corrections, (list, dict)) else 0
                })
            
            return state
        except Exception as e:
            logger.error(f"Dictionary Lookup error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Dictionary Lookup", str(e))
            state.setdefault("errors", []).append(f"Dictionary Lookup: {str(e)}")
            return state
    
    def refinement_node(state: ActionPlanState) -> ActionPlanState:
        """Translation refinement node."""
        logger.info("Executing Translation Refinement")
        data = {
            "translated_plan": state["translated_plan"],
            "dictionary_corrections": state["dictionary_corrections"]
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Translation Refinement", {
                "plan_length": len(state["translated_plan"]),
                "corrections_count": len(state["dictionary_corrections"]) if isinstance(state["dictionary_corrections"], (list, dict)) else 0
            })
        
        try:
            final_persian_plan = translation_refinement.execute(data)
            state["final_persian_plan"] = final_persian_plan
            state["current_stage"] = "refinement"
            
            _save_agent_output(state, "translation_refinement", {"final_persian_plan": final_persian_plan})

            if markdown_logger:
                markdown_logger.log_agent_output("Translation Refinement", {
                    "final_plan_length": len(final_persian_plan)
                })
            
            return state
        except Exception as e:
            logger.error(f"Translation Refinement error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Translation Refinement", str(e))
            state.setdefault("errors", []).append(f"Translation Refinement: {str(e)}")
            return state
    
    def assigning_translator_node(state: ActionPlanState) -> ActionPlanState:
        """Assigning translator node - corrects organizational assignments in Persian translation."""
        logger.info("Executing Assigning Translator")
        data = {"final_persian_plan": state["final_persian_plan"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Assigning Translator", {
                "plan_length": len(state["final_persian_plan"])
            })
        
        try:
            corrected_persian_plan = assigning_translator.execute(data)
            state["final_persian_plan"] = corrected_persian_plan
            state["current_stage"] = "assigning_translator"
            
            _save_agent_output(state, "assigning_translator", {"final_persian_plan": corrected_persian_plan})

            if markdown_logger:
                markdown_logger.log_agent_output("Assigning Translator", {
                    "corrected_plan_length": len(corrected_persian_plan)
                })
            
            return state
        except Exception as e:
            logger.error(f"Assigning Translator error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Assigning Translator", str(e))
            state.setdefault("errors", []).append(f"Assigning Translator: {str(e)}")
            # Keep the original plan if correction fails
            return state
    
    def comprehensive_quality_validator_node(state: ActionPlanState) -> ActionPlanState:
        """Comprehensive quality validator node."""
        logger.info("Executing Comprehensive Quality Validator")
        
        # Initialize validator
        validator = ComprehensiveQualityValidator(
            agent_name="quality_checker",
            dynamic_settings=dynamic_settings,
            markdown_logger=markdown_logger
        )
        
        # Prepare validation data
        validation_data = {
            "final_plan": state.get("final_plan", ""),
            "subject": state["subject"],
            "orchestrator_context": state.get("orchestrator_context", {}),
            "assigned_actions": state.get("assigned_actions", []),
            "original_input": state.get("original_input", {}),
            "validator_retry_count": state.get("validator_retry_count", 0)
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("ComprehensiveQualityValidator", {
                "subject": state["subject"],
                "plan_length": len(state.get("final_plan", "")),
                "retry_count": state.get("validator_retry_count", 0)
            })
        
        try:
            result = validator.execute(validation_data)
            
            # Update state based on validation result
            state["validation_report"] = result
            state["current_stage"] = "comprehensive_quality_validator"
            
            _save_agent_output(state, "comprehensive_quality_validator", result)

            # Handle different statuses
            if result.get("status") == "approve":
                # Plan approved, keep final_plan as is
                if markdown_logger:
                    markdown_logger.log_agent_output("ComprehensiveQualityValidator", {
                        "status": "approved",
                        "quality_score": result.get("quality_score", 0.0),
                        "validation_report": result.get("validation_report", {})
                    })
            
            elif result.get("status") == "self_repair":
                # Self-repair completed, update final_plan
                state["final_plan"] = result.get("repaired_plan", state.get("final_plan", ""))
                if "repairs_made" in result:
                    state.setdefault("quality_repairs", []).extend(result["repairs_made"])
                
                if markdown_logger:
                    markdown_logger.log_agent_output("ComprehensiveQualityValidator", {
                        "status": "self_repaired",
                        "repairs_made": result.get("repairs_made", []),
                        "diagnosis": result.get("diagnosis", {}),
                        "validation_report": result.get("validation_report", {})
                    })
            
            elif result.get("status") == "agent_rerun":
                # Agent re-run requested
                state["validator_retry_count"] = result.get("retry_count", 0)
                
                if markdown_logger:
                    log_output = {
                        "status": "agent_rerun_requested",
                        "responsible_agent": result.get("responsible_agent", "unknown"),
                        "issue_description": result.get("issue_description", ""),
                        "targeted_feedback": result.get("targeted_feedback", ""),
                        "diagnosis": result.get("diagnosis", {}),
                        "validation_report": result.get("validation_report", {})
                    }
                    markdown_logger.log_agent_output("ComprehensiveQualityValidator", log_output)
            
            return state
        
        except Exception as e:
            logger.error(f"Comprehensive Quality Validator error: {e}")
            if markdown_logger:
                markdown_logger.log_error("ComprehensiveQualityValidator", str(e))
            
            # On error, approve and continue to avoid blocking
            state["validation_report"] = {
                "status": "approve",
                "quality_score": 0.5,
                "error": str(e)
            }
            state.setdefault("errors", []).append(f"Comprehensive Quality Validator: {str(e)}")
            return state
    
    # Define routing logic
    def should_continue_after_quality(state: ActionPlanState) -> str:
        """Decide whether to continue or retry based on quality feedback."""
        feedback = state.get("quality_feedback", {})
        status = feedback.get("status", "retry")
        current_stage = state.get("current_stage", "")
        
        # Initialize retry count if not exists
        if "retry_count" not in state:
            state["retry_count"] = {}
        
        retry_count = state["retry_count"].get(current_stage, 0)
        max_retries = settings.max_retries
        
        if status == "pass":
            # Reset retry count and proceed
            state["retry_count"][current_stage] = 0
            
            # Route to next stage (NEW: includes analyzer → analyzer_d)
            if current_stage == "extractor":
                return "timing_node"
            elif current_stage == "timing":
                return "assigner"
            elif current_stage == "assigner":
                return "formatter"
            else:
                return "formatter"
        
        elif retry_count < max_retries:
            # Retry current stage
            state["retry_count"][current_stage] = retry_count + 1
            logger.warning(f"Retrying {current_stage} (attempt {retry_count + 1}/{max_retries})")
            
            if markdown_logger:
                markdown_logger.log_retry_attempt(
                    current_stage, 
                    retry_count + 1, 
                    max_retries,
                    feedback.get("feedback", "Quality check failed")
                )
            
            return current_stage
        
        else:
            # Max retries exceeded, proceed anyway with warning
            logger.error(f"Max retries exceeded for {current_stage}, proceeding...")
            state.setdefault("errors", []).append(
                f"Quality check failed for {current_stage} after {max_retries} retries"
            )
            
            # Proceed to next stage (NEW: includes analyzer → analyzer_d)
            if current_stage == "extractor":
                return "timing_node"
            elif current_stage == "timing":
                return "assigner"
            elif current_stage == "assigner":
                return "formatter"
            else:
                return "formatter"
    
    def route_validator_decision(state: ActionPlanState) -> str:
        """Route based on comprehensive validator decision."""
        validation_result = state.get("validation_report", {})
        status = validation_result.get("status", "approve")
        
        if status == "approve":
            return "translator"
        elif status == "self_repair":
            return "translator"
        elif status == "agent_rerun":
            return "agent_rerun"
        else:
            # Default: proceed to translator
            return "translator"
    
    def route_to_responsible_agent(state: ActionPlanState) -> str:
        """Route to the agent that needs to re-execute."""
        validation_result = state.get("validation_report", {})
        diagnosis = validation_result.get("diagnosis", {})
        responsible = diagnosis.get("responsible_agent", "formatter")
        
        # Check retry limit
        retry_count = state.get("validator_retry_count", 0)
        max_retries = settings.max_validator_retries
        
        if retry_count >= max_retries:
            logger.warning(f"Max validator retries ({max_retries}) reached, proceeding to translator")
            return "translator"
        
        # Map agent names to node names
        agent_node_map = {
            "orchestrator": "orchestrator",
            "analyzer": "analyzer",
            "phase3": "phase3",
            "special_protocols": "special_protocols",
            "extractor": "extractor",
            "deduplicator": "deduplicator",
            "selector": "selector",
            "timing": "timing_node",
            "assigner": "assigner",
            "formatter": "formatter"
        }
        
        target_node = agent_node_map.get(responsible, "formatter")
        logger.info(f"Routing to {target_node} for re-execution (retry {retry_count}/{max_retries})")
        
        return target_node
    
    # Build the graph
    workflow = StateGraph(ActionPlanState)
    
    # Add nodes (NEW: includes phase3, deduplicator, selector, special_protocols, and translation workflow)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("phase3", phase3_node)
    workflow.add_node("special_protocols", special_protocols_node)  # NEW: Special Protocols processor
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("deduplicator", deduplicator_node)
    workflow.add_node("selector", selector_node)
    workflow.add_node("timing_node", timing_node)
    workflow.add_node("assigner", assigner_node)
    workflow.add_node("quality_checker", quality_checker_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("comprehensive_quality_validator", comprehensive_quality_validator_node)
    
    # Add translation workflow nodes
    workflow.add_node("translator", translator_node)
    workflow.add_node("segmentation", segmentation_node)
    workflow.add_node("term_identifier", term_identifier_node)
    workflow.add_node("dictionary_lookup", dictionary_lookup_node)
    workflow.add_node("refinement", refinement_node)
    workflow.add_node("assigning_translator", assigning_translator_node)
    
    # Set entry point
    workflow.set_entry_point("orchestrator")
    
    # Add edges (FIXED: Sequential execution to avoid concurrent state updates)
    # Sequential flow: orchestrator → special_protocols → analyzer → phase3 → extractor
    # This ensures no concurrent writes to state
    workflow.add_edge("orchestrator", "special_protocols")
    workflow.add_edge("special_protocols", "analyzer")
    workflow.add_edge("analyzer", "phase3")
    workflow.add_edge("phase3", "extractor")
    
    # Continue with normal flow after extractor
    workflow.add_edge("extractor", "selector")
    workflow.add_edge("selector", "deduplicator")
    workflow.add_edge("deduplicator", "timing_node")
    workflow.add_edge("timing_node", "assigner")
    workflow.add_edge("assigner", "formatter")
    
    # Conditional routing from formatter based on comprehensive validator setting
    def formatter_routing(state: ActionPlanState) -> str:
        """Route from formatter based on comprehensive validator setting."""
        if settings.enable_comprehensive_validator:
            return "comprehensive_quality_validator"
        else:
            logger.info("Comprehensive Quality Validator is disabled, skipping to translator")
            return "translator"
    
    workflow.add_conditional_edges(
        "formatter",
        formatter_routing,
        {
            "comprehensive_quality_validator": "comprehensive_quality_validator",
            "translator": "translator"
        }
    )
    
    # Conditional edges from comprehensive validator
    def validator_routing(state: ActionPlanState) -> str:
        """Combined routing logic for validator."""
        validation_result = state.get("validation_report", {})
        status = validation_result.get("status", "approve")
        
        if status == "approve" or status == "self_repair":
            return "translator"
        elif status == "agent_rerun":
            return route_to_responsible_agent(state)
        else:
            return "translator"
    
    workflow.add_conditional_edges(
        "comprehensive_quality_validator",
        validator_routing,
        {
            "translator": "translator",
            "orchestrator": "orchestrator",
            "analyzer": "analyzer",
            "phase3": "phase3",
            "special_protocols": "special_protocols",
            "extractor": "extractor",
            "deduplicator": "deduplicator",
            "selector": "selector",
            "timing": "timing_node",
            "assigner": "assigner",
            "formatter": "formatter"
        }
    )
    
    # Translation workflow (translator → ... → refinement → assigning_translator → END)
    workflow.add_edge("translator", "segmentation")
    workflow.add_edge("segmentation", "term_identifier")
    workflow.add_edge("term_identifier", "dictionary_lookup")
    workflow.add_edge("dictionary_lookup", "refinement")
    workflow.add_edge("refinement", "assigning_translator")
    workflow.add_edge("assigning_translator", END)
    
    # Compile and return
    compiled_workflow = workflow.compile()
    logger.info("Workflow compiled successfully")
    
    return compiled_workflow


