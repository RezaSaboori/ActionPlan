"""Utility for assembling orchestrator prompts from templates."""

import logging
from pathlib import Path
from typing import Dict, Optional
from config.settings import get_settings

logger = logging.getLogger(__name__)


def assemble_orchestrator_prompt(config: Dict[str, str]) -> str:
    """
    Assemble orchestrator prompt by combining user title with selected template.
    
    Args:
        config: Dictionary containing:
            - name: the action plan title
            - timing: time period and/or trigger
            - level: ministry | university | center
            - phase: preparedness | response
            - subject: war | sanction
            
    Returns:
        Assembled prompt string combining template content + user title + output request
        
    Raises:
        FileNotFoundError: If the template file doesn't exist
        ValueError: If required config parameters are missing
    """
    # Validate required parameters
    required_keys = ['name', 'timing', 'level', 'phase', 'subject']
    missing = [key for key in required_keys if key not in config or not config[key]]
    
    if missing:
        raise ValueError(f"Missing required configuration parameters: {', '.join(missing)}")
    
    # Extract config values
    name = config['name']
    level = config['level'].lower()
    phase = config['phase'].lower()
    subject = config['subject'].lower()
    
    # Validate enum values
    valid_levels = ['ministry', 'university', 'center']
    valid_phases = ['preparedness', 'response']
    valid_subjects = ['war', 'sanction']
    
    if level not in valid_levels:
        raise ValueError(f"Invalid level '{level}'. Must be one of: {', '.join(valid_levels)}")
    if phase not in valid_phases:
        raise ValueError(f"Invalid phase '{phase}'. Must be one of: {', '.join(valid_phases)}")
    if subject not in valid_subjects:
        raise ValueError(f"Invalid subject '{subject}'. Must be one of: {', '.join(valid_subjects)}")
    
    # Build template file path
    settings = get_settings()
    template_filename = f"{level}_{phase}_{subject}.md"
    template_path = Path(settings.prompt_template_dir) / template_filename
    
    # Check if template exists
    if not template_path.exists():
        available_templates = list_available_templates()
        logger.error(f"Template not found: {template_path}")
        logger.info(f"Available templates: {', '.join(available_templates)}")
        raise FileNotFoundError(
            f"Prompt template not found: {template_filename}\n"
            f"Available templates: {', '.join(available_templates)}"
        )
    
    # Read template content
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        logger.error(f"Error reading template file {template_path}: {e}")
        raise IOError(f"Failed to read template file: {e}")
    
    # Assemble the complete prompt
    assembled_prompt = f"""# Action Plan Development Task

## User Request
**Action Plan Title**: {name}

## Context-Specific Guidelines and Requirements
{template_content}

## Your Task
Based on the above guidelines and the user's action plan title, generate a focused **problem statement** that will guide the subsequent analysis phases.

The problem statement should:
1. Clearly articulate the core challenge or scenario
2. Reference the specific context (level: {level}, phase: {phase}, subject: {subject})
3. Highlight key considerations from the guidelines above
4. Set clear boundaries for what needs to be addressed
5. Be specific enough to guide targeted document analysis

Output your response as a clear, focused problem statement (2-4 paragraphs).
"""
    
    logger.info(f"Successfully assembled orchestrator prompt using template: {template_filename}")
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
        return False, f"Invalid subject '{subject}'. Must be one of: {', '.join(valid_subjects)}"
    
    # Check if template exists
    settings = get_settings()
    template_filename = f"{level}_{phase}_{subject}.md"
    template_path = Path(settings.prompt_template_dir) / template_filename
    
    if not template_path.exists():
        available = list_available_templates()
        return False, f"Template '{template_filename}' not found. Available: {', '.join(available)}"
    
    return True, None

