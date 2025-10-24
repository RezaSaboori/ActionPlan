"""Prioritizer Agent for action sequencing and timeline assignment."""

import logging
import json
from typing import Dict, Any, List
from utils.llm_client import LLMClient
from rag_tools.hybrid_rag import HybridRAG
from config.prompts import get_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class PrioritizerAgent:
    """Prioritizer agent for ordering actions by timeline."""
    
    def __init__(
        self,
        llm_client: LLMClient,
        protocols_rag: HybridRAG,
        markdown_logger=None
    ):
        """
        Initialize Prioritizer Agent.
        
        Args:
            llm_client: Ollama client instance
            protocols_rag: HybridRAG for timing references
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.protocols_rag = protocols_rag
        self.markdown_logger = markdown_logger
        self.settings = get_settings()
        self.retrieval_mode = self.settings.prioritizer_retrieval_mode
        self.system_prompt = get_prompt("prioritizer")
        logger.info(f"Initialized PrioritizerAgent with retrieval mode: {self.retrieval_mode}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute prioritizer logic.
        
        Args:
            data: Dictionary containing refined actions and optional timing parameter
            
        Returns:
            Dictionary with prioritized actions
        """
        refined_actions = data.get("refined_actions", [])
        user_timing = data.get("timing")  # User-specified timing context
        logger.info(f"Prioritizer processing {len(refined_actions)} actions")
        
        if not refined_actions:
            logger.warning("No actions to prioritize")
            return {"prioritized_actions": []}
        
        # Get timing context from protocols
        timing_context = self._get_timing_context()
        
        # Prioritize actions
        prioritized = self._prioritize_actions(refined_actions, timing_context)
        
        # Apply user timing modification if provided
        if user_timing:
            prioritized = self._apply_user_timing(prioritized, user_timing)
        
        logger.info(f"Prioritizer completed with {len(prioritized)} prioritized actions")
        return {"prioritized_actions": prioritized}
    
    def _get_timing_context(self) -> str:
        """Get detailed timing guidelines from protocols using content mode."""
        query = "action timeline immediate short-term long-term emergency response timing prioritization sequencing"
        
        try:
            # Use content mode for comprehensive timing information
            results = self.protocols_rag.query(
                query_text=query,
                strategy=self.retrieval_mode,
                top_k=5
            )
            
            context_parts = []
            for result in results:
                text = result.get('text', '')
                if text:
                    context_parts.append(text[:500])
            
            return "\n\n".join(context_parts) if context_parts else "Standard emergency timelines: Immediate (0-24h), Short-term (1-7 days), Long-term (1+ weeks)"
        except Exception as e:
            logger.error(f"Error getting timing context: {e}")
            return "Standard emergency timelines: Immediate (0-24h), Short-term (1-7 days), Long-term (1+ weeks)"
    
    def _prioritize_actions(
        self,
        actions: List[Dict[str, Any]],
        timing_context: str
    ) -> List[Dict[str, Any]]:
        """Prioritize actions using LLM with batching for performance."""
        # Batch processing for large action lists
        batch_size = 15  # Process 15 actions at a time for better performance
        
        if len(actions) <= batch_size:
            # Small enough to process in one go
            return self._prioritize_batch(actions, timing_context)
        
        # Process in batches
        logger.info(f"Processing {len(actions)} actions in batches of {batch_size}")
        all_prioritized = []
        
        for i in range(0, len(actions), batch_size):
            batch = actions[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(actions) + batch_size - 1) // batch_size
            
            logger.info(f"Prioritizing batch {batch_num}/{total_batches} ({len(batch)} actions)")
            prioritized_batch = self._prioritize_batch(batch, timing_context)
            all_prioritized.extend(prioritized_batch)
        
        logger.info(f"Completed prioritization of {len(all_prioritized)} actions")
        return all_prioritized
    
    def _prioritize_batch(
        self,
        actions: List[Dict[str, Any]],
        timing_context: str
    ) -> List[Dict[str, Any]]:
        """Prioritize a single batch of actions using LLM."""
        actions_text = json.dumps(actions, indent=2)
        
        prompt = f"""Prioritize and assign timelines to these actions based on health emergency protocols.

Actions to prioritize:
{actions_text}

Timing Guidelines:
{timing_context}

For each action, assign:
1. priority_level: "immediate" (0-24h), "short-term" (1-7 days), or "long-term" (1+ weeks)
2. estimated_time: Specific timeframe (e.g., "within 2 hours", "day 1-3")
3. urgency_score: 1-10 (10 = most urgent, life-saving)
4. dependencies: List any action IDs this depends on
5. rationale: Brief explanation of priority

Health Emergency Priority Order:
- Life-saving interventions: Immediate
- Critical infrastructure: Immediate to Short-term
- Essential services: Short-term
- Recovery/improvement: Long-term

Provide JSON output:
{{
  "prioritized_actions": [
    {{
      "action": "Action description",
      "priority_level": "immediate|short-term|long-term",
      "estimated_time": "Specific timeframe",
      "urgency_score": 1-10,
      "dependencies": [],
      "rationale": "Why this priority",
      "category": "preparedness|response|recovery",
      "sources": ["Source citations"]
    }}
  ]
}}

Order actions by urgency within each priority level. Respond with valid JSON only."""
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.3
            )
            
            if isinstance(result, dict) and "prioritized_actions" in result:
                return result["prioritized_actions"]
            elif isinstance(result, list):
                return result
            else:
                logger.warning("Unexpected prioritization result")
                # Fallback: assign default priorities
                return self._apply_default_priorities(actions)
        
        except Exception as e:
            logger.error(f"Error prioritizing batch: {e}")
            return self._apply_default_priorities(actions)
    
    def _apply_default_priorities(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply default priorities based on category."""
        prioritized = []
        
        for action in actions:
            category = action.get("category", "response")
            
            # Simple default logic
            if category == "preparedness":
                priority_level = "immediate"
                urgency_score = 8
            elif category == "response":
                priority_level = "short-term"
                urgency_score = 9
            else:  # recovery
                priority_level = "long-term"
                urgency_score = 6
            
            prioritized.append({
                **action,
                "priority_level": priority_level,
                "estimated_time": f"{priority_level} phase",
                "urgency_score": urgency_score,
                "dependencies": [],
                "rationale": f"Default priority based on {category} category"
            })
        
        return prioritized
    
    def _apply_user_timing(
        self,
        actions: List[Dict[str, Any]],
        user_timing: str
    ) -> List[Dict[str, Any]]:
        """
        Apply user-specified timing to actions without specific timeframes.
        
        Only modifies actions with vague timing like "regularly", "periodically",
        "as needed", or no specific timing indicators.
        
        Args:
            actions: Prioritized actions
            user_timing: User-specified timing context (e.g., "yearly", "seasonal", "monthly")
            
        Returns:
            Actions with modified timing where appropriate
        """
        logger.info(f"Applying user timing: {user_timing}")
        
        # Keywords that indicate specific timeframes (don't modify these)
        specific_indicators = [
            "hour", "minute", "day", "week", "month",
            "within", "after", "before", "during",
            "0-", "1-", "2-", "first", "second"
        ]
        
        modified_count = 0
        
        for action in actions:
            estimated_time = action.get("estimated_time", "").lower()
            when = action.get("when", "").lower()
            
            # Check if action has specific timeframe
            has_specific_timing = any(
                indicator in estimated_time or indicator in when
                for indicator in specific_indicators
            )
            
            # Only modify if no specific timing found
            if not has_specific_timing:
                # Add timing context to the action metadata
                if "timing_context" not in action:
                    action["timing_context"] = user_timing
                
                # Modify estimated_time to include timing context
                if estimated_time and estimated_time not in ["", "tbd", "n/a"]:
                    action["estimated_time"] = f"{estimated_time} ({user_timing})"
                else:
                    action["estimated_time"] = f"As per {user_timing} schedule"
                
                modified_count += 1
        
        logger.info(f"Modified timing for {modified_count} actions based on user timing: {user_timing}")
        return actions

