# Assigning Translator Agent Implementation

## Overview

A new specialized agent has been added to the translation workflow to ensure accurate translation of organizational assignments, job titles, departments, and units in Persian action plans. This agent serves as the final step in the translation pipeline, correcting any mistranslations of organizational terminology to match the official Ministry of Health structure.

## Agent Purpose

The **Assigning Translator Agent** addresses a critical quality issue in translations: while general translation may be accurate, organizational terminology (job titles, department names, unit designations) often requires precise official terminology that matches the Iranian Ministry of Health organizational structure.

### Key Responsibilities

1. **Organizational Terminology Correction**: Ensures all job titles, departments, and units use official Persian terminology
2. **Reference-Based Validation**: Compares translated organizational assignments against the official reference document
3. **Hierarchical Accuracy**: Maintains correct organizational hierarchy (Ministry > University > Center/Hospital)
4. **Structure Preservation**: Keeps all markdown formatting, tables, and document structure intact

## Implementation Details

### File Structure

```
agents/
├── assigning_translator.py          # New agent implementation
└── __init__.py                       # Updated with new agent

config/
└── prompts.py                        # Added ASSIGNING_TRANSLATOR_PROMPT

workflows/
└── orchestration.py                  # Integrated agent into workflow

assigner_tools/Fa/
└── Assigner refrence.md             # Reference document (existing)
```

### Agent Flow

The translation workflow now follows this sequence:

```
translator → segmentation → term_identifier → dictionary_lookup → refinement → assigning_translator → END
```

### Key Features

#### 1. Reference Document Integration
- Loads `assigner_tools/Fa/Assigner refrence.md` automatically
- Contains complete Ministry of Health organizational structure
- Covers three hierarchical levels:
  - **Ministry Level**: Deputy Ministries, General Directorates, Centers, Offices
  - **University Level**: Vice-Presidencies, Directorates, Schools, Research Centers
  - **Center/Hospital Level**: 5-level hospital hierarchy (President → Manager → Supervisors → Department Heads → Staff)

#### 2. Intelligent Correction
The agent:
- Identifies organizational terminology in the translated text
- Compares against official reference document
- Corrects mistranslations while preserving context
- Maintains all formatting and non-organizational content

#### 3. Common Corrections

The agent is designed to catch and fix common mistranslations:

| Incorrect Translation | Correct Translation |
|----------------------|---------------------|
| مدیر بیمارستان (for President) | رئیس بیمارستان |
| مدیر پرستاری | مترون / مدیر خدمات پرستاری |
| مرکز عملیات اضطراری | مرکز مدیریت حوادث و فوریت‌های پزشکی |
| وزارت معاون | معاونت بهداشت / معاونت درمان |
| شبکه سلامت | شبکه بهداشت و درمان |

#### 4. Error Handling
- Gracefully handles missing reference document
- Returns original translation if correction fails
- Logs all errors for debugging
- Does not block the translation pipeline

## Technical Implementation

### Agent Class

```python
class AssigningTranslatorAgent:
    """
    Corrects organizational assignments in Persian translations to match
    official Ministry of Health organizational structure.
    """
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        # Initialize LLM client
        # Load reference document
        # Set up system prompt
    
    def _load_reference_document(self) -> str:
        # Loads assigner_tools/Fa/Assigner refrence.md
    
    def execute(self, data: Dict[str, Any]) -> str:
        # Corrects organizational terminology in translated plan
```

### System Prompt

The agent uses a comprehensive Persian-language system prompt that:
- Defines the agent's role as an organizational terminology correction specialist
- Provides detailed correction principles
- Lists common mistranslations to correct
- Specifies organizational hierarchy structure
- Ensures formatting preservation

### Integration Points

#### Workflow Orchestration
```python
# Initialize agent
assigning_translator = AssigningTranslatorAgent("assigning_translator", dynamic_settings, markdown_logger)

# Add node
workflow.add_node("assigning_translator", assigning_translator_node)

# Update edges
workflow.add_edge("refinement", "assigning_translator")
workflow.add_edge("assigning_translator", END)
```

## Benefits

1. **Accuracy**: Ensures organizational terminology matches official Ministry of Health structure
2. **Consistency**: All plans use standardized terminology
3. **Professionalism**: Delivers translation-quality equivalent to official government documents
4. **Automated**: No manual correction needed after translation
5. **Scalable**: Handles any size document efficiently

## Usage

The agent is automatically invoked as the final step in the translation workflow. No configuration or manual intervention required.

### Input
- Persian-translated action plan (after dictionary refinement)

### Output
- Corrected Persian plan with accurate organizational assignments

### Logging
The agent logs:
- Input/output document lengths
- Reference document loading status
- Any errors encountered
- Completion status

## Future Enhancements

Potential improvements:
1. Track specific corrections made for reporting
2. Add confidence scoring for corrections
3. Flag uncertain corrections for human review
4. Support for multiple organizational structures (other ministries)
5. Version control for reference document updates

## Testing

To test the agent:
1. Generate an action plan in English
2. Let it flow through the translation pipeline
3. Check the final Persian output for organizational terminology
4. Verify job titles match the reference document

## Maintenance

### Updating Reference Document
When the Ministry of Health organizational structure changes:
1. Update `assigner_tools/Fa/Assigner refrence.md`
2. No code changes needed - agent automatically loads latest version

### Monitoring
Monitor agent logs for:
- Reference document loading failures
- Correction failures
- Unusually short/long correction times

## Conclusion

The Assigning Translator Agent completes the translation pipeline with a critical quality assurance step, ensuring that all organizational terminology in translated action plans accurately reflects the official Ministry of Health structure. This automation saves time, ensures consistency, and delivers professionally-translated documents ready for official use.

