"""Selector Agent for filtering actions based on relevance."""

import logging
import json
import re
from typing import Dict, Any, List, Tuple
from utils.llm_client import LLMClient
from config.prompts import get_prompt, get_selector_user_prompt, get_selector_table_scoring_prompt

logger = logging.getLogger(__name__)

# Define a batch size for processing actions to avoid overloading the LLM
ACTION_BATCH_SIZE = 15


class SelectorAgent:
    """
    Selector Agent for filtering actions based on semantic relevance.
    
    Workflow:
    - Receives problem_statement, user_config, and unified actions list
    - Uses LLM to semantically analyze each action against problem statement and user config
    - Filters both complete and flagged actions based on relevance
    - Discards irrelevant actions completely
    - Returns unified list of relevant actions with relevance scores and rationale
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        markdown_logger=None
    ):
        """
        Initialize Selector Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("selector")
        logger.info(f"Initialized SelectorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute selection logic to filter actions based on relevance.
        
        Handles actions and tables. Formulas are now integrated into actions.
        Preserves references for all selected items.
        
        Args:
            data: Dictionary containing:
                - problem_statement: The refined problem/objective from Orchestrator
                - user_config: User configuration (name, timing, level, phase, subject)
                - actions: Unified list of actions with timing_flagged/actor_flagged flags
                - tables: List of table objects (optional)
                
        Returns:
            Dictionary with:
                - selected_actions: Filtered actions (unified list)
                - tables: Tables (filtered)
                - selection_summary: Statistics about filtering
                - discarded_actions: Actions that were filtered out with reasons
        """
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        actions = data.get("actions", [])
        tables = data.get("tables", [])
        
        # Separate actions by flags for internal processing and logging
        complete_actions = [a for a in actions if not a.get('actor_flagged', False) and not a.get('timing_flagged', False)]
        flagged_actions = [a for a in actions if a.get('actor_flagged', False) or a.get('timing_flagged', False)]
        
        logger.info(f"=" * 80)
        logger.info(f"SELECTOR AGENT STARTING")
        logger.info(f"Input: {len(complete_actions)} complete actions, {len(flagged_actions)} flagged actions")
        logger.info(f"       {len(tables)} tables")
        logger.info(f"Problem Statement: {problem_statement[:100]}...")
        logger.info(f"User Config: {user_config}")
        logger.info(f"=" * 80)
        
        # Log input details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Selector Input Summary",
                {
                    "problem_statement": problem_statement[:200] + "...",
                    "user_config": user_config,
                    "complete_actions_count": len(complete_actions),
                    "flagged_actions_count": len(flagged_actions),
                    "total_actions": len(complete_actions) + len(flagged_actions),
                    "tables_count": len(tables)
                }
            )
            
            # Log all input actions (raw)
            if complete_actions:
                self.markdown_logger.add_text("### Input Complete Actions (All)", bold=True)
                self.markdown_logger.add_text("")
                for idx, action in enumerate(complete_actions, 1):
                    self.markdown_logger.add_text(f"**{idx}. {action.get('action', 'N/A')}**")
                    self.markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                    self.markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                    self.markdown_logger.add_text("")
            
            if flagged_actions:
                self.markdown_logger.add_text("### Input Flagged Actions (All)", bold=True)
                self.markdown_logger.add_text("")
                for idx, action in enumerate(flagged_actions, 1):
                    self.markdown_logger.add_text(f"**{idx}. {action.get('action', 'N/A')}**")
                    self.markdown_logger.add_list_item(f"Missing: {', '.join(action.get('missing_fields', []))}", level=1)
                    self.markdown_logger.add_text("")
        
        # If no actions, return empty
        if not actions:
            logger.warning("No actions provided for selection")
            return {
                "selected_actions": [],
                "tables": tables,  # Pass through tables
                "selection_summary": {
                    "total_input_actions": 0,
                    "total_input_complete": 0,
                    "total_input_flagged": 0,
                    "selected_actions": 0,
                    "selected_complete": 0,
                    "selected_flagged": 0,
                    "discarded_complete": 0,
                    "discarded_flagged": 0,
                    "average_relevance_score": 0.0
                },
                "discarded_actions": []
            }
        
        # Batch process complete actions
        final_selected_complete, discarded_complete_actions = self._batch_process_actions(
            complete_actions, "complete", problem_statement, user_config
        )

        # Batch process flagged actions
        final_selected_flagged, discarded_flagged_actions = self._batch_process_actions(
            flagged_actions, "flagged", problem_statement, user_config
        )
        
        final_discarded = discarded_complete_actions + discarded_flagged_actions
        
        # Combine selected actions into unified list
        all_selected = final_selected_complete + final_selected_flagged
        
        # Create final selection summary
        final_summary = {
            "total_input_actions": len(actions),
            "total_input_complete": len(complete_actions),
            "total_input_flagged": len(flagged_actions),
            "selected_actions": len(all_selected),
            "selected_complete": len(final_selected_complete),
            "selected_flagged": len(final_selected_flagged),
            "discarded_complete": len(complete_actions) - len(final_selected_complete),
            "discarded_flagged": len(flagged_actions) - len(final_selected_flagged),
        }
        
        # Calculate average relevance score if available
        if all_selected:
            total_score = sum(a.get("relevance_score", 0.0) for a in all_selected)
            final_summary["average_relevance_score"] = total_score / len(all_selected)
        else:
            final_summary["average_relevance_score"] = 0.0

        # Filter tables using relevance scoring (after action selection)
        logger.info(f"Filtering {len(tables)} tables...")
        final_tables, discarded_tables = self._filter_tables(
            tables, 
            problem_statement, 
            user_config,
            all_selected  # Pass selected actions for context
        )
        
        # Add table filtering statistics
        final_summary["total_input_tables"] = len(tables)
        final_summary["selected_tables"] = len(final_tables)
        final_summary["discarded_tables"] = len(discarded_tables)
        
        logger.info(f"=" * 80)
        logger.info(f"SELECTOR AGENT COMPLETED")
        logger.info(f"Output: {len(all_selected)} selected actions ({len(final_selected_complete)} complete, {len(final_selected_flagged)} flagged)")
        logger.info(f"        {len(final_tables)} tables (filtered from {len(tables)})")
        logger.info(f"Discarded Actions: {final_summary.get('discarded_complete', 0)} complete, {final_summary.get('discarded_flagged', 0)} flagged")
        logger.info(f"Discarded Tables: {final_summary.get('discarded_tables', 0)}")
        logger.info(f"Average Relevance Score: {final_summary.get('average_relevance_score', 0.0):.2f}")
        logger.info(f="=" * 80)
        
        # Log output details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Selector Output Summary",
                {
                    "selected_actions_count": len(all_selected),
                    "selected_complete_actions_count": len(final_selected_complete),
                    "selected_flagged_actions_count": len(final_selected_flagged),
                    "tables_count": len(final_tables),
                    "discarded_tables_count": len(discarded_tables),
                    "selection_summary": final_summary
                }
            )
            
            # Log detailed selection information
            self._log_selection_details(
                final_selected_complete,
                final_selected_flagged,
                final_discarded,
                final_summary
            )
        
        # Remove tables with empty markdown_content
        initial_table_count = len(final_tables)
        final_tables = [table for table in final_tables if table.get('markdown_content', '') != '']
        removed_empty_count = initial_table_count - len(final_tables)
        
        if removed_empty_count > 0:
            logger.info(f"Removed {removed_empty_count} table(s) with empty markdown_content")
            final_summary["removed_empty_tables"] = removed_empty_count
        
        return {
            "selected_actions": all_selected,
            "tables": final_tables,
            "selection_summary": final_summary,
            "discarded_actions": final_discarded
        }

    def _batch_process_actions(
        self,
        actions: List[Dict[str, Any]],
        action_type: str,
        problem_statement: str,
        user_config: Dict[str, Any]
    ) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
        """
        Process actions in batches to avoid LLM overload.
        
        Args:
            actions: The list of actions to process
            action_type: "complete" or "flagged" for logging purposes
            problem_statement: The problem statement for context
            user_config: The user configuration for context
            
        Returns:
            A tuple of (selected_actions, discarded_actions).
        """
        if not actions:
            return [], []

        all_selected = []
        all_discarded = []

        for i in range(0, len(actions), ACTION_BATCH_SIZE):
            batch = actions[i:i + ACTION_BATCH_SIZE]
            logger.info(f"Processing {action_type} actions batch {i//ACTION_BATCH_SIZE + 1}...")
            
            if action_type == "complete":
                result = self._llm_select(problem_statement, user_config, batch, [])
            else:
                result = self._llm_select(problem_statement, user_config, [], batch)
            
            # Use unified selected_actions output
            all_selected.extend(result.get("selected_actions", []))
            all_discarded.extend(result.get("discarded_actions", []))

        return all_selected, all_discarded
    
    def _llm_select(
        self,
        problem_statement: str,
        user_config: Dict[str, Any],
        complete_actions: List[Dict[str, Any]],
        flagged_actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to select relevant actions based on semantic analysis.
        
        Args:
            problem_statement: The refined problem/objective
            user_config: User configuration
            complete_actions: List of complete actions
            flagged_actions: List of flagged actions
            
        Returns:
            Dictionary with selected actions and selection summary
        """
        logger.info("Performing LLM-based semantic selection")
        
        # Prepare input for LLM using centralized template
        prompt = get_selector_user_prompt(
            problem_statement=problem_statement,
            user_config=user_config,
            complete_actions=complete_actions,
            flagged_actions=flagged_actions
        )
        
        try:
            logger.debug("Sending selection request to LLM")
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2,
                json_mode=True  # Instruct the client to enforce JSON output
            )
            
            # Log raw LLM output to markdown
            if self.markdown_logger:
                self.markdown_logger.add_text("### Raw LLM Selection Output", bold=True)
                self.markdown_logger.add_text("")
                self.markdown_logger.add_code_block(json.dumps(result, indent=2, ensure_ascii=False), language="json")
                self.markdown_logger.add_text("")
            
            logger.debug(f"LLM response type: {type(result)}")
            
            if isinstance(result, dict):
                # Validate response structure for unified output
                if "selected_actions" not in result:
                    # Fallback: combine complete and flagged actions
                    result["selected_actions"] = complete_actions + flagged_actions
                    logger.warning("LLM didn't return selected_actions, using all original")
                
                selected_actions = result.get("selected_actions", [])
                
                # Normalize selected_actions: map IDs back to full action objects if needed
                all_input_actions = complete_actions + flagged_actions
                selected_actions = self._normalize_selected_actions(selected_actions, all_input_actions)
                
                # Validate normalized actions have required fields
                selected_actions = self._validate_action_fields(selected_actions, "selected")
                result["selected_actions"] = selected_actions
                
                # Normalize discarded_actions: map IDs back to full action objects if needed
                discarded_actions = result.get("discarded_actions", [])
                discarded_actions = self._normalize_discarded_actions(discarded_actions, all_input_actions)
                discarded_actions = self._validate_action_fields(discarded_actions, "discarded")
                result["discarded_actions"] = discarded_actions
                
                if "selection_summary" not in result:
                    # Count selected actions by type for summary
                    selected_complete_count = sum(1 for a in selected_actions if not a.get('actor_flagged') and not a.get('timing_flagged'))
                    selected_flagged_count = len(selected_actions) - selected_complete_count
                    
                    result["selection_summary"] = {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "selected_complete": selected_complete_count,
                        "selected_flagged": selected_flagged_count,
                        "discarded_complete": len(complete_actions) - selected_complete_count,
                        "discarded_flagged": len(flagged_actions) - selected_flagged_count,
                        "average_relevance_score": 0.0
                    }
                
                if "discarded_actions" not in result:
                    result["discarded_actions"] = []
                
                logger.info(f"Selection successful: {len(selected_actions)} unified actions")
                return result
            else:
                logger.warning(f"Unexpected LLM response format: {type(result)}")
                # Return original actions unchanged (unified format)
                return {
                    "selected_actions": complete_actions + flagged_actions,
                    "selection_summary": {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "selected_complete": len(complete_actions),
                        "selected_flagged": len(flagged_actions),
                        "discarded_complete": 0,
                        "discarded_flagged": 0,
                        "average_relevance_score": 0.0
                    },
                    "discarded_actions": []
                }
                
        except Exception as e:
            logger.error(f"Error in LLM selection: {e}", exc_info=True)
            # Return original actions unchanged on error (unified format)
            return {
                "selected_actions": complete_actions + flagged_actions,
                "selection_summary": {
                    "total_input_complete": len(complete_actions),
                    "total_input_flagged": len(flagged_actions),
                    "selected_complete": len(complete_actions),
                    "selected_flagged": len(flagged_actions),
                    "discarded_complete": 0,
                    "discarded_flagged": 0,
                    "average_relevance_score": 0.0,
                    "error": str(e)
                },
                "discarded_actions": []
            }
    
    def _normalize_selected_actions(
        self,
        selected_actions: List[Dict[str, Any]],
        all_input_actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize selected actions by mapping IDs back to full action objects if LLM returned only IDs.
        
        Args:
            selected_actions: Actions returned by LLM (may be incomplete)
            all_input_actions: Complete list of input actions to map from
            
        Returns:
            Normalized list of complete action objects
        """
        if not selected_actions:
            return []
        
        # Create lookup maps for different ID types
        id_map = {}  # UUID/id -> action
        action_id_map = {}  # numeric index -> action
        action_text_map = {}  # action text -> action
        
        for idx, action in enumerate(all_input_actions):
            # Map by UUID/id
            action_id = action.get("id")
            if action_id:
                id_map[action_id] = action
            
            # Map by numeric index (position in list)
            action_id_map[idx] = action
            
            # Map by action text (for fallback matching)
            action_text = action.get("action", "")
            if action_text:
                action_text_map[action_text] = action
        
        normalized = []
        for llm_action in selected_actions:
            # Check if this is already a complete action object
            if "action" in llm_action and "id" in llm_action:
                # Already complete, but ensure all fields are preserved
                # Try to find original and merge to preserve all fields
                original_id = llm_action.get("id")
                original_action = id_map.get(original_id) if original_id else None
                
                if original_action:
                    # Merge: start with original, update with LLM additions (relevance_score, rationale)
                    normalized_action = dict(original_action)
                    normalized_action.update({
                        k: v for k, v in llm_action.items() 
                        if k in ["relevance_score", "relevance_rationale", "rationale"]
                    })
                    # Preserve LLM's relevance_score and rationale
                    if "relevance_score" in llm_action:
                        normalized_action["relevance_score"] = llm_action["relevance_score"]
                    if "relevance_rationale" in llm_action:
                        normalized_action["relevance_rationale"] = llm_action["relevance_rationale"]
                    elif "rationale" in llm_action:
                        normalized_action["relevance_rationale"] = llm_action["rationale"]
                    normalized.append(normalized_action)
                else:
                    # Complete but ID not found, use as-is
                    normalized.append(llm_action)
            
            # Check if LLM returned only action_id (numeric)
            elif "action_id" in llm_action:
                action_id = llm_action.get("action_id")
                if isinstance(action_id, int) and action_id in action_id_map:
                    original_action = action_id_map[action_id]
                    normalized_action = dict(original_action)
                    normalized_action["relevance_score"] = llm_action.get("relevance_score", 0.0)
                    normalized_action["relevance_rationale"] = llm_action.get("rationale", llm_action.get("relevance_rationale", ""))
                    normalized.append(normalized_action)
                    logger.warning(f"Mapped numeric action_id {action_id} back to full action object")
                else:
                    logger.warning(f"Could not map action_id {action_id} to original action, skipping")
            
            # Check if LLM returned only id (UUID)
            elif "id" in llm_action and "action" not in llm_action:
                action_id = llm_action.get("id")
                if action_id in id_map:
                    original_action = id_map[action_id]
                    normalized_action = dict(original_action)
                    normalized_action["relevance_score"] = llm_action.get("relevance_score", 0.0)
                    normalized_action["relevance_rationale"] = llm_action.get("rationale", llm_action.get("relevance_rationale", ""))
                    normalized.append(normalized_action)
                    logger.warning(f"Mapped UUID id {action_id} back to full action object")
                else:
                    logger.warning(f"Could not map id {action_id} to original action, skipping")
            
            # Check if LLM returned action text but missing other fields
            elif "action" in llm_action and "id" not in llm_action:
                action_text = llm_action.get("action", "")
                if action_text in action_text_map:
                    original_action = action_text_map[action_text]
                    normalized_action = dict(original_action)
                    normalized_action["relevance_score"] = llm_action.get("relevance_score", 0.0)
                    normalized_action["relevance_rationale"] = llm_action.get("rationale", llm_action.get("relevance_rationale", ""))
                    # Update with any LLM-provided fields
                    normalized_action.update({
                        k: v for k, v in llm_action.items() 
                        if k not in ["action"]  # Don't overwrite action text
                    })
                    normalized.append(normalized_action)
                    logger.warning(f"Mapped action text back to full action object")
                else:
                    # Action text not found, use as-is but log warning
                    logger.warning(f"Could not find original action for text: {action_text[:50]}...")
                    normalized.append(llm_action)
            
            else:
                # Unknown format, log and skip
                logger.warning(f"Unknown action format in LLM response: {list(llm_action.keys())}")
                logger.debug(f"Action content: {llm_action}")
        
        return normalized
    
    def _normalize_discarded_actions(
        self,
        discarded_actions: List[Dict[str, Any]],
        all_input_actions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize discarded actions by mapping IDs back to full action objects if LLM returned only IDs.
        
        Args:
            discarded_actions: Discarded actions returned by LLM (may be incomplete)
            all_input_actions: Complete list of input actions to map from
            
        Returns:
            Normalized list of discarded action objects with discard_reason
        """
        if not discarded_actions:
            return []
        
        # Create lookup maps
        id_map = {}
        action_id_map = {}
        action_text_map = {}
        
        for idx, action in enumerate(all_input_actions):
            action_id = action.get("id")
            if action_id:
                id_map[action_id] = action
            action_id_map[idx] = action
            action_text = action.get("action", "")
            if action_text:
                action_text_map[action_text] = action
        
        normalized = []
        for llm_discarded in discarded_actions:
            discard_reason = llm_discarded.get("discard_reason", llm_discarded.get("reason", ""))
            
            # Already has action field
            if "action" in llm_discarded:
                normalized_discarded = dict(llm_discarded)
                if "discard_reason" not in normalized_discarded and "reason" in normalized_discarded:
                    normalized_discarded["discard_reason"] = normalized_discarded.pop("reason")
                normalized.append(normalized_discarded)
            
            # Has action_id (numeric)
            elif "action_id" in llm_discarded:
                action_id = llm_discarded.get("action_id")
                if isinstance(action_id, int) and action_id in action_id_map:
                    original_action = action_id_map[action_id]
                    normalized_discarded = dict(original_action)
                    normalized_discarded["discard_reason"] = discard_reason
                    normalized.append(normalized_discarded)
                    logger.warning(f"Mapped numeric action_id {action_id} back to full discarded action")
            
            # Has only id (UUID)
            elif "id" in llm_discarded:
                action_id = llm_discarded.get("id")
                if action_id in id_map:
                    original_action = id_map[action_id]
                    normalized_discarded = dict(original_action)
                    normalized_discarded["discard_reason"] = discard_reason
                    normalized.append(normalized_discarded)
                    logger.warning(f"Mapped UUID id {action_id} back to full discarded action")
            
            else:
                logger.warning(f"Unknown discarded action format: {list(llm_discarded.keys())}")
        
        return normalized
    
    def _validate_action_fields(
        self,
        actions: List[Dict[str, Any]],
        action_type: str
    ) -> List[Dict[str, Any]]:
        """
        Validate that actions have required fields and log warnings for missing fields.
        
        Args:
            actions: List of actions to validate
            action_type: "selected" or "discarded" for logging context
            
        Returns:
            Validated list of actions (invalid ones are logged but kept)
        """
        required_fields_selected = ["id", "action"]
        required_fields_discarded = ["id", "action", "discard_reason"]
        
        required_fields = required_fields_discarded if action_type == "discarded" else required_fields_selected
        validated = []
        
        for idx, action in enumerate(actions):
            missing_fields = [field for field in required_fields if field not in action or not action.get(field)]
            
            if missing_fields:
                logger.warning(
                    f"{action_type.capitalize()} action at index {idx} missing required fields: {missing_fields}. "
                    f"Action keys: {list(action.keys())}"
                )
                # Try to fill in missing fields if possible
                if "id" not in action or not action.get("id"):
                    logger.debug(f"Action {idx} has no id, cannot recover")
                if "action" not in action or not action.get("action"):
                    logger.debug(f"Action {idx} has no action text, cannot recover")
                if action_type == "discarded" and ("discard_reason" not in action or not action.get("discard_reason")):
                    action["discard_reason"] = "No reason provided"
            
            validated.append(action)
        
        return validated
    
    def _log_selection_details(
        self,
        selected_complete: List[Dict[str, Any]],
        selected_flagged: List[Dict[str, Any]],
        discarded_actions: List[Dict[str, Any]],
        selection_summary: Dict[str, Any]
    ):
        """
        Log detailed selection information to markdown logger.
        
        Args:
            selected_complete: Selected complete actions
            selected_flagged: Selected flagged actions
            discarded_actions: Discarded actions with reasons
            selection_summary: Selection statistics
        """
        if not self.markdown_logger:
            return
        
        # Log selection statistics
        self.markdown_logger.add_text("### Selection Statistics", bold=True)
        self.markdown_logger.add_text("")
        self.markdown_logger.add_list_item(f"Input Complete Actions: {selection_summary.get('total_input_complete', 0)}")
        self.markdown_logger.add_list_item(f"Input Flagged Actions: {selection_summary.get('total_input_flagged', 0)}")
        self.markdown_logger.add_list_item(f"Selected Complete Actions: {selection_summary.get('selected_complete', 0)}")
        self.markdown_logger.add_list_item(f"Selected Flagged Actions: {selection_summary.get('selected_flagged', 0)}")
        self.markdown_logger.add_list_item(f"Discarded Complete Actions: {selection_summary.get('discarded_complete', 0)}")
        self.markdown_logger.add_list_item(f"Discarded Flagged Actions: {selection_summary.get('discarded_flagged', 0)}")
        self.markdown_logger.add_list_item(f"Average Relevance Score: {selection_summary.get('average_relevance_score', 0.0):.2f}")
        self.markdown_logger.add_text("")
        
        # Log selected complete actions with relevance scores
        if selected_complete:
            self.markdown_logger.add_text("### Selected Complete Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(selected_complete, 1):
                relevance_score = action.get("relevance_score", 0.0)
                relevance_rationale = action.get("relevance_rationale", "N/A")
                self.markdown_logger.add_text(f"**Action {idx} (Relevance: {relevance_score:.2f}):**")
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"WHO: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"WHEN: {action.get('when', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Rationale: {relevance_rationale}", level=1)
                self.markdown_logger.add_text("")
        
        # Log selected flagged actions
        if selected_flagged:
            self.markdown_logger.add_text("### Selected Flagged Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(selected_flagged, 1):
                relevance_score = action.get("relevance_score", 0.0)
                relevance_rationale = action.get("relevance_rationale", "N/A")
                self.markdown_logger.add_text(f"**Flagged Action {idx} (Relevance: {relevance_score:.2f}):**")
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Missing Fields: {', '.join(action.get('missing_fields', []))}", level=1)
                self.markdown_logger.add_list_item(f"Rationale: {relevance_rationale}", level=1)
                self.markdown_logger.add_text("")
        
        # Log discarded actions with reasons
        if discarded_actions:
            self.markdown_logger.add_text("### Discarded Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(discarded_actions, 1):
                discard_reason = action.get("discard_reason", "N/A")
                self.markdown_logger.add_text(f"**Discarded {idx}:**")
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Reason: {discard_reason}", level=1)
                self.markdown_logger.add_text("")

    def _filter_tables(
        self,
        tables: List[Dict[str, Any]],
        problem_statement: str,
        user_config: Dict[str, Any],
        selected_actions: List[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter tables using LLM-based relevance scoring against problem statement.
        
        Tables pass filter if:
        - Relevance score >= threshold (7/10)
        
        Args:
            tables: List of table objects to filter
            problem_statement: Problem/objective statement for relevance scoring
            user_config: User configuration
            selected_actions: List of selected actions (for context in scoring)
            
        Returns:
            Tuple of (selected_tables, discarded_tables)
        """
        if not tables:
            return [], []
        
        logger.info(f"Filtering {len(tables)} tables using relevance scoring...")
        
        selected_tables = []
        discarded_tables = []
        
        RELEVANCE_THRESHOLD = 7.0  # Minimum score out of 10
        
        for table in tables:
            # Score table for relevance (with selected actions context)
            relevance_score = self._score_table_relevance(table, problem_statement, user_config, selected_actions)
            table['relevance_score'] = relevance_score
            
            if relevance_score >= RELEVANCE_THRESHOLD:
                table['kept_reason'] = f'relevance_score_{relevance_score:.1f}'
                selected_tables.append(table)
                logger.debug(f"Table '{table.get('table_title', 'Untitled')}' kept (score: {relevance_score:.1f})")
            else:
                table['discard_reason'] = f'low_relevance_score_{relevance_score:.1f}'
                discarded_tables.append(table)
                logger.debug(f"Table '{table.get('table_title', 'Untitled')}' discarded (score: {relevance_score:.1f})")
        
        logger.info(f"Table filtering complete: {len(selected_tables)} selected, {len(discarded_tables)} discarded")
        return selected_tables, discarded_tables

    def _score_table_relevance(
        self,
        table: Dict[str, Any],
        problem_statement: str,
        user_config: Dict[str, Any],
        selected_actions: List[Dict[str, Any]] = None
    ) -> float:
        """
        Score a table's relevance to the problem statement using LLM.
        
        Args:
            table: Table object to score
            problem_statement: Problem/objective statement
            user_config: User configuration
            selected_actions: List of selected actions (for context in scoring)
            
        Returns:
            Relevance score (0-10)
        """
        table_title = table.get('table_title', 'Untitled')
        table_type = table.get('table_type', 'Unknown')
        headers = table.get('headers', [])
        row_count = len(table.get('rows', []))
        markdown_content = table.get('markdown_content', '')
        
        # Build table content for LLM - include full markdown content
        if markdown_content:
            # Include metadata + full table content
            table_summary = f"Title: {table_title}\nType: {table_type}\nHeaders: {', '.join(headers)}\nRow count: {row_count}\n\nTable Content:\n{markdown_content}"
        else:
            # Fallback to summary if markdown_content not available
            table_summary = f"Title: {table_title}\nType: {table_type}\nHeaders: {', '.join(headers)}\nRow count: {row_count}"
        
        prompt = get_selector_table_scoring_prompt(problem_statement, user_config, table_summary, selected_actions)
        
        try:
            result = self.llm.generate(
                prompt=prompt,
                system_prompt=None,
                temperature=0.3
            )
            
            # Extract number from result
            match = re.search(r'\d+\.?\d*', result)
            if match:
                score = float(match.group())
                return min(10.0, max(0.0, score))  # Clamp between 0-10
            else:
                logger.warning(f"Could not parse relevance score from LLM response: {result}")
                return 5.0  # Default to neutral score
                
        except Exception as e:
            logger.error(f"Error scoring table relevance: {e}")
            return 5.0  # Default to neutral score on error

