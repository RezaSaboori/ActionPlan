# Quality Checker Template Mapping System - Implementation Summary

## Overview
Successfully implemented a dynamic template selection system for the Quality Checker Agent that automatically loads context-specific quality rules based on user configuration (level, phase, subject) - similar to how the Orchestrator agent uses prompt extensions.

## Files Created

### 1. `/utils/quality_checker_template_loader.py` (NEW)
A comprehensive utility module for quality checker template management.

**Key Functions:**

- **`select_quality_checker_template(config)`**
  - Maps user config (level, phase, subject) to template filename
  - Handles special naming cases (e.g., university templates with spaces)
  - Returns template content or None if not found
  - Validates config parameters

- **`assemble_quality_checker_prompt(config)`**
  - Main function for assembling context-specific quality checker prompts
  - Combines base prompt with loaded template
  - Appends context information and specific quality rules
  - Provides detailed checking instructions
  - Falls back gracefully if template not found

- **`list_available_quality_checker_templates()`**
  - Lists all available template files
  - Useful for debugging and verification

- **`validate_quality_checker_config(config)`**
  - Validates user configuration
  - Checks for required keys and valid values
  - Returns (is_valid, error_message) tuple

- **`get_quality_checker_template_info(config)`**
  - Returns template metadata for given config
  - Useful for debugging and testing

## Files Modified

### 2. `/config/prompts.py` (MODIFIED)
Updated the `get_prompt()` function to support template loading for quality_checker agent.

**Changes:**
- Added optional `config` parameter
- Added special handling for `agent_name == "quality_checker"`
- Calls `assemble_quality_checker_prompt(config)` when config is provided
- Falls back to base prompt if template loading fails
- Maintains backward compatibility

```python
def get_prompt(agent_name: str, include_examples: bool = False, config: dict = None) -> str:
    # ... existing code ...
    
    # Special handling for quality_checker with config-based template loading
    if agent_name == "quality_checker" and config is not None:
        try:
            from utils.quality_checker_template_loader import assemble_quality_checker_prompt
            prompt = assemble_quality_checker_prompt(config)
        except Exception as e:
            logger.warning(f"Failed to load quality checker template: {e}. Using base prompt.")
            prompt = QUALITY_CHECKER_PROMPT
    # ... rest of code ...
```

### 3. `/agents/quality_checker.py` (MODIFIED)
Updated QualityCheckerAgent to use user_config for template loading.

**Changes:**
- Modified `execute()` method to accept optional `user_config` parameter
- Dynamically loads system prompt with templates based on user_config
- Passes system_prompt to `_evaluate()` method
- Updated `_evaluate()` method signature to accept `system_prompt` parameter
- Added logging for template loading

**New Method Signature:**
```python
def execute(
    self,
    data: Dict[str, Any],
    stage: str,
    user_config: Dict[str, str] = None  # NEW PARAMETER
) -> Dict[str, Any]:
```

### 4. `/templates/prompt_extensions/QualityChecker/README.md` (NEW)
Comprehensive documentation for the quality checker template system.

**Includes:**
- Overview of template system
- Naming conventions
- Available templates table
- Template structure guidelines
- Usage examples
- Testing procedures
- Troubleshooting guide
- Maintenance recommendations

## Template Mapping Logic

The system maps user configuration to templates using this logic:

```
Configuration:
  level: ministry | university | center
  phase: preparedness | response
  subject: war | sanction

Template Filename Pattern:
  {level}_{phase}_{subject}.md

Examples:
  center + response + war        → center_response_war.md
  ministry + preparedness + sanction  → ministry_preparedness_sanction.md
  university + response + war    → university _response_war.md  (note the space)
```

### Special Handling
- **University templates**: System checks for both `university_{phase}_{subject}.md` and `university _{phase}_{subject}.md` (with space)
- **Missing templates**: Falls back to base prompt with warning log
- **Invalid config**: Raises ValueError with clear error message

## Available Templates (12 total)

### War Scenarios (6)
1. `center_preparedness_war.md`
2. `center_response_war.md`
3. `university _preparedness_war.md`
4. `university _response_war.md`
5. `ministry_preparedness_war.md`
6. `ministry_response_war.md`

### Sanction Scenarios (6)
7. `center_preparedness_sanction.md`
8. `center_response_sanction.md`
9. `university_preparedness_sanction.md`
10. `university_response_sanction.md`
11. `ministry_preparedness_sanction.md`
12. `ministry_response_sanction.md`

## Template Content Structure

Each template contains two main parts:

### Part One: Framework Rules
- Plan definition (EOP for preparedness, IAP for response)
- Governing principles
- Command and authority rules
- Mandatory preparedness/response functions
- Level-specific requirements
- Crisis-specific considerations

### Part Two: Checklist Creation Rules
- Structural specifications
- Target audience definition
- Mandatory profile data requirements
- Content formatting rules
- Accountability standards
- Role-based writing guidelines

## Integration with Workflow

The quality checker template system integrates seamlessly with the existing workflow:

```
Workflow Step → Quality Check → Template Selection
     ↓                ↓                    ↓
User Config → QualityChecker.execute() → select_template()
     ↓                ↓                    ↓
Template Loaded → Prompt Assembled → Quality Check Performed
```

### Workflow Call Example:
```python
# In workflow node function
user_config = state.get("user_config", {})

result = quality_checker.execute(
    data=formatted_plan,
    stage="formatter",
    user_config=user_config  # Templates loaded automatically based on this
)
```

## Key Features

### ✅ Dynamic Template Selection
- Automatic selection based on level/phase/subject
- No manual template management required
- Handles naming variations automatically

### ✅ Graceful Fallback
- Falls back to base prompt if template not found
- Logs warnings for debugging
- Never crashes due to missing templates

### ✅ Validation
- Validates config parameters before template selection
- Clear error messages for invalid configurations
- Type checking and value validation

### ✅ Context-Aware Quality Checking
- Templates provide specific rules for each scenario
- Different standards for ministry/university/center
- Different requirements for preparedness/response
- Crisis-specific considerations (war vs sanction)

### ✅ Backward Compatibility
- `user_config` parameter is optional
- Works with existing code that doesn't pass config
- Base prompt used when config not provided

### ✅ Logging and Debugging
- Comprehensive logging at each step
- Template info retrieval for debugging
- List available templates function
- Validation feedback

## Testing

### Manual Testing:
```python
from utils.quality_checker_template_loader import (
    assemble_quality_checker_prompt,
    get_quality_checker_template_info,
    list_available_quality_checker_templates
)

# List all templates
templates = list_available_quality_checker_templates()
print(f"Found {len(templates)} templates: {templates}")

# Test specific config
config = {
    "level": "center",
    "phase": "response",
    "subject": "war"
}

# Get template info
info = get_quality_checker_template_info(config)
print(f"Template: {info['template_name']}")
print(f"Exists: {info['exists']}")

# Assemble prompt
prompt = assemble_quality_checker_prompt(config)
print(f"Prompt length: {len(prompt)} characters")
```

### Integration Testing:
```python
from agents.quality_checker import QualityCheckerAgent

# Initialize agent
quality_checker = QualityCheckerAgent("quality_checker", dynamic_settings, rules_rag)

# Execute with config
result = quality_checker.execute(
    data=test_action_plan,
    stage="formatter",
    user_config={
        "level": "university",
        "phase": "preparedness",
        "subject": "war"
    }
)

# Verify template was loaded (check logs)
# Verify quality checks applied correct standards
```

## Benefits

1. **Precision**: Quality checks are tailored to specific scenarios
2. **Maintainability**: Templates can be updated independently
3. **Scalability**: Easy to add new templates for new scenarios
4. **Consistency**: Same selection logic as Orchestrator agent
5. **Flexibility**: Templates can be modified without code changes
6. **Transparency**: Clear mapping between config and templates
7. **Robustness**: Graceful handling of missing templates

## Comparison with Orchestrator

The implementation follows the same pattern as the Orchestrator agent:

| Aspect | Orchestrator | Quality Checker |
|--------|--------------|-----------------|
| Template Directory | `templates/prompt_extensions/Orchestrator/` | `templates/prompt_extensions/QualityChecker/` |
| Naming Convention | `{level}_{phase}_{subject}.md` | `{level}_{phase}_{subject}.md` |
| Loader Module | `utils/prompt_template_loader.py` | `utils/quality_checker_template_loader.py` |
| Main Function | `assemble_orchestrator_prompt()` | `assemble_quality_checker_prompt()` |
| Integration | Called in `OrchestratorAgent.execute()` | Called in `QualityCheckerAgent.execute()` |
| Config Required | Yes | Optional (backward compatible) |

## Future Enhancements

Potential improvements for future iterations:

1. **Template Caching**: Cache loaded templates to improve performance
2. **Template Versioning**: Version control for template evolution
3. **Template Validation**: Validate template structure and content
4. **Dynamic Template Discovery**: Auto-detect and register new templates
5. **Template Inheritance**: Allow templates to extend base templates
6. **Multi-language Support**: Templates in different languages
7. **Template Testing**: Automated testing of template effectiveness

## Documentation

Complete documentation provided in:
- `/templates/prompt_extensions/QualityChecker/README.md` - Template usage guide
- This file - Implementation summary
- Code docstrings - Inline documentation
- Logging messages - Runtime information

## Status

✅ **IMPLEMENTATION COMPLETE**

All components implemented, tested, and documented:
- [x] Template loader utility created
- [x] Config prompts updated
- [x] Quality checker agent modified
- [x] Documentation written
- [x] No linter errors
- [x] Backward compatible
- [x] Graceful error handling
- [x] Comprehensive logging

The quality checker template mapping system is ready for production use.

---

**Implementation Date**: 2025-10-26  
**Author**: AI Assistant (Cursor)  
**Review Status**: Ready for review

