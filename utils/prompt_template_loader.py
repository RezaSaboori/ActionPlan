"""Utility for assembling orchestrator prompts from templates."""

import logging
from pathlib import Path
from typing import Dict, Optional
from config.settings import get_settings
from config.prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


def assemble_orchestrator_prompt(config: Dict[str, str]) -> str:
    """
    Assemble orchestrator prompt by formatting the ORCHESTRATOR_PROMPT.
    
    Args:
        config: Dictionary containing user inputs.
            
    Returns:
        Assembled prompt string.
        
    Raises:
        ValueError: If required config parameters are missing.
    """
    # Validate required parameters
    required_keys = ['name', 'timing', 'level', 'phase', 'subject']
    missing = [key for key in required_keys if key not in config or not config[key]]
    
    if missing:
        raise ValueError(f"Missing required configuration parameters: {', '.join(missing)}")
    
    # Prepare prompt format dictionary
    prompt_data = {
        "name": config.get("name"),
        "timing": config.get("timing"),
        "level": config.get("level"),
        "phase": config.get("phase"),
        "subject": config.get("subject"),
        "description": config.get("description", "Not provided")
    }

    # Add a note to prioritize description if it exists
    if config.get("description"):
        prompt_data["description"] = (
            f"{config['description']}\n\n"
            "**Note to Orchestrator**: The user has provided a detailed description. "
            "Prioritize this description when defining the problem statement, "
            "ensuring the core challenge reflects the user's specific goals and scope."
        )

    assembled_prompt = ORCHESTRATOR_PROMPT.format(**prompt_data)
    
    logger.info("Successfully assembled orchestrator prompt.")
    return assembled_prompt


def list_available_templates() -> list:
    """
    List all available prompt template files.
    
    Returns:
        List of template filenames
    """
    settings = get_settings()
    template_dir = Path(settings.prompt_template_dir)
    
    if not template_dir.exists():
        logger.warning(f"Template directory not found: {template_dir}")
        return []
    
    templates = [f.name for f in template_dir.glob("*.md")]
    return sorted(templates)


def validate_config(config: Dict[str, str]) -> tuple[bool, Optional[str]]:
    """
    Validate user configuration dictionary.
    
    Args:
        config: User configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ['name', 'timing', 'level', 'phase', 'subject']
    
    # Check required keys
    missing = [key for key in required_keys if key not in config or not config[key]]
    if missing:
        return False, f"Missing required parameters: {', '.join(missing)}"
    
    # Validate enum values
    level = config['level'].lower()
    phase = config['phase'].lower()
    subject = config['subject'].lower()
    
    valid_levels = ['ministry', 'university', 'center']
    valid_phases = ['preparedness', 'response']
    valid_subjects = ['war', 'sanction']
    
    if level not in valid_levels:
        return False, f"Invalid level '{level}'. Must be one of: {', '.join(valid_levels)}"
    if phase not in valid_phases:
        return False, f"Invalid phase '{phase}'. Must be one of: {', '.join(valid_phases)}"
    if subject not in valid_subjects:
        raise ValueError(f"Invalid subject '{subject}'. Must be one of: {', '.join(valid_subjects)}")
    
    return True, None

