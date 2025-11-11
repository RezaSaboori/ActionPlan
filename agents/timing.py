"""Timing Agent for adding triggers and timelines to actions."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class TimingAgent:
    """Timing agent for adding triggers and timelines to actions."""
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        markdown_logger=None
    ):
        """
        Initialize Timing Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.system_prompt = get_prompt("timing")
        logger.info(f"Initialized TimingAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute timing assignment logic.
        
        Enhanced to preserve references and handle formulas/tables.
        
        Args:
            data: Dictionary containing:
                - actions: List of actions to process
                - problem_statement: Problem/objective statement
                - user_config: User configuration
                - formulas: List of formula objects (optional, passed through)
                - tables: List of table objects (optional, passed through)
            
        Returns:
            Dictionary with:
                - timed_actions: Actions updated with timing information (references preserved)
                - formulas: Pass-through formulas
                - tables: Pass-through tables
        """
        actions = data.get("actions", [])
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        formulas = data.get("formulas", [])
        tables = data.get("tables", [])
        
        logger.info(f"Timing Agent processing {len(actions)} actions")
        logger.info(f"                         {len(formulas)} formulas, {len(tables)} tables (pass-through)")
        
        if not actions:
            logger.warning("No actions to process for timing")
            return {
                "timed_actions": [],
                "formulas": formulas,
                "tables": tables
            }
        
        # Filter actions that need timing info
        actions_to_process = [
            action for action in actions 
            if not action.get("estimated_time") or not action.get("trigger")
        ]
        
        if not actions_to_process:
            logger.info("No actions require timing updates")
            return {
                "timed_actions": actions,
                "formulas": formulas,
                "tables": tables
            }
            
        logger.info(f"Found {len(actions_to_process)} actions requiring timing information")

        # Get timing assignments from LLM
        timed_actions = self._get_timing_assignments(
            actions_to_process, 
            problem_statement,
            user_config
        )
        
        # Merge updated actions back into the original list
        # Create a mapping based on action description since actions may not have IDs
        action_map = {action.get("action", ""): action for action in timed_actions}
        final_actions = []
        for action in actions:
            action_key = action.get("action", "")
            if action_key in action_map:
                final_actions.append(action_map[action_key])
            else:
                # If not found in timed actions, keep original
                final_actions.append(action)
        
        logger.info(f"Timing Agent completed with {len(final_actions)} actions")
        logger.info(f"                           {len(formulas)} formulas, {len(tables)} tables")
        return {
            "timed_actions": final_actions,
            "formulas": formulas,
            "tables": tables
        }

    def _get_timing_assignments(
        self,
        actions: List[Dict[str, Any]],
        problem_statement: str,
        user_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get timing and triggers for actions using LLM."""
        
        actions_text = json.dumps(actions, indent=2)
        config_text = json.dumps(user_config, indent=2)
        
        prompt = f"""You are an expert in operational planning for health emergencies.
Your task is to assign a trigger and an estimated time for a list of actions that are missing this information.

## Context
**Problem Statement:**
{problem_statement}

**User Configuration:**
{config_text}

## Actions to Process
{actions_text}

## Your Task
For each action in the list, provide:
1.  **trigger**: The specific event or condition that should initiate the action.
    - Examples: "Upon notification of a mass casualty event", "When patient count exceeds 20", "After initial triage is complete".
2.  **estimated_time**: A realistic timeframe for completing the action once triggered.
    - Examples: "Within 15 minutes", "1-2 hours", "Before patient arrival".

## Output Format
Return a JSON object with a single key "timed_actions" containing the list of updated actions. 
Each action in the list should be a complete JSON object, including all original fields plus the new `trigger` and `estimated_time` fields.
Ensure the output is valid JSON.

Example:
{{
  "timed_actions": [
    {{
      "action": "Activate the hospital's emergency communication plan",
      "who": "Communications Officer",
      ... // other fields
      "trigger": "Immediately upon declaration of a Code Orange",
      "estimated_time": "Within 10 minutes"
    }}
  ]
}}
"""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.4
            )
            
            if isinstance(result, dict) and "timed_actions" in result:
                return result["timed_actions"]
            else:
                logger.warning(f"Unexpected timing result format: {result}")
                return actions # Return original actions on failure

        except Exception as e:
            logger.error(f"Error getting timing assignments: {e}")
            return actions # Return original actions on failure

