# Quality Checker Templates

This directory contains context-specific quality checking templates for the Action Plan Generation System.

## Overview

The Quality Checker Agent uses these templates to apply appropriate quality standards based on:
- **Organizational Level** (ministry, university, center)
- **Plan Phase** (preparedness, response)
- **Crisis Type** (war, sanction)

## Template Naming Convention

Templates follow this naming pattern:
```
{level}_{phase}_{subject}.md
```

### Examples:
- `center_response_war.md` - For center-level response phase plans addressing war scenarios
- `ministry_preparedness_sanction.md` - For ministry-level preparedness phase plans addressing sanctions
- `university_response_sanction.md` - For university-level response phase plans addressing sanctions

### Special Cases:
- Some university templates may have a space: `university _{phase}_{subject}.md`
- The system automatically handles these naming variations

## Available Templates

### War Scenarios
| Level | Phase | Filename |
|-------|-------|----------|
| Center | Preparedness | `center_preparedness_war.md` |
| Center | Response | `center_response_war.md` |
| University | Preparedness | `university _preparedness_war.md` |
| University | Response | `university _response_war.md` |
| Ministry | Preparedness | `ministry_preparedness_war.md` |
| Ministry | Response | `ministry_response_war.md` |

### Sanction Scenarios
| Level | Phase | Filename |
|-------|-------|----------|
| Center | Preparedness | `center_preparedness_sanction.md` |
| Center | Response | `center_response_sanction.md` |
| University | Preparedness | `university_preparedness_sanction.md` |
| University | Response | `university_response_sanction.md` |
| Ministry | Preparedness | `ministry_preparedness_sanction.md` |
| Ministry | Response | `ministry_response_sanction.md` |

## Template Structure

Each template contains two main parts:

### Part One: Framework Rules
Rules for the strategic plan framework (EOP for preparedness, IAP for response):
- Definition and purpose
- Governing principles
- Command and authority rules
- Mandatory functions
- Specific requirements for the crisis type

### Part Two: Checklist Creation Rules
Rules for creating implementing checklists:
- Structural specifications
- Target audience definition
- Content formatting rules
- Accountability requirements
- Role-based writing guidelines

## How Templates Are Used

### 1. Template Selection
When the Quality Checker is invoked, it automatically selects the appropriate template based on the user configuration:

```python
user_config = {
    "level": "center",      # ministry | university | center
    "phase": "response",    # preparedness | response
    "subject": "war"        # war | sanction
}

# Template selected: center_response_war.md
```

### 2. Template Loading
The system uses `quality_checker_template_loader.py` to:
1. Map config parameters to template filename
2. Load template content from this directory
3. Append template rules to base quality checker prompt
4. Provide context-aware quality checking

### 3. Quality Checking
The loaded template enhances the quality checker with:
- **Specific structural requirements** for the plan type
- **Mandatory fields and sections** that must be present
- **Formatting rules** that must be followed
- **Role and responsibility standards** specific to the level
- **Phase-specific requirements** (EOP vs IAP, timing, etc.)

## Usage Example

### In Code:
```python
from utils.quality_checker_template_loader import assemble_quality_checker_prompt

user_config = {
    "level": "university",
    "phase": "preparedness",
    "subject": "war"
}

# Get context-specific prompt with template
quality_prompt = assemble_quality_checker_prompt(user_config)

# The prompt now includes:
# 1. Base quality checker instructions
# 2. University-level preparedness rules for war scenarios
# 3. Specific checklist creation requirements
```

### Via Quality Checker Agent:
```python
from agents.quality_checker import QualityCheckerAgent

# Initialize agent
quality_checker = QualityCheckerAgent("quality_checker", dynamic_settings, rules_rag)

# Execute with config (template loaded automatically)
result = quality_checker.execute(
    data=action_plan_data,
    stage="formatter",
    user_config={
        "level": "center",
        "phase": "response",
        "subject": "war"
    }
)
```

## Template Content Guidelines

When creating or modifying templates, ensure they include:

### Required Sections:
1. ✅ **Framework Rules** (Part One)
   - Plan definition and purpose
   - Governing principles
   - Command structure rules
   - Mandatory preparedness/response functions
   - Level-specific requirements

2. ✅ **Checklist Rules** (Part Two)
   - Structural specifications
   - Target audience definition
   - Content formatting requirements
   - Accountability standards

### Key Quality Standards:
- **Role-Based Writing**: Use organizational roles, not individuals
- **Mandatory Profile Data**: Checklist name, domain, crisis scope, type
- **Directive Language**: Short, clear, command-style verbs
- **Table Organization**: Action | Status | Remarks columns
- **Execution Confirmation**: Sign-off requirements

## Testing Template Selection

To test if templates are correctly selected:

```python
from utils.quality_checker_template_loader import (
    get_quality_checker_template_info,
    list_available_quality_checker_templates
)

# List all available templates
templates = list_available_quality_checker_templates()
print(f"Available templates: {templates}")

# Check which template would be used for a config
config = {"level": "ministry", "phase": "preparedness", "subject": "sanction"}
template_info = get_quality_checker_template_info(config)
print(f"Template: {template_info['template_name']}")
print(f"Exists: {template_info['exists']}")
print(f"Path: {template_info['path']}")
```

## Fallback Behavior

If no template is found for a given configuration:
- System logs a warning
- Base quality checker prompt is used
- Quality checking continues (may be less precise)
- No errors are raised

## Adding New Templates

To add a new template:

1. **Create file** following naming convention: `{level}_{phase}_{subject}.md`
2. **Structure content** with Part One (Framework) and Part Two (Checklists)
3. **Include all required sections** as described above
4. **Test template** using the testing code above
5. **Verify loading** in Quality Checker agent logs

Example:
```bash
# New template for regional-level (if added in future)
templates/prompt_extensions/QualityChecker/regional_response_war.md
```

## Troubleshooting

### Template Not Loading
- Check filename matches exactly: `{level}_{phase}_{subject}.md`
- Verify file exists in this directory
- Check for typos in level/phase/subject values
- Look for space variations (especially for university templates)

### Template Content Issues
- Ensure markdown formatting is correct
- Verify all section headers are present
- Check for proper encoding (UTF-8)
- Test with Quality Checker to see actual usage

## Related Files

- `/utils/quality_checker_template_loader.py` - Template loading logic
- `/config/prompts.py` - Base quality checker prompt and get_prompt() function
- `/agents/quality_checker.py` - Quality Checker agent implementation
- `/config/settings.py` - Project settings and paths

## Maintenance

Templates should be reviewed and updated:
- ✅ **Annually** - To reflect updated health policy standards
- ✅ **After incidents** - Incorporate lessons learned
- ✅ **When regulations change** - Align with new requirements
- ✅ **Based on feedback** - Improve quality checking effectiveness

---

For questions or issues with quality checker templates, consult the project maintainer or review the codebase documentation.

