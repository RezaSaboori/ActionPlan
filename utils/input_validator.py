"""Input validation utilities for user configuration."""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class InputValidator:
    """Validator for user input configuration."""
    
    VALID_LEVELS = ['ministry', 'university', 'center']
    VALID_PHASES = ['preparedness', 'response']
    VALID_SUBJECTS = ['war', 'sanction']
    
    @staticmethod
    def validate_user_config(config: Dict[str, str]) -> Tuple[bool, List[str]]:
        """
        Validate user configuration dictionary.
        
        Args:
            config: Dictionary with user parameters
            
        Returns:
            Tuple of (is_valid, list_of_error_messages)
        """
        errors = []
        
        # Check if config is a dictionary
        if not isinstance(config, dict):
            return False, ["Configuration must be a dictionary"]
        
        # Check required keys
        required_keys = ['name', 'timing', 'level', 'phase', 'subject']
        for key in required_keys:
            if key not in config:
                errors.append(f"Missing required parameter: '{key}'")
            elif not config[key] or not str(config[key]).strip():
                errors.append(f"Parameter '{key}' cannot be empty")
        
        # If basic validation failed, return early
        if errors:
            return False, errors
        
        # Validate enum values
        level = str(config['level']).strip().lower()
        phase = str(config['phase']).strip().lower()
        subject = str(config['subject']).strip().lower()
        
        if level not in InputValidator.VALID_LEVELS:
            errors.append(
                f"Invalid level '{level}'. Must be one of: {', '.join(InputValidator.VALID_LEVELS)}"
            )
        
        if phase not in InputValidator.VALID_PHASES:
            errors.append(
                f"Invalid phase '{phase}'. Must be one of: {', '.join(InputValidator.VALID_PHASES)}"
            )
        
        if subject not in InputValidator.VALID_SUBJECTS:
            errors.append(
                f"Invalid subject '{subject}'. Must be one of: {', '.join(InputValidator.VALID_SUBJECTS)}"
            )
        
        # Validate name length
        name = str(config['name']).strip()
        if len(name) < 5:
            errors.append("Action plan name must be at least 5 characters long")
        elif len(name) > 200:
            errors.append("Action plan name must be at most 200 characters long")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def normalize_config(config: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize user configuration (lowercase enums, trim strings).
        
        Args:
            config: Raw user configuration
            
        Returns:
            Normalized configuration dictionary
        """
        normalized = {}
        
        for key, value in config.items():
            if key in ['level', 'phase', 'subject']:
                # Normalize enum values to lowercase
                normalized[key] = str(value).strip().lower()
            else:
                # Trim other string values
                normalized[key] = str(value).strip()
        
        return normalized
    
    @staticmethod
    def get_validation_help() -> str:
        """
        Get help text for validation requirements.
        
        Returns:
            Formatted help string
        """
        return f"""
User Configuration Requirements:

Required Parameters:
  - name: Action plan title (5-200 characters)
  - timing: Time period and/or trigger (free text)
  - level: One of {', '.join(InputValidator.VALID_LEVELS)}
  - phase: One of {', '.join(InputValidator.VALID_PHASES)}
  - subject: One of {', '.join(InputValidator.VALID_SUBJECTS)}

Example:
  {{
    "name": "Emergency Triage Protocol for Mass Casualty Events",
    "timing": "Immediate activation upon Code Orange declaration",
    "level": "ministry",
    "phase": "response",
    "subject": "war"
  }}
"""

