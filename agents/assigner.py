"""Assigner Agent for role and responsibility assignment."""

import logging
import json
import os
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from config.prompts import get_prompt
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
        
        Args:
            data: Dictionary containing prioritized actions and user_config
            
        Returns:
            Dictionary with assigned actions
        """
        prioritized_actions = data.get("prioritized_actions", [])
        user_config = data.get("user_config", {})
        
        logger.info(f"Assigner processing {len(prioritized_actions)} actions")
        logger.info(f"User config: level={user_config.get('level')}, phase={user_config.get('phase')}, subject={user_config.get('subject')}")
        
        if not prioritized_actions:
            logger.warning("No actions to assign")
            return {"assigned_actions": []}
        
        # Check if batch processing is needed
        batch_threshold = self.settings.assigner_batch_threshold
        batch_size = self.settings.assigner_batch_size
        
        if len(prioritized_actions) > batch_threshold:
            logger.info(f"Using batch processing: {len(prioritized_actions)} actions, batch_size={batch_size}")
            assigned = self._assign_responsibilities_batched(prioritized_actions, user_config, batch_size)
        else:
            logger.info("Processing all actions in single batch")
            assigned = self._assign_responsibilities(prioritized_actions, user_config)
        
        logger.info(f"Assigner completed with {len(assigned)} assigned actions")
        return {"assigned_actions": assigned}
    
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
            
            try:
                batch_assigned = self._assign_responsibilities(batch, user_config)
                all_assigned.extend(batch_assigned)
                logger.info(f"Batch {batch_num} completed successfully")
            except Exception as e:
                logger.error(f"Error in batch {batch_num}: {e}")
                # Apply default assignments for failed batch
                batch_assigned = self._apply_default_assignments(batch, user_config)
                all_assigned.extend(batch_assigned)
        
        return all_assigned
    
    def _assign_responsibilities(
        self,
        actions: List[Dict[str, Any]],
        user_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Assign responsibilities using LLM with reference document."""
        actions_text = json.dumps(actions, indent=2, ensure_ascii=False)
        
        # Extract key config parameters
        org_level = user_config.get('level', 'center')
        phase = user_config.get('phase', 'response')
        subject = user_config.get('subject', 'emergency')
        
        prompt = f"""You are assigning roles and responsibilities for actions in the Iranian health system.

## Context

**Organizational Level**: {org_level}
**Phase**: {phase}
**Subject**: {subject}

## Actions to Assign

{actions_text}

## Ministry of Health Organizational Structure Reference

{self.reference_doc}

## Instructions

1. For each action, assign a SPECIFIC job position from the reference document above
2. Consider the organizational level ({org_level}) when selecting positions:
   - "ministry" level → Use Ministry-level positions
   - "university" level → Use University-level positions
   - "center" level → Use Hospital/Center-level positions
3. Use EXACT terminology from the reference document
4. Identify specific collaborators (not departments or general teams)
5. Preserve all original action metadata
6. If an action already has a "who" field, correct it to match the reference document

Provide your response as valid JSON following the output format specified in your system prompt."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.1
            )
            
            if isinstance(result, dict) and "assigned_actions" in result:
                return result["assigned_actions"]
            elif isinstance(result, list):
                return result
            else:
                logger.warning("Unexpected assignment result format")
                return self._apply_default_assignments(actions, user_config)
        
        except Exception as e:
            logger.error(f"Error assigning responsibilities: {e}")
            return self._apply_default_assignments(actions, user_config)
    
    def _apply_default_assignments(
        self,
        actions: List[Dict[str, Any]],
        user_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply default role assignments based on organizational level."""
        assigned = []
        org_level = user_config.get('level', 'center')
        
        for action in actions:
            priority = action.get("priority_level", "short-term")
            category = action.get("category", "response")
            action_text = action.get("action", "").lower()
            
            # Default assignments based on level and action keywords
            if org_level == "ministry":
                if "policy" in action_text or "national" in action_text:
                    who = "Deputy Minister of Health"
                elif "emergency" in action_text or "disaster" in action_text:
                    who = "Center for Emergency and Disaster Management"
                else:
                    who = "General Directorate of Health Affairs"
            elif org_level == "university":
                if "education" in action_text or "training" in action_text:
                    who = "Vice-Chancellor for Education"
                elif "research" in action_text:
                    who = "Vice-Chancellor for Research"
                else:
                    who = "Vice-Chancellor for Health"
            else:  # center level
                if "triage" in action_text:
                    who = "Head of Emergency Department"
                elif "nursing" in action_text or "patient care" in action_text:
                    who = "Matron/Director of Nursing Services"
                elif "technical" in action_text or "medical" in action_text:
                    who = "Hospital Technical Officer"
                else:
                    who = "Hospital Manager/Director"
            
            assigned.append({
                **action,
                "who": who,
                "when": action.get("when", f"During {priority} phase"),
                "collaborators": ["Relevant department staff"],
                "resources_needed": action.get("resources_needed", ["Standard resources"]),
                "verification": action.get("verification", "Documentation and reporting"),
                "organizational_level": org_level,
                "shift_type": "as-needed"
            })
        
        return assigned

