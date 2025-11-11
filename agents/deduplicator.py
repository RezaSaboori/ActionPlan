"""De-duplicator and Merger Agent for action consolidation."""

import logging
import json
from typing import Dict, Any, List, Optional
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)

# Define a batch size for processing actions to avoid overloading the LLM
ACTION_BATCH_SIZE = 15


class DeduplicatorAgent:
    """
    De-duplicator and Merger Agent for consolidating extracted actions.
    
    Workflow:
    - Receives complete_actions (with who/when) and flagged_actions (missing who/when)
    - Uses LLM to identify and merge duplicate or similar actions
    - Preserves all source citations when merging
    - Maintains separation between complete and flagged actions
    - Returns refined action lists with merge metadata
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        markdown_logger=None
    ):
        """
        Initialize De-duplicator Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("deduplicator")
        logger.info(f"Initialized DeduplicatorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute de-duplication and merging logic using batch processing.
        
        Enhanced to handle formulas and tables alongside actions.
        Preserves all references when merging.
        
        Args:
            data: Dictionary containing:
                - complete_actions: List of actions with who/when defined
                - flagged_actions: List of actions missing who/when
                - formulas: List of formula objects (optional)
                - tables: List of table objects (optional)
                
        Returns:
            Dictionary with:
                - refined_complete_actions: Merged complete actions
                - refined_flagged_actions: Merged flagged actions
                - formulas: Deduplicated formulas
                - tables: Deduplicated tables
                - merge_summary: Statistics about merging
        """
        complete_actions = data.get("complete_actions", [])
        flagged_actions = data.get("flagged_actions", [])
        formulas = data.get("formulas", [])
        tables = data.get("tables", [])
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT STARTING")
        logger.info(f"Input: {len(complete_actions)} complete actions, {len(flagged_actions)} flagged actions")
        logger.info(f"       {len(formulas)} formulas, {len(tables)} tables")
        logger.info(f"=" * 80)
        
        # Log input details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Input Summary",
                {
                    "complete_actions_count": len(complete_actions),
                    "flagged_actions_count": len(flagged_actions),
                    "total_actions": len(complete_actions) + len(flagged_actions),
                    "formulas_count": len(formulas),
                    "tables_count": len(tables)
                }
            )
        
        # If no actions, return empty
        if not complete_actions and not flagged_actions:
            logger.warning("No actions provided for de-duplication")
            return {
                "refined_complete_actions": [],
                "refined_flagged_actions": [],
                "formulas": formulas,  # Pass through formulas
                "tables": tables,  # Pass through tables
                "merge_summary": {
                    "total_input_complete": 0,
                    "total_input_flagged": 0,
                    "total_output_complete": 0,
                    "total_output_flagged": 0,
                    "merges_performed": 0,
                    "actions_unchanged": 0
                }
            }
        
        # Batch process complete actions
        final_complete_actions = self._batch_process_actions(complete_actions, "complete")
        
        # Batch process flagged actions
        final_flagged_actions = self._batch_process_actions(flagged_actions, "flagged")
        
        # Create final merge summary
        merges_performed = (len(complete_actions) - len(final_complete_actions)) + \
                           (len(flagged_actions) - len(final_flagged_actions))
        
        final_summary = {
            "total_input_complete": len(complete_actions),
            "total_input_flagged": len(flagged_actions),
            "total_output_complete": len(final_complete_actions),
            "total_output_flagged": len(final_flagged_actions),
            "merges_performed": merges_performed,
            "actions_unchanged": len(final_complete_actions) + len(final_flagged_actions)
        }
        
        # Formulas and tables are passed through (they're unique by nature)
        # Each formula has unique computation, each table has unique structure
        final_formulas = formulas
        final_tables = tables
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT COMPLETED")
        logger.info(f"Output: {len(final_complete_actions)} complete actions, {len(final_flagged_actions)} flagged actions")
        logger.info(f"        {len(final_formulas)} formulas, {len(final_tables)} tables")
        logger.info(f"Merges performed: {final_summary.get('merges_performed', 0)}")
        logger.info(f"=" * 80)
        
        # Log output details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Output Summary",
                {
                    "refined_complete_actions_count": len(final_complete_actions),
                    "refined_flagged_actions_count": len(final_flagged_actions),
                    "formulas_count": len(final_formulas),
                    "tables_count": len(final_tables),
                    "merge_summary": final_summary
                }
            )
            
            # Log detailed merge information
            self._log_merge_details(
                complete_actions, 
                flagged_actions, 
                final_complete_actions, 
                final_flagged_actions,
                final_summary
            )
        
        return {
            "refined_complete_actions": final_complete_actions,
            "refined_flagged_actions": final_flagged_actions,
            "formulas": final_formulas,
            "tables": final_tables,
            "merge_summary": final_summary
        }

    def _batch_process_actions(self, actions: List[Dict[str, Any]], action_type: str) -> List[Dict[str, Any]]:
        """
        Process actions in batches to avoid LLM overload.
        
        Args:
            actions: The list of actions to process
            action_type: "complete" or "flagged" for logging purposes
            
        Returns:
            A list of refined (deduplicated) actions.
        """
        if not actions:
            return []

        refined_actions = []
        for i in range(0, len(actions), ACTION_BATCH_SIZE):
            batch = actions[i:i + ACTION_BATCH_SIZE]
            logger.info(f"Processing {action_type} actions batch {i//ACTION_BATCH_SIZE + 1}...")
            
            # Use the LLM to deduplicate the current batch
            if action_type == "complete":
                result = self._llm_deduplicate(batch, [])
                refined_actions.extend(result.get("complete_actions", batch))
            else:
                result = self._llm_deduplicate([], batch)
                refined_actions.extend(result.get("flagged_actions", batch))
        
        return refined_actions
    
    def _llm_deduplicate(
        self,
        complete_actions: List[Dict[str, Any]],
        flagged_actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to deduplicate and merge actions.
        
        Args:
            complete_actions: List of complete actions
            flagged_actions: List of flagged actions
            
        Returns:
            Dictionary with refined actions and merge summary
        """
        logger.info("Performing LLM-based de-duplication and merging")
        
        # Prepare input for LLM
        prompt = f"""You are given two lists of actions extracted from health policy documents:

1. COMPLETE ACTIONS (have who/when defined): {len(complete_actions)} actions
2. FLAGGED ACTIONS (missing who/when): {len(flagged_actions)} actions

Your task is to identify and merge duplicate or highly similar actions while preserving all source information.

COMPLETE ACTIONS:
{json.dumps(complete_actions, indent=2)}

FLAGGED ACTIONS:
{json.dumps(flagged_actions, indent=2)}

Please analyze these actions and:
1. Identify duplicates or highly similar actions within each list
2. Merge similar actions, combining their sources
3. Preserve the most complete and specific description
4. Keep complete and flagged actions separate
5. Provide a merge summary

Return a JSON object with the structure defined in your system prompt."""
        
        try:
            logger.debug("Sending de-duplication request to LLM")
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            logger.debug(f"LLM response type: {type(result)}")
            
            if isinstance(result, dict):
                # Validate response structure
                if "complete_actions" not in result:
                    result["complete_actions"] = complete_actions
                    logger.warning("LLM didn't return complete_actions, using original")
                
                if "flagged_actions" not in result:
                    result["flagged_actions"] = flagged_actions
                    logger.warning("LLM didn't return flagged_actions, using original")
                
                if "merge_summary" not in result:
                    result["merge_summary"] = {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "total_output_complete": len(result.get("complete_actions", [])),
                        "total_output_flagged": len(result.get("flagged_actions", [])),
                        "merges_performed": 0,
                        "actions_unchanged": len(complete_actions) + len(flagged_actions)
                    }
                
                logger.info(f"De-duplication successful: {len(result['complete_actions'])} complete, {len(result['flagged_actions'])} flagged")
                return result
            else:
                logger.warning(f"Unexpected LLM response format: {type(result)}")
                # Return original actions unchanged
                return {
                    "complete_actions": complete_actions,
                    "flagged_actions": flagged_actions,
                    "merge_summary": {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "total_output_complete": len(complete_actions),
                        "total_output_flagged": len(flagged_actions),
                        "merges_performed": 0,
                        "actions_unchanged": len(complete_actions) + len(flagged_actions)
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in LLM de-duplication: {e}", exc_info=True)
            # Return original actions unchanged on error
            return {
                "complete_actions": complete_actions,
                "flagged_actions": flagged_actions,
                "merge_summary": {
                    "total_input_complete": len(complete_actions),
                    "total_input_flagged": len(flagged_actions),
                    "total_output_complete": len(complete_actions),
                    "total_output_flagged": len(flagged_actions),
                    "merges_performed": 0,
                    "actions_unchanged": len(complete_actions) + len(flagged_actions),
                    "error": str(e)
                }
            }
    
    def _log_merge_details(
        self,
        original_complete: List[Dict[str, Any]],
        original_flagged: List[Dict[str, Any]],
        refined_complete: List[Dict[str, Any]],
        refined_flagged: List[Dict[str, Any]],
        merge_summary: Dict[str, Any]
    ):
        """
        Log detailed merge information to markdown logger.
        
        Args:
            original_complete: Original complete actions
            original_flagged: Original flagged actions
            refined_complete: Refined complete actions
            refined_flagged: Refined flagged actions
            merge_summary: Merge statistics
        """
        if not self.markdown_logger:
            return
        
        # Log merge statistics
        self.markdown_logger.add_text("### Merge Statistics", bold=True)
        self.markdown_logger.add_text("")
        self.markdown_logger.add_list_item(f"Input Complete Actions: {len(original_complete)}")
        self.markdown_logger.add_list_item(f"Input Flagged Actions: {len(original_flagged)}")
        self.markdown_logger.add_list_item(f"Output Complete Actions: {len(refined_complete)}")
        self.markdown_logger.add_list_item(f"Output Flagged Actions: {len(refined_flagged)}")
        self.markdown_logger.add_list_item(f"Merges Performed: {merge_summary.get('merges_performed', 0)}")
        self.markdown_logger.add_list_item(f"Actions Unchanged: {merge_summary.get('actions_unchanged', 0)}")
        self.markdown_logger.add_text("")
        
        # Log sample merged actions (up to 5)
        if refined_complete:
            self.markdown_logger.add_text("### Sample Merged Complete Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(refined_complete[:5], 1):
                merged_from = action.get("merged_from", [])
                if merged_from:
                    self.markdown_logger.add_text(f"**Action {idx} (Merged from {len(merged_from)} sources):**")
                else:
                    self.markdown_logger.add_text(f"**Action {idx}:**")
                self.markdown_logger.add_list_item(f"Who: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"When: {action.get('when', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"What: {action.get('what', 'N/A')}", level=1)
                if merged_from:
                    self.markdown_logger.add_list_item(f"Merge Rationale: {action.get('merge_rationale', 'N/A')}", level=1)
                self.markdown_logger.add_text("")
        
        # Log sample flagged actions (up to 3)
        if refined_flagged:
            self.markdown_logger.add_text("### Sample Flagged Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(refined_flagged[:3], 1):
                self.markdown_logger.add_text(f"**Flagged Action {idx}:**")
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Missing Fields: {', '.join(action.get('missing_fields', []))}", level=1)
                self.markdown_logger.add_list_item(f"Flag Reason: {action.get('flag_reason', 'N/A')}", level=1)
                self.markdown_logger.add_text("")

