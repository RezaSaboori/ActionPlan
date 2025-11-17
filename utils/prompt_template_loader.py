"""Utility for assembling orchestrator prompts from templates."""

import logging
from pathlib import Path
from typing import Dict, Optional
from config.settings import get_settings
from config.prompts import ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


def select_orchestrator_template(config: Dict[str, str]) -> Optional[str]:
    """
    Select and load the appropriate orchestrator template based on user configuration.
    
    Args:
        config: Dictionary containing user inputs:
            - level: ministry | university | center
            - phase: preparedness | response
            - subject: war | sanction
            
    Returns:
        Template content string or None if not found
    """
    # Validate required parameters
    required_keys = ['level', 'phase', 'subject']
    missing = [key for key in required_keys if key not in config or not config[key]]
    
    if missing:
        logger.warning(f"Missing configuration parameters for template selection: {', '.join(missing)}")
        return None
    
    # Normalize values to lowercase
    level = config['level'].lower()
    phase = config['phase'].lower()
    subject = config['subject'].lower()
    
    # Build template filename following the naming convention: {level}_{phase}_{subject}.md
    template_filename = f"{level}_{phase}_{subject}.md"
    
    # Get orchestrator template directory from settings
    settings = get_settings()
    template_dir = Path(settings.prompt_template_dir)
    
    # Handle relative paths
    if not template_dir.is_absolute():
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent  # Go up from utils/ to project root
        template_dir = project_root / template_dir
    
    template_path = template_dir / template_filename
    
    # Check for special case: university templates may have a space in the name
    if not template_path.exists() and level == "university":
        # Try with space: "university _{phase}_{subject}.md"
        template_filename_alt = f"university _{phase}_{subject}.md"
        template_path_alt = template_dir / template_filename_alt
        if template_path_alt.exists():
            template_path = template_path_alt
            template_filename = template_filename_alt
    
    if not template_path.exists():
        logger.warning(
            f"Orchestrator template not found: {template_filename} "
            f"(searched in {template_dir})"
        )
        return None
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"Successfully loaded orchestrator template: {template_filename}")
        return content
    except Exception as e:
        logger.error(f"Failed to read orchestrator template {template_filename}: {e}")
        return None


def assemble_orchestrator_prompt(config: Dict[str, str]) -> str:
    """
    Assemble orchestrator prompt by formatting the ORCHESTRATOR_PROMPT with user config and context-specific template.
    
    Args:
        config: Dictionary containing user inputs.
            
    Returns:
        Assembled prompt string with template extension if found.
        
    Raises:
        ValueError: If required config parameters are missing.
    """
    # Validate required parameters
    required_keys = ['name', 'timing', 'level', 'phase', 'subject']
    missing = [key for key in required_keys if key not in config or not config[key]]
    
    if missing:
        raise ValueError(f"Missing required configuration parameters: {', '.join(missing)}")
    
    # Format subject with explanation if it's "sanction"
    subject_value = config.get("subject")
    sanction_explanation = "externally imposed economic and trade restrictions that block access to essential medicines, cripple health infrastructure, drive health workers to leave"
    
    # Format for context section (title case)
    subject_display_context = subject_value.title() if subject_value else ""
    if subject_value and subject_value.lower() == "sanction":
        subject_display_context = f"sanction: {sanction_explanation}"
    
    # Format for main prompt template (lowercase with explanation if sanction)
    subject_display_prompt = subject_value if subject_value else ""
    if subject_value and subject_value.lower() == "sanction":
        subject_display_prompt = f"sanction: {sanction_explanation}"
    
    # Load context-specific template extension
    template_content = select_orchestrator_template(config)
    
    if template_content:
        # Format context section with template extension
        context_section = f"""
## Context-Specific Guidelines and Requirements

**For the current action plan context:**
- **Level**: {config['level'].title()}
- **Phase**: {config['phase'].title()}
- **Subject**: {subject_display_context}

**The following context-specific guidelines and requirements apply:**

{template_content}

**Note**: When generating the problem statement, ensure strict adherence to ALL guidelines and requirements specified above. These context-specific rules take precedence and must be reflected in the problem statement structure and content."""
        logger.info(
            f"Loaded orchestrator template extension for "
            f"{config['level']}/{config['phase']}/{config['subject']}"
        )
    else:
        # No template found, use empty placeholder
        context_section = ""
        logger.info(
            f"No template extension found for "
            f"{config['level']}/{config['phase']}/{config['subject']}"
        )
    
    # Prepare prompt format dictionary
    prompt_data = {
        "name": config.get("name"),
        "timing": config.get("timing"),
        "level": config.get("level"),
        "phase": config.get("phase"),
        "subject": subject_display_prompt,
        "description": config.get("description", "Not provided"),
        "context_specific_guidelines": context_section
    }

    # Format complete prompt with all placeholders
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

