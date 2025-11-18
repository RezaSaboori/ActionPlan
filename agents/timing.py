"""Timing Agent for adding triggers and timelines to actions."""

import logging
import json
import re
from typing import Dict, Any, List, Tuple
from utils.llm_client import LLMClient
from config.prompts import get_prompt, get_timing_user_prompt
from config.settings import get_settings

logger = logging.getLogger(__name__)


class TimingAgent:
    """Timing agent for adding triggers and timelines to actions."""
    
    # Forbidden vague temporal terms that require conversion
    VAGUE_TERMS = [
        "immediately", "soon", "asap", "a.s.a.p", "as soon as possible",
        "promptly", "quickly", "rapidly", "as needed", "when necessary",
        "when needed", "when required", "eventually", "shortly", "urgent"
    ]
    
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
        
        Enhanced to preserve references and handle tables.
        
        Args:
            data: Dictionary containing:
                - actions: List of actions to process
                - problem_statement: Problem/objective statement
                - user_config: User configuration
                - tables: List of table objects (optional, passed through)
            
        Returns:
            Dictionary with:
                - timed_actions: Actions updated with timing information (references preserved)
                - tables: Pass-through tables
        """
        actions = data.get("actions", [])
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        tables = data.get("tables", [])
        
        # Remove selector-specific fields that are not needed downstream
        # These fields (relevance_score, relevance_rationale) are only relevant for selection
        # Also remove redundant fields (source_node, source_lines) since they're in reference
        for action in actions:
            action.pop('relevance_score', None)
            action.pop('relevance_rationale', None)
            action.pop('source_node', None)
            action.pop('source_lines', None)
        
        logger.info(f"Timing Agent processing {len(actions)} actions")
        logger.info(f"                         {len(tables)} tables (pass-through)")
        
        if not actions:
            logger.warning("No actions to process for timing")
            return {
                "timed_actions": [],
                "tables": tables
            }
        
        # Filter actions that need timing info by checking 'when' field structure
        actions_to_process = [
            action for action in actions 
            if self._is_timing_needed(action.get("when", ""))
        ]
        
        if not actions_to_process:
            logger.info("No actions require timing updates")
            # Still remove redundant fields before returning
            for action in actions:
                action.pop('source_node', None)
                action.pop('source_lines', None)
            return {
                "timed_actions": actions,
                "tables": tables
            }
            
        logger.info(f"Found {len(actions_to_process)} actions requiring timing information")

        # Send ALL actions to LLM (per updated prompt requirement)
        # LLM will update only actions that need timing and return all actions
        all_actions_from_llm = self._get_timing_assignments(
            actions,  # Send all actions, not just ones needing timing
            problem_statement,
            user_config
        )
        
        # Validate and improve timing information for returned actions
        processed_actions = self._validate_and_consolidate_timing(all_actions_from_llm, user_config)
        
        # LLM returns all actions (updated and unchanged), so use them directly
        # Create a mapping by action description to match with original actions
        # This ensures we preserve any fields from original that LLM might not have included
        action_map = {action.get("action", ""): action for action in processed_actions}
        final_actions = []
        
        for original_action in actions:
            action_key = original_action.get("action", "")
            if action_key in action_map:
                # LLM returned this action, merge to preserve original fields
                processed_action = action_map[action_key]
                # Start with original to preserve all fields, then update with LLM output
                merged_action = dict(original_action)
                merged_action.update(processed_action)
                # Ensure 'when' field is from processed action (LLM's update)
                merged_action['when'] = processed_action.get('when', original_action.get('when', ''))
                final_actions.append(merged_action)
            else:
                # LLM didn't return this action (shouldn't happen), keep original
                logger.warning(f"Action '{action_key[:50]}...' not found in LLM response, keeping original")
                final_actions.append(original_action)
        
        logger.info(f"Timing Agent completed with {len(final_actions)} actions")
        logger.info(f"                           {len(tables)} tables")
        
        # Ensure temporary fields are removed from the final output
        # Also ensure redundant fields are removed
        for action in final_actions:
            action.pop('trigger', None)
            action.pop('time_window', None)
            action.pop('source_node', None)
            action.pop('source_lines', None)
            
        return {
            "timed_actions": final_actions,
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
        
        prompt = get_timing_user_prompt(problem_statement, config_text, actions_text)
        
        try:
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.4
            )
            
            # Expect new format: "actions" key containing all actions
            if isinstance(result, dict) and "actions" in result:
                return result["actions"]
            
            logger.error(f"LLM returned unexpected format. Expected 'actions' key, got: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            return actions # Return original actions on failure

        except Exception as e:
            logger.error(f"Error getting timing assignments: {e}")
            return actions # Return original actions on failure
    
    def _is_timing_needed(self, when_text: str) -> bool:
        """
        Check if an action's 'when' field needs processing.
        
        Args:
            when_text: The content of the 'when' field.
            
        Returns:
            True if the 'when' field is vague, unstructured, or empty.
        """
        if not when_text or not when_text.strip():
            return True
            
        when_lower = when_text.lower()
        
        # Check for vague terms
        if any(vague in when_lower for vague in self.VAGUE_TERMS):
            return True
            
        # Check for structure (must contain a separator)
        if '|' not in when_text:
            return True
            
        # Check if both parts (trigger and time_window) are valid
        parts = when_text.split('|')
        if len(parts) != 2:
            return True
            
        trigger, time_window = parts[0].strip(), parts[1].strip()
        
        is_trigger_valid, _ = self._validate_trigger(trigger)
        is_time_window_valid, _ = self._validate_time_window(time_window)
        
        return not (is_trigger_valid and is_time_window_valid)

    def _validate_and_consolidate_timing(
        self,
        actions: List[Dict[str, Any]],
        user_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Validate timing fields in 'when' field and convert vague terms if needed.
        
        LLM returns actions with 'when' field already set. This function validates
        and improves the timing if needed.
        
        Args:
            actions: List of actions with 'when' field set by LLM
            user_config: User configuration for context
            
        Returns:
            List of actions with validated and improved timing
        """
        validated_actions = []
        
        for action in actions:
            when_field = action.get("when", "")
            
            if when_field:
                # Check if when field needs validation/improvement
                if self._is_timing_needed(when_field):
                    # Still needs timing improvement, try to extract and improve
                    parts = when_field.split('|')
                    if len(parts) == 2:
                        trigger, time_window = parts[0].strip(), parts[1].strip()
                        # Validate and convert if needed
                        trigger_valid, _ = self._validate_trigger(trigger)
                        time_window_valid, _ = self._validate_time_window(time_window)
                        
                        if not trigger_valid or not time_window_valid:
                            trigger, time_window = self._convert_vague_terms(
                                trigger, time_window, action, user_config
                            )
                            action['when'] = f"{trigger.strip()} | {time_window.strip()}"
                    else:
                        # Invalid format, try to convert
                        trigger, time_window = self._convert_vague_terms(
                            "", when_field, action, user_config
                        )
                        action['when'] = f"{trigger.strip()} | {time_window.strip()}"
                # If when field is already valid, keep it as is
            else:
                # Empty when field - should not happen if LLM followed instructions
                logger.warning(f"Action '{action.get('action', '')[:50]}...' has empty 'when' field")
            
            validated_actions.append(action)
        
        return validated_actions
    
    def _validate_trigger(self, trigger: str) -> Tuple[bool, str]:
        """
        Validate that trigger is an observable condition or timestamp, not a vague term.
        
        Args:
            trigger: The trigger string to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not trigger or not trigger.strip():
            return False, "Empty trigger"
        
        trigger_lower = trigger.lower().strip()
        
        # Check for forbidden vague terms
        for vague_term in self.VAGUE_TERMS:
            if vague_term in trigger_lower:
                return False, f"Contains vague term '{vague_term}'"
        
        # Valid trigger patterns (observable conditions or timestamps)
        valid_patterns = [
            r"upon\s+\w+",  # "Upon notification", "Upon declaration"
            r"when\s+\w+.*\s+(exceeds?|reaches?|drops?|falls?|equals?|is\s+greater|is\s+less)",  # Observable thresholds
            r"after\s+\w+",  # "After triage", "After activation"
            r"at\s+\d{1,2}:\d{2}",  # "At 08:00"
            r"t_0|t0|timestamp",  # Reference to timestamp
            r"\d{4}-\d{2}-\d{2}",  # Date format
            r"(daily|weekly|monthly|hourly)\s+at",  # Recurring with time
            r"on\s+(receipt|arrival|completion|activation)",  # Event-based
        ]
        
        # Check if trigger matches any valid pattern
        for pattern in valid_patterns:
            if re.search(pattern, trigger_lower):
                return True, "Valid observable trigger"
        
        # If no vague terms but also no recognized pattern, still accept
        # (might be a specific condition we haven't enumerated)
        if len(trigger.split()) > 2:  # At least 3 words suggests specificity
            return True, "Specific trigger condition"
        
        return False, "Trigger lacks observable condition or timestamp"
    
    def _validate_time_window(self, time_window: str) -> Tuple[bool, str]:
        """
        Validate that time window has specific duration format.
        
        Args:
            time_window: The time window string to validate
            
        Returns:
            Tuple of (is_valid, reason)
        """
        if not time_window or not time_window.strip():
            return False, "Empty time window"
        
        time_window_lower = time_window.lower().strip()
        
        # Check for forbidden vague terms
        for vague_term in self.VAGUE_TERMS:
            if vague_term in time_window_lower:
                return False, f"Contains vague term '{vague_term}'"
        
        # Valid time window patterns (specific durations)
        valid_patterns = [
            r"within\s+\d+[-\s]?\d*\s*(minute|min|hour|hr|day|week)",  # "Within 30 minutes", "Within 1-2 hours"
            r"\d+[-\s]?\d*\s*(minute|min|hour|hr|day|week)",  # "30 minutes", "1-2 hours"
            r"t_0\s*\+\s*\d+",  # "T_0 + 30 min"
            r"t0\s*\+\s*\d+",  # "T0 + 30"
            r"maximum\s+\d+",  # "Maximum 2 hours"
            r"before\s+t_0\s*\+",  # "Before T_0 + 60 min"
            r"\d+\s*to\s*\d+\s*(minute|min|hour|hr)",  # "15 to 20 minutes"
        ]
        
        # Check if time window matches any valid pattern
        for pattern in valid_patterns:
            if re.search(pattern, time_window_lower):
                return True, "Valid specific time window"
        
        return False, "Time window lacks specific duration with units"
    
    def _convert_vague_terms(
        self, 
        trigger: str, 
        time_window: str,
        action_context: Dict[str, Any],
        user_config: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Convert vague temporal terms to specific timestamps based on action context.
        
        Args:
            trigger: Original trigger (may contain vague terms)
            time_window: Original time window (may contain vague terms)
            action_context: Full action dictionary with context
            user_config: User configuration for additional context
            
        Returns:
            Tuple of (converted_trigger, converted_time_window)
        """
        converted_trigger = trigger
        converted_time_window = time_window
        
        # Extract context factors
        action_desc = action_context.get("action", "").lower()
        subject = action_context.get("subject", "").lower()
        phase = user_config.get("phase", "").lower()
        level = user_config.get("level", "").lower()
        
        # Determine action category from context
        is_emergency = any(term in action_desc for term in ["emergency", "critical", "urgent", "life-threatening", "code"])
        is_clinical = any(term in action_desc for term in ["patient", "clinical", "medical", "treatment", "triage", "surgery"])
        is_administrative = any(term in action_desc for term in ["report", "document", "coordinate", "meeting", "review", "approve"])
        is_communication = any(term in action_desc for term in ["notify", "alert", "communicate", "inform", "announce", "contact"])
        is_training = any(term in action_desc for term in ["train", "drill", "exercise", "practice", "educate"])
        is_resource = any(term in action_desc for term in ["mobilize", "allocate", "procure", "deploy", "resource", "supply"])
        
        # Convert vague terms in TRIGGER
        trigger_lower = trigger.lower()
        for vague_term in self.VAGUE_TERMS:
            if vague_term in trigger_lower:
                # For triggers, convert vague term to "Upon [event] (T_0)"
                if "immediately" in trigger_lower or "asap" in trigger_lower or "promptly" in trigger_lower:
                    # Extract the context after the vague term if present
                    context_match = re.search(rf"{vague_term}\s+(upon|after|when)?\s*(.+)", trigger_lower)
                    if context_match and context_match.group(2):
                        converted_trigger = f"Upon {context_match.group(2).strip()} (T_0)"
                    else:
                        converted_trigger = f"Upon event activation (T_0)"
                break
        
        # Convert vague terms in TIME WINDOW
        time_window_lower = time_window.lower()
        for vague_term in self.VAGUE_TERMS:
            if vague_term in time_window_lower:
                # Context-based conversion
                if "immediately" in time_window_lower or "asap" in time_window_lower or "promptly" in time_window_lower:
                    if is_emergency:
                        converted_time_window = "Within 5 minutes (T_0 + 5 min)"
                    elif is_communication:
                        converted_time_window = "Within 2-3 minutes (T_0 + 2-3 min)"
                    elif is_administrative:
                        converted_time_window = "Within 15 minutes (T_0 + 15 min)"
                    else:
                        converted_time_window = "Within 10 minutes (T_0 + 10 min)"
                
                elif "soon" in time_window_lower or "shortly" in time_window_lower:
                    if is_clinical:
                        converted_time_window = "Within 30-60 minutes (T_0 + 30-60 min)"
                    elif is_resource:
                        converted_time_window = "Within 2-4 hours (T_0 + 2-4 hr)"
                    elif is_training:
                        converted_time_window = "Within 24-48 hours (T_0 + 24-48 hr)"
                    else:
                        converted_time_window = "Within 1-2 hours (T_0 + 1-2 hr)"
                
                elif "quickly" in time_window_lower or "rapidly" in time_window_lower:
                    if is_emergency:
                        converted_time_window = "Within 10-15 minutes (T_0 + 10-15 min)"
                    elif is_clinical:
                        converted_time_window = "Within 20-30 minutes (T_0 + 20-30 min)"
                    else:
                        converted_time_window = "Within 30 minutes (T_0 + 30 min)"
                
                elif any(term in time_window_lower for term in ["as needed", "when necessary", "when needed", "when required"]):
                    # These suggest on-demand actions
                    if is_clinical:
                        converted_time_window = "Within 15-30 minutes of request (T_request + 15-30 min)"
                    else:
                        converted_time_window = "Within 1 hour of request (T_request + 60 min)"
                
                elif "urgent" in time_window_lower:
                    if is_emergency:
                        converted_time_window = "Within 15 minutes (T_0 + 15 min)"
                    else:
                        converted_time_window = "Within 30-60 minutes (T_0 + 30-60 min)"
                
                break
        
        return converted_trigger, converted_time_window
    
    def _check_when_field(
        self, 
        action: Dict[str, Any],
        user_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate and potentially modify the 'when' field to ensure it meets timing requirements.
        
        Args:
            action: Action dictionary
            user_config: User configuration for context
            
        Returns:
            Updated action dictionary
        """
        # This function's logic has been integrated into _is_timing_needed
        # and _validate_and_consolidate_timing.
        # It can be kept for compatibility or removed. For now, just pass through.
        return action

