"""Assigner Agent for role and responsibility assignment."""

import logging
import json
import os
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt, get_assigner_user_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class AssignerAgent:
    """Assigner agent for assigning responsibilities using organizational structure reference."""
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        markdown_logger=None
    ):
        """
        Initialize Assigner Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.system_prompt = get_prompt("assigner")
        
        # Load reference document
        self.reference_doc = self._load_reference_document()
        
        logger.info(f"Initialized AssignerAgent with agent_name='{agent_name}', model={self.llm.model}")
        logger.info(f"Reference document loaded: {len(self.reference_doc)} characters")
    
    def _load_reference_document(self) -> str:
        """Load the organizational structure reference document."""
        ref_path = self.settings.assigner_reference_doc
        
        # Try multiple path resolutions
        possible_paths = [
            ref_path,  # As configured
            os.path.join(os.getcwd(), ref_path),  # Relative to current directory
            os.path.join(os.path.dirname(__file__), '..', ref_path),  # Relative to agents directory
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    logger.info(f"Successfully loaded reference document from: {path}")
                    return content
                except Exception as e:
                    logger.error(f"Error reading reference document from {path}: {e}")
        
        # Fallback error message
        error_msg = f"Reference document not found. Tried paths: {', '.join(possible_paths)}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute assigner logic.
        
        This agent's sole responsibility is to assign the 'who' field.
        All other fields are passed through untouched.
        
        Args:
            data: Dictionary containing:
                - prioritized_actions: List of actions to assign
                - user_config: User configuration
                - tables: List of table objects (optional, passed through)
            
        Returns:
            Dictionary with:
                - assigned_actions: Actions with 'who' field assigned
                - tables: Pass-through tables
        """
        prioritized_actions = data.get("prioritized_actions", [])
        user_config = data.get("user_config", {})
        tables = data.get("tables", [])
        
        logger.info(f"Assigner Agent processing {len(prioritized_actions)} actions")
        logger.info(f"                            {len(tables)} tables (pass-through)")

        if not prioritized_actions:
            logger.warning("No actions to process for assignment")
            return {
                "assigned_actions": [],
                "tables": tables
            }
        
        # Check if batch processing is needed
        batch_threshold = self.settings.assigner_batch_threshold
        batch_size = self.settings.assigner_batch_size
        
        if len(prioritized_actions) > batch_threshold:
            logger.info(f"Using batch processing: {len(prioritized_actions)} actions, batch_size={batch_size}")
            assigned = self._assign_responsibilities_batched(prioritized_actions, user_config, batch_size)
        else:
            logger.info("Processing all actions in single batch")
            assigned = self._assign_responsibilities(prioritized_actions, user_config)
        
        logger.info(f"Assigner Agent completed with {len(assigned)} actions")
        logger.info(f"                             {len(tables)} tables")
        
        return {
            "assigned_actions": assigned,
            "tables": tables
        }
    
    def _assign_responsibilities_batched(
        self,
        actions: List[Dict[str, Any]],
        user_config: Dict[str, Any],
        batch_size: int
    ) -> List[Dict[str, Any]]:
        """Process actions in batches."""
        all_assigned = []
        total_batches = (len(actions) + batch_size - 1) // batch_size
        
        for i in range(0, len(actions), batch_size):
            batch_num = (i // batch_size) + 1
            batch = actions[i:i + batch_size]
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} actions)")
            
            batch_assigned = self._assign_responsibilities(batch, user_config)
            all_assigned.extend(batch_assigned)
            logger.info(f"Batch {batch_num} completed")
        
        return all_assigned
    
    def _assign_responsibilities(
	    self,
	    actions: List[Dict[str, Any]],
	    user_config: Dict[str, Any]
	) -> List[Dict[str, Any]]:
	    """
	    Assigns the 'who' field for a list of actions using an LLM.
	
	    LLM returns all actions with updated 'who' field in format: {"actions": [...]}
	    This method preserves all original action fields, only updating 'who'.
	    On failure it returns the originals with existing 'who' fields.
	    """
	    actions_text = json.dumps(actions, indent=2, ensure_ascii=False)
	
	    # Extract key config parameters
	    org_level = user_config.get('level', 'center')
	
	    prompt = get_assigner_user_prompt(
	        org_level=org_level,
	        phase=user_config.get('phase', ''),
	        subject=user_config.get('subject', ''),
	        actions_text=actions_text,
	        reference_doc=self.reference_doc
	    )
	
	    try:
	        result = self.llm.generate_json(
	            prompt=prompt,
	            system_prompt=self.system_prompt,
	            temperature=0.1
	        )
	
	        # Expect new format: "actions" key containing all actions
	        if not isinstance(result, dict) or "actions" not in result:
	            logger.error("LLM returned unexpected format. Expected 'actions' key, got: %r", list(result.keys()) if isinstance(result, dict) else type(result))
	            return [dict(action, who=action.get('who', '')) for action in actions]
	        
	        assigned_raw = result["actions"]
	        
	        if not isinstance(assigned_raw, list):
	            logger.error("LLM returned non-list for actions: %r", type(assigned_raw))
	            return [dict(action, who=action.get('who', '')) for action in actions]
	
	        # Validate that LLM returned correct number of actions
	        if len(assigned_raw) != len(actions):
	            logger.error(
	                "LLM returned %d actions for %d input actions. Expected same count.",
	                len(assigned_raw), len(actions)
	            )
	            return [dict(action, who=action.get('who', '')) for action in actions]
	
	        # Validate each item is a dict
	        for idx, item in enumerate(assigned_raw):
	            if not isinstance(item, dict):
	                logger.error("LLM returned non-dict at index %d: %r", idx, type(item))
	                return [dict(action, who=action.get('who', '')) for action in actions]
	
	        # Merge LLM-returned actions with originals to preserve all fields
	        # LLM returns all actions with updated 'who' field
	        final_actions: List[Dict[str, Any]] = []
	        for i, original in enumerate(actions):
	            llm_action = assigned_raw[i]
	            
	            # Start with original to preserve all fields
	            merged_action = original.copy() if isinstance(original, dict) else {}
	            
	            # Update with LLM output, ensuring 'who' field is from LLM
	            merged_action.update(llm_action)
	            merged_action['who'] = llm_action.get('who', original.get('who', ''))
	
	            final_actions.append(merged_action)
	
	        return final_actions
	
	    except Exception as e:
	        logger.error("Error in assignment: %s", e)
	        # Return originals with empty WHO on failure
	        return [dict(action, who=action.get('who', '')) for action in actions]