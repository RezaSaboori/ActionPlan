"""Selector Agent for filtering actions based on relevance."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)

# Define a batch size for processing actions to avoid overloading the LLM
ACTION_BATCH_SIZE = 15


class SelectorAgent:
    """
    Selector Agent for filtering actions based on semantic relevance.
    
    Workflow:
    - Receives problem_statement, user_config, complete_actions, and flagged_actions
    - Uses LLM to semantically analyze each action against problem statement and user config
    - Filters both complete and flagged actions based on relevance
    - Discards irrelevant actions completely
    - Returns only relevant actions with relevance scores and rationale
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
        
        Args:
            data: Dictionary containing:
                - problem_statement: The refined problem/objective from Orchestrator
                - user_config: User configuration (name, timing, level, phase, subject)
                - complete_actions: List of actions with who/when defined
                - flagged_actions: List of actions missing who/when
                
        Returns:
            Dictionary with:
                - selected_complete_actions: Filtered complete actions
                - selected_flagged_actions: Filtered flagged actions
                - selection_summary: Statistics about filtering
                - discarded_actions: Actions that were filtered out with reasons
        """
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        complete_actions = data.get("complete_actions", [])
        flagged_actions = data.get("flagged_actions", [])
        
        logger.info(f"=" * 80)
        logger.info(f"SELECTOR AGENT STARTING")
        logger.info(f"Input: {len(complete_actions)} complete actions, {len(flagged_actions)} flagged actions")
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
                    "total_actions": len(complete_actions) + len(flagged_actions)
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
                    self.markdown_logger.add_list_item(f"WHAT: {action.get('what', 'N/A')}", level=1)
                    self.markdown_logger.add_text("")
            
            if flagged_actions:
                self.markdown_logger.add_text("### Input Flagged Actions (All)", bold=True)
                self.markdown_logger.add_text("")
                for idx, action in enumerate(flagged_actions, 1):
                    self.markdown_logger.add_text(f"**{idx}. {action.get('action', 'N/A')}**")
                    self.markdown_logger.add_list_item(f"Missing: {', '.join(action.get('missing_fields', []))}", level=1)
                    self.markdown_logger.add_text("")
        
        # If no actions, return empty
        if not complete_actions and not flagged_actions:
            logger.warning("No actions provided for selection")
            return {
                "selected_complete_actions": [],
                "selected_flagged_actions": [],
                "selection_summary": {
                    "total_input_complete": 0,
                    "total_input_flagged": 0,
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
        
        # Create final selection summary
        final_summary = {
            "total_input_complete": len(complete_actions),
            "total_input_flagged": len(flagged_actions),
            "selected_complete": len(final_selected_complete),
            "selected_flagged": len(final_selected_flagged),
            "discarded_complete": len(complete_actions) - len(final_selected_complete),
            "discarded_flagged": len(flagged_actions) - len(final_selected_flagged),
        }
        
        # Calculate average relevance score if available
        all_selected = final_selected_complete + final_selected_flagged
        if all_selected:
            total_score = sum(a.get("relevance_score", 0.0) for a in all_selected)
            final_summary["average_relevance_score"] = total_score / len(all_selected)
        else:
            final_summary["average_relevance_score"] = 0.0

        logger.info(f"=" * 80)
        logger.info(f"SELECTOR AGENT COMPLETED")
        logger.info(f"Output: {len(final_selected_complete)} complete actions, {len(final_selected_flagged)} flagged actions")
        logger.info(f"Discarded: {final_summary.get('discarded_complete', 0)} complete, {final_summary.get('discarded_flagged', 0)} flagged")
        logger.info(f"Average Relevance Score: {final_summary.get('average_relevance_score', 0.0):.2f}")
        logger.info(f"=" * 80)
        
        # Log output details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "Selector Output Summary",
                {
                    "selected_complete_actions_count": len(final_selected_complete),
                    "selected_flagged_actions_count": len(final_selected_flagged),
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
        
        return {
            "selected_complete_actions": final_selected_complete,
            "selected_flagged_actions": final_selected_flagged,
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
                all_selected.extend(result.get("selected_complete_actions", []))
                all_discarded.extend(result.get("discarded_actions", []))
            else:
                result = self._llm_select(problem_statement, user_config, [], batch)
                all_selected.extend(result.get("selected_flagged_actions", []))
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
        
        # Prepare input for LLM
        prompt = f"""You are given a problem statement, user configuration, and lists of actions.

**Problem Statement:**
{problem_statement}

**User Configuration:**
- Name/Subject: {user_config.get('name', 'N/A')}
- Timing: {user_config.get('timing', 'N/A')}
- Level: {user_config.get('level', 'N/A')}
- Phase: {user_config.get('phase', 'N/A')}
- Crisis Subject: {user_config.get('subject', 'N/A')}
"""
        if complete_actions:
            prompt += f"""
**COMPLETE ACTIONS ({len(complete_actions)} actions):**
{json.dumps(complete_actions, indent=2, ensure_ascii=False)}
"""
        if flagged_actions:
            prompt += f"""
**FLAGGED ACTIONS ({len(flagged_actions)} actions):**
{json.dumps(flagged_actions, indent=2, ensure_ascii=False)}
"""
        prompt += """
Your task is to:
1. Analyze each action for semantic relevance to the problem statement and user configuration
2. Select only actions that are directly relevant
3. Discard actions that are tangentially related or irrelevant
4. Provide relevance scores and rationale for selected actions
5. List discarded actions with reasons

Return a JSON object with the structure defined in your system prompt."""
        
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
                # Validate response structure
                if "selected_complete_actions" not in result:
                    result["selected_complete_actions"] = complete_actions
                    logger.warning("LLM didn't return selected_complete_actions, using all original")
                
                if "selected_flagged_actions" not in result:
                    result["selected_flagged_actions"] = flagged_actions
                    logger.warning("LLM didn't return selected_flagged_actions, using all original")
                
                if "selection_summary" not in result:
                    result["selection_summary"] = {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "selected_complete": len(result.get("selected_complete_actions", [])),
                        "selected_flagged": len(result.get("selected_flagged_actions", [])),
                        "discarded_complete": len(complete_actions) - len(result.get("selected_complete_actions", [])),
                        "discarded_flagged": len(flagged_actions) - len(result.get("selected_flagged_actions", [])),
                        "average_relevance_score": 0.0
                    }
                
                if "discarded_actions" not in result:
                    result["discarded_actions"] = []
                
                logger.info(f"Selection successful: {len(result['selected_complete_actions'])} complete, {len(result['selected_flagged_actions'])} flagged")
                return result
            else:
                logger.warning(f"Unexpected LLM response format: {type(result)}")
                # Return original actions unchanged
                return {
                    "selected_complete_actions": complete_actions,
                    "selected_flagged_actions": flagged_actions,
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
            # Return original actions unchanged on error
            return {
                "selected_complete_actions": complete_actions,
                "selected_flagged_actions": flagged_actions,
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
                self.markdown_logger.add_list_item(f"WHAT: {action.get('what', 'N/A')}", level=1)
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

