"""Utility for loading quality checker templates based on user configuration."""

import logging
from pathlib import Path
from typing import Dict, Optional
from config.settings import get_settings
from config.prompts import QUALITY_CHECKER_PROMPT

logger = logging.getLogger(__name__)


def select_quality_checker_template(config: Dict[str, str]) -> Optional[str]:
    """
    Select and load the appropriate quality checker template based on user configuration.
    
    Args:
        config: Dictionary containing user inputs:
            - level: ministry | university | center
            - phase: preparedness | response
            - subject: war | sanction
            
    Returns:
        Template content string or None if not found
        
    Raises:
        ValueError: If required config parameters are missing or invalid
    """
    # Validate required parameters
    required_keys = ['level', 'phase', 'subject']
    missing = [key for key in required_keys if key not in config or not config[key]]
    
    if missing:
        raise ValueError(f"Missing required configuration parameters for quality checker: {', '.join(missing)}")
    
    # Normalize values to lowercase
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
    
    # Build template filename following the naming convention: {level}_{phase}_{subject}.md
    template_filename = f"{level}_{phase}_{subject}.md"
    
    # Get quality checker template directory
    # Quality checker templates are in templates/prompt_extensions/QualityChecker
    # Calculate path relative to this file
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent  # Go up from utils/ to project root
    template_dir = project_root / "templates" / "prompt_extensions" / "QualityChecker"
    
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
            f"Quality checker template not found: {template_filename} "
            f"(searched in {template_dir})"
        )
        return None
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        logger.info(f"Successfully loaded quality checker template: {template_filename}")
        return content
    except Exception as e:
        logger.error(f"Failed to read quality checker template {template_filename}: {e}")
        return None


def assemble_quality_checker_prompt(config: Dict[str, str]) -> str:
    """
    Assemble quality checker prompt by combining base prompt with context-specific template.
    
    Args:
        config: Dictionary containing user inputs:
            - level: ministry | university | center
            - phase: preparedness | response
            - subject: war | sanction
            
    Returns:
        Assembled prompt string with template appended
        
    Raises:
        ValueError: If required config parameters are missing or invalid
    """
    # Start with base quality checker prompt
    base_prompt = QUALITY_CHECKER_PROMPT
    
    # Load context-specific template
    template_content = select_quality_checker_template(config)
    
    if template_content:
        # Append template content to base prompt
        assembled_prompt = f"""{base_prompt}

\n---

## Context-Specific Quality Rules

**For the current action plan context:**
- **Level**: {config['level'].title()}
- **Phase**: {config['phase'].title()}
- **Subject**: {config['subject'].title()}

**The following rules and standards apply:**

{template_content}

---

**Quality Checking Instructions:**

When evaluating the action plan, ensure strict adherence to ALL rules specified above. Pay particular attention to:
1. Structural requirements (mandatory profile data, role assignments, etc.)
2. Content formatting rules (directive language, table organization, status options)
3. Accountability requirements (execution confirmation, reporting)
4. Phase-specific rules (EOP vs IAP requirements, timing, review cycles)
5. Level-specific requirements (organizational hierarchy, command structure)

For each violation of the above rules, provide:
- Specific rule reference (quote the violated rule)
- Severity (critical/major/minor)
- Detailed explanation of the violation
- Concrete remediation steps
"""
        logger.info(
            f"Assembled quality checker prompt with template for "
            f"{config['level']}/{config['phase']}/{config['subject']}"
        )
    else:
        # Template not found, use base prompt with warning
        assembled_prompt = f"""{base_prompt}

\n---

**Note**: No context-specific template was found for {config['level']}/{config['phase']}/{config['subject']}. 
Using generic quality checking criteria. Results may be less precise.
"""
        logger.warning(
            f"Using base quality checker prompt without template for "
            f"{config['level']}/{config['phase']}/{config['subject']}"
        )
    
    return assembled_prompt


def list_available_quality_checker_templates() -> list:
    """
    List all available quality checker template files.
    
    Returns:
        List of template filenames
    """
    # Calculate path relative to this file
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent  # Go up from utils/ to project root
    template_dir = project_root / "templates" / "prompt_extensions" / "QualityChecker"
    
    if not template_dir.exists():
        logger.warning(f"Quality checker template directory not found: {template_dir}")
        return []
    
    templates = [f.name for f in template_dir.glob("*.md") if f.name != "README.md"]
    return sorted(templates)


def validate_quality_checker_config(config: Dict[str, str]) -> tuple[bool, Optional[str]]:
    """
    Validate quality checker configuration dictionary.
    
    Args:
        config: Quality checker configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_keys = ['level', 'phase', 'subject']
    
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
    
    return True, None


def get_quality_checker_template_info(config: Dict[str, str]) -> Dict[str, any]:
    """
    Get information about the quality checker template that would be used for given config.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary with template information:
            - template_name: Name of template file
            - exists: Whether template file exists
            - path: Full path to template
    """
    level = config['level'].lower()
    phase = config['phase'].lower()
    subject = config['subject'].lower()
    
    template_filename = f"{level}_{phase}_{subject}.md"
    
    # Calculate path relative to this file
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent  # Go up from utils/ to project root
    template_dir = project_root / "templates" / "prompt_extensions" / "QualityChecker"
    template_path = template_dir / template_filename
    
    # Check for university special case
    if not template_path.exists() and level == "university":
        template_filename_alt = f"university _{phase}_{subject}.md"
        template_path_alt = template_dir / template_filename_alt
        if template_path_alt.exists():
            template_path = template_path_alt
            template_filename = template_filename_alt
    
    return {
        "template_name": template_filename,
        "exists": template_path.exists(),
        "path": str(template_path)
    }

