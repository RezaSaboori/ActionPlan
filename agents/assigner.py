"""Assigner Agent for role and responsibility assignment."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import OllamaClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class AssignerAgent:
    """Assigner agent for assigning responsibilities and verifying timings."""
    
    def __init__(
        self,
        llm_client: OllamaClient,
        protocols_rag: HybridRAG,
        markdown_logger=None
    ):
        """
        Initialize Assigner Agent.
        
        Args:
            llm_client: Ollama client instance
            protocols_rag: HybridRAG for protocol references
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.protocols_rag = protocols_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.retrieval_mode = self.settings.assigner_retrieval_mode
        self.system_prompt = get_prompt("assigner")
        logger.info(f"Initialized AssignerAgent with retrieval mode: {self.retrieval_mode}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute assigner logic.
        
        Args:
            data: Dictionary containing prioritized actions
            
        Returns:
            Dictionary with assigned actions
        """
        prioritized_actions = data.get("prioritized_actions", [])
        logger.info(f"Assigner processing {len(prioritized_actions)} actions")
        
        if not prioritized_actions:
            logger.warning("No actions to assign")
            return {"assigned_actions": []}
        
        # Get role assignment context
        role_context = self._get_role_context()
        
        # Assign responsibilities
        assigned = self._assign_responsibilities(prioritized_actions, role_context)
        
        logger.info(f"Assigner completed with {len(assigned)} assigned actions")
        return {"assigned_actions": assigned}
    
    def _get_role_context(self) -> str:
        """Get role assignment guidelines from protocols using summary mode."""
        query = "responsible unit duties roles responsibilities commander officer team structure"
        
        try:
            # Use summary mode for faster retrieval of role information
            results = self.protocols_rag.query(
                query_text=query,
                strategy=self.retrieval_mode,
                top_k=5
            )
            
            context_parts = []
            for result in results:
                title = result.get('title', '')
                text = result.get('text', '')
                if title or text:
                    context_parts.append(f"{title}: {text[:200]}")
            
            return "\n".join(context_parts) if context_parts else "Standard health system roles: EOC, Incident Commander, Medical Staff, Support Teams"
        
        except Exception as e:
            logger.error(f"Error getting role context: {e}")
            return "Standard health system roles: EOC, Incident Commander, Medical Staff, Support Teams"
    
    def _assign_responsibilities(
        self,
        actions: List[Dict[str, Any]],
        role_context: str
    ) -> List[Dict[str, Any]]:
        """Assign responsibilities using LLM."""
        actions_text = json.dumps(actions, indent=2)
        
        prompt = f"""Assign specific roles and responsibilities for each action based on health system protocols.

Actions to assign:
{actions_text}

Role Assignment Context:
{role_context}

For each action, assign:
1. who: Specific role or unit responsible (e.g., "Triage Officer", "Emergency Operations Center")
2. when: Precise timing based on priority level
3. collaborators: Supporting roles/units
4. resources_needed: Key resources required
5. verification: How to verify completion

Standard Health System Roles:
- Emergency Operations Center (EOC): Overall coordination
- Incident Commander: On-scene command
- Triage Officer: Patient prioritization
- Medical Director: Clinical decisions
- Support Teams: Logistics, supplies, communications
- Specialized Units: Disease control, environmental health

Provide JSON output:
{{
  "assigned_actions": [
    {{
      "action": "Action description",
      "who": "Responsible role/unit",
      "when": "Specific timing",
      "collaborators": ["Supporting roles"],
      "resources_needed": ["Required resources"],
      "verification": "Completion verification method",
      "priority_level": "immediate|short-term|long-term",
      "sources": ["Source citations"]
    }}
  ]
}}

Cross-reference protocol sources for role assignments. Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3
            )
            
            if isinstance(result, dict) and "assigned_actions" in result:
                return result["assigned_actions"]
            elif isinstance(result, list):
                return result
            else:
                logger.warning("Unexpected assignment result")
                return self._apply_default_assignments(actions)
        
        except Exception as e:
            logger.error(f"Error assigning responsibilities: {e}")
            return self._apply_default_assignments(actions)
    
    def _apply_default_assignments(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply default role assignments."""
        assigned = []
        
        for action in actions:
            priority = action.get("priority_level", "short-term")
            category = action.get("category", "response")
            
            # Simple default logic
            if category == "preparedness":
                who = "Emergency Operations Center"
            elif "triage" in action.get("action", "").lower():
                who = "Triage Officer"
            elif "command" in action.get("action", "").lower():
                who = "Incident Commander"
            else:
                who = "Health System Personnel"
            
            assigned.append({
                **action,
                "who": who,
                "when": f"During {priority} phase",
                "collaborators": ["Support Teams"],
                "resources_needed": ["Standard emergency equipment"],
                "verification": "Documentation and reporting"
            })
        
        return assigned

