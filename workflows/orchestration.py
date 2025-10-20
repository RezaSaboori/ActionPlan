"""LangGraph workflow orchestration."""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from config.settings import get_settings
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG
from rag_tools.graph_rag import GraphRAG
from rag_tools.vector_rag import VectorRAG
from agents.orchestrator import OrchestratorAgent
from agents.analyzer import AnalyzerAgent
from agents.analyzer_d import AnalyzerDAgent
from agents.extractor import ExtractorAgent
from agents.prioritizer import PrioritizerAgent
from agents.assigner import AssignerAgent
from agents.quality_checker import QualityCheckerAgent, ComprehensiveQualityValidator
from agents.formatter import FormatterAgent
from agents.translator import TranslatorAgent
from agents.segmentation import SegmentationAgent
from agents.term_identifier import TermIdentifierAgent
from agents.dictionary_lookup import DictionaryLookupAgent
from agents.translation_refinement import TranslationRefinementAgent
from .graph_state import ActionPlanState

logger = logging.getLogger(__name__)


def create_workflow(markdown_logger=None):
    """
    Create and compile the LangGraph workflow.
    
    Args:
        markdown_logger: Optional MarkdownLogger instance for comprehensive logging
    
    Returns:
        Compiled workflow graph
    """
    settings = get_settings()
    
    # Initialize LLM client
    llm_client = OllamaClient()
    
    # Initialize main RAG tools (excludes Dictionary.md for main agents)
    main_graph_rag = GraphRAG(collection_name=settings.graph_prefix, markdown_logger=markdown_logger)
    main_vector_rag = VectorRAG(collection_name=settings.documents_collection, markdown_logger=markdown_logger)
    main_hybrid_rag = HybridRAG(
        graph_collection=settings.graph_prefix,
        vector_collection=settings.documents_collection,
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
    orchestrator = OrchestratorAgent(llm_client, main_hybrid_rag, main_graph_rag, markdown_logger)
    analyzer = AnalyzerAgent(llm_client, main_hybrid_rag, main_graph_rag, markdown_logger)
    analyzer_d = AnalyzerDAgent(llm_client, main_hybrid_rag, main_graph_rag, markdown_logger)
    quality_checker = QualityCheckerAgent(llm_client, main_hybrid_rag, markdown_logger)
    extractor = ExtractorAgent(llm_client, main_graph_rag, quality_checker, orchestrator, markdown_logger)
    prioritizer = PrioritizerAgent(llm_client, main_hybrid_rag, markdown_logger)
    assigner = AssignerAgent(llm_client, main_hybrid_rag, markdown_logger)
    formatter = FormatterAgent(llm_client, markdown_logger)
    
    # Initialize translation agents (Dictionary Lookup uses dictionary RAG)
    translator = TranslatorAgent(llm_client, markdown_logger)
    segmentation = SegmentationAgent(llm_client, markdown_logger)
    term_identifier = TermIdentifierAgent(llm_client, markdown_logger)
    dictionary_lookup = DictionaryLookupAgent(llm_client, dictionary_hybrid_rag, markdown_logger)
    translation_refinement = TranslationRefinementAgent(llm_client, markdown_logger)
    
    # Define node functions
    def orchestrator_node(state: ActionPlanState) -> ActionPlanState:
        """Orchestrator node."""
        logger.info("Executing Orchestrator")
        if markdown_logger:
            markdown_logger.log_agent_start("Orchestrator", {"subject": state["subject"]})
        
        try:
            result = orchestrator.execute(state["subject"])
            state["rules_context"] = result
            state["plan_structure"] = result.get("structure", {})
            
            # Extract topics for Analyzer
            topics = result.get("topics", [])
            if not topics:
                # Fallback: extract from subject
                topics = [word for word in state["subject"].split() if len(word) > 3]
            state["topics"] = topics
            
            # Store orchestrator context for comprehensive validator
            state["orchestrator_context"] = {
                "rules_context": result,
                "structure": result.get("structure", {}),
                "topics": topics,
                "guidelines": result.get("guidelines", [])
            }
            
            # Store original input parameters for comprehensive validator
            state["original_input"] = {
                "subject": state["subject"],
                "timing": state.get("timing"),
                "trigger": state.get("trigger"),
                "responsible_party": state.get("responsible_party"),
                "process_owner": state.get("process_owner")
            }
            
            state["current_stage"] = "orchestrator"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Orchestrator", {
                    "topics": topics,
                    "structure": result.get("structure", {})
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
        context = {
            "subject": state["subject"],
            "topics": state.get("topics", []),
            "structure": state.get("plan_structure", {})
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Analyzer", context)
        
        try:
            result = analyzer.execute(context)
            
            # Phase 1 output: context_map
            state["context_map"] = result.get("context_map", {})
            
            # Phase 2 output: identified_subjects
            state["identified_subjects"] = result.get("identified_subjects", [])
            
            state["current_stage"] = "analyzer"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Analyzer", {
                    "identified_subjects": state["identified_subjects"],
                    "documents_found": len(state["context_map"].get("documents", []))
                })
            
            return state
        except Exception as e:
            logger.error(f"Analyzer error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Analyzer", str(e))
            state.setdefault("errors", []).append(f"Analyzer: {str(e)}")
            return state
    
    def analyzer_d_node(state: ActionPlanState) -> ActionPlanState:
        """Analyzer_D node (deep analysis)."""
        logger.info("Executing Analyzer_D (Deep Analysis)")
        context = {
            "identified_subjects": state.get("identified_subjects", [])
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Analyzer_D", context)
        
        try:
            result = analyzer_d.execute(context)
            
            # Output: subject_nodes
            state["subject_nodes"] = result.get("subject_nodes", [])
            
            state["current_stage"] = "analyzer_d"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Analyzer_D", {
                    "subject_nodes_count": len(state["subject_nodes"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Analyzer_D error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Analyzer_D", str(e))
            state.setdefault("errors", []).append(f"Analyzer_D: {str(e)}")
            return state
    
    def extractor_node(state: ActionPlanState) -> ActionPlanState:
        """Extractor node (multi-subject processing)."""
        logger.info("Executing Extractor (Multi-Subject)")
        input_data = {"subject_nodes": state.get("subject_nodes", [])}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Extractor", {
                "subject_nodes_count": len(input_data["subject_nodes"])
            })
        
        try:
            # Use new multi-subject processing
            result = extractor.execute(input_data)
            
            # Output: subject_actions
            state["subject_actions"] = result.get("subject_actions", [])
            
            # Also consolidate into refined_actions for backward compatibility
            all_actions = []
            for subject_data in state["subject_actions"]:
                all_actions.extend(subject_data.get("actions", []))
            state["refined_actions"] = all_actions
            
            state["current_stage"] = "extractor"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Extractor", {
                    "total_actions": len(all_actions),
                    "subjects_processed": len(state["subject_actions"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Extractor error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Extractor", str(e))
            state.setdefault("errors", []).append(f"Extractor: {str(e)}")
            return state
    
    def prioritizer_node(state: ActionPlanState) -> ActionPlanState:
        """Prioritizer node."""
        logger.info("Executing Prioritizer")
        input_data = {
            "refined_actions": state["refined_actions"],
            "timing": state.get("timing")  # Pass user timing if provided
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Prioritizer", {
                "actions_count": len(state["refined_actions"]),
                "user_timing": state.get("timing")
            })
        
        try:
            result = prioritizer.execute(input_data)
            state["prioritized_actions"] = result.get("prioritized_actions", [])
            state["current_stage"] = "prioritizer"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Prioritizer", {
                    "prioritized_actions_count": len(state["prioritized_actions"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Prioritizer error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Prioritizer", str(e))
            state.setdefault("errors", []).append(f"Prioritizer: {str(e)}")
            return state
    
    def assigner_node(state: ActionPlanState) -> ActionPlanState:
        """Assigner node."""
        logger.info("Executing Assigner")
        input_data = {"prioritized_actions": state["prioritized_actions"]}
        
        if markdown_logger:
            markdown_logger.log_agent_start("Assigner", {
                "actions_count": len(state["prioritized_actions"])
            })
        
        try:
            result = assigner.execute(input_data)
            state["assigned_actions"] = result.get("assigned_actions", [])
            state["current_stage"] = "assigner"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Assigner", {
                    "assigned_actions_count": len(state["assigned_actions"])
                })
            
            return state
        except Exception as e:
            logger.error(f"Assigner error: {e}")
            if markdown_logger:
                markdown_logger.log_error("Assigner", str(e))
            state.setdefault("errors", []).append(f"Assigner: {str(e)}")
            return state
    
    def quality_checker_node(state: ActionPlanState) -> ActionPlanState:
        """Quality checker node."""
        logger.info("Executing Quality Checker")
        stage = state.get("current_stage", "unknown")
        
        # Get appropriate data for stage
        if stage == "extractor":
            data = {"refined_actions": state.get("refined_actions", [])}
        elif stage == "prioritizer":
            data = {"prioritized_actions": state.get("prioritized_actions", [])}
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
        """Formatter node."""
        logger.info("Executing Formatter")
        data = {
            "subject": state["subject"],
            "assigned_actions": state["assigned_actions"],
            "rules_context": state.get("rules_context", {}),
            "trigger": state.get("trigger"),
            "responsible_party": state.get("responsible_party"),
            "process_owner": state.get("process_owner")
        }
        
        if markdown_logger:
            markdown_logger.log_agent_start("Formatter", {
                "subject": state["subject"],
                "actions_count": len(state["assigned_actions"]),
                "trigger": state.get("trigger"),
                "responsible_party": state.get("responsible_party"),
                "process_owner": state.get("process_owner")
            })
        
        try:
            plan = formatter.execute(data)
            state["final_plan"] = plan
            state["current_stage"] = "formatter"
            
            if markdown_logger:
                markdown_logger.log_agent_output("Formatter", {
                    "plan_length": len(plan),
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
    
    def comprehensive_quality_validator_node(state: ActionPlanState) -> ActionPlanState:
        """Comprehensive quality validator node."""
        logger.info("Executing Comprehensive Quality Validator")
        
        # Initialize validator
        validator = ComprehensiveQualityValidator(
            llm_client=llm_client,
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
                return "prioritizer"
            elif current_stage == "prioritizer":
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
                return "prioritizer"
            elif current_stage == "prioritizer":
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
            "analyzer_d": "analyzer_d",
            "extractor": "extractor",
            "prioritizer": "prioritizer",
            "assigner": "assigner",
            "formatter": "formatter"
        }
        
        target_node = agent_node_map.get(responsible, "formatter")
        logger.info(f"Routing to {target_node} for re-execution (retry {retry_count}/{max_retries})")
        
        return target_node
    
    # Build the graph
    workflow = StateGraph(ActionPlanState)
    
    # Add nodes (NEW: includes analyzer_d and translation workflow)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("analyzer_d", analyzer_d_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("prioritizer", prioritizer_node)
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
    
    # Set entry point
    workflow.set_entry_point("orchestrator")
    
    # Add edges (NEW: Linear flow without intermediate quality checks)
    workflow.add_edge("orchestrator", "analyzer")
    workflow.add_edge("analyzer", "analyzer_d")
    workflow.add_edge("analyzer_d", "extractor")
    workflow.add_edge("extractor", "prioritizer")
    workflow.add_edge("prioritizer", "assigner")
    workflow.add_edge("assigner", "formatter")
    
    # Comprehensive quality validator after formatter
    workflow.add_edge("formatter", "comprehensive_quality_validator")
    
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
            "analyzer_d": "analyzer_d",
            "extractor": "extractor",
            "prioritizer": "prioritizer",
            "assigner": "assigner",
            "formatter": "formatter"
        }
    )
    
    # Translation workflow (translator → ... → refinement → END)
    workflow.add_edge("translator", "segmentation")
    workflow.add_edge("segmentation", "term_identifier")
    workflow.add_edge("term_identifier", "dictionary_lookup")
    workflow.add_edge("dictionary_lookup", "refinement")
    workflow.add_edge("refinement", END)
    
    # Compile and return
    compiled_workflow = workflow.compile()
    logger.info("Workflow compiled successfully")
    
    return compiled_workflow

