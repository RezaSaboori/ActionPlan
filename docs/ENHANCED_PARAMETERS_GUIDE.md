# Enhanced Input Parameters - User Guide

## Overview

The action plan generation system now supports advanced configuration options that allow you to customize how action plans are generated, including document selection, timing contexts, and organizational metadata.

## New Features

### 1. Timing Context

**Purpose**: Specify when the action plan will be used to automatically adjust action timings.

**Examples**:
- `yearly` - Annual planning cycle
- `seasonal` - Quarterly or seasonal updates
- `monthly` - Monthly review cycles
- `weekly` - Weekly operational planning

**How it works**:
- Actions with specific timeframes (e.g., "within 2 hours", "day 1-3") remain unchanged
- Actions with vague timing (e.g., "regularly", "as needed") are modified to include your timing context
- Example: "Monitor supplies regularly" → "Monitor supplies regularly (yearly)"

**Usage in UI**:
1. Go to "Advanced Options"
2. Under "Timing and Schedule", enter your timing context
3. Generate the plan

### 2. Activation Trigger

**Purpose**: Define when this checklist should be activated.

**Examples**:
- "Mass casualty incident with >50 casualties"
- "Disease outbreak declared by health authorities"
- "Natural disaster affecting healthcare facilities"
- "Sanctions impacting medical supply chain"

**Usage in UI**:
1. Go to "Advanced Options" → "Organizational Details"
2. Enter the activation trigger
3. This appears in the "Checklist Activation Trigger" field of the generated plan

### 3. Process Owner

**Purpose**: Identify the person or unit responsible for the overall process.

**Examples**:
- "Emergency Operations Center Director"
- "Health Minister"
- "Public Health Director"
- "Hospital Chief Executive"

**Usage in UI**:
1. Go to "Advanced Options" → "Organizational Details"
2. Enter the process owner
3. This appears in the "Process Owner" field of the generated plan

### 4. Responsible Party

**Purpose**: Specify the individual or role responsible for executing the actions.

**Examples**:
- "Incident Commander"
- "Triage Team Lead"
- "Logistics Coordinator"
- "Medical Director"

**Usage in UI**:
1. Go to "Advanced Options" → "Organizational Details"
2. Enter the responsible party
3. This appears in the "Acting Individual(s)/Responsible Party" field of the generated plan

### 5. Document Selection

**Purpose**: Choose which documents to query for action extraction.

**Status**: Currently in development (placeholder in UI)

**How it will work**:
- Select specific documents from available corpus
- Guideline documents are always included (cannot be deselected)
- Empty selection means all documents are used

## Complete Workflow Example

### Scenario: Preparing a Yearly Emergency Triage Plan

**Step 1: Enter Subject**
```
Subject: Emergency triage procedures during mass casualty incidents
```

**Step 2: Configure Advanced Options**

**Timing Context**:
```
yearly
```

**Activation Trigger**:
```
Mass casualty incident with 50+ casualties or disaster declaration
```

**Process Owner**:
```
Emergency Operations Center Director
```

**Responsible Party**:
```
Incident Commander and Triage Team Lead
```

**Step 3: Generate**

Click "Generate Plan" and the system will:
1. Extract actions from all documents (guidelines always included)
2. Prioritize and assign actions
3. Modify vague timings to include "yearly" context
4. Include organizational metadata in the checklist specifications

### Example Output Differences

**Without Timing Context**:
```
Action: Review triage protocols regularly
Timeline: Long-term
```

**With Timing Context (yearly)**:
```
Action: Review triage protocols regularly
Timeline: As per yearly schedule
```

## Best Practices

### Timing Context
- Use consistent timing across your organization
- Match timing to your review cycles
- Consider regulatory requirements

### Activation Trigger
- Be specific about thresholds (e.g., "50+ casualties")
- Include measurable criteria
- Reference official declarations or protocols

### Process Owner
- Use official titles
- Ensure person/unit has authority
- Align with organizational structure

### Responsible Party
- Specify clear roles, not individuals
- Use standard terminology
- Consider on-call rotations

## Advanced Use Cases

### Case 1: Seasonal Flu Preparedness
```
Subject: Seasonal influenza response plan
Timing: seasonal (winter)
Trigger: Flu season declaration by public health authority
Process Owner: Public Health Director
Responsible Party: Infectious Disease Team Lead
```

### Case 2: Monthly Supply Chain Review
```
Subject: Medical supply chain management under sanctions
Timing: monthly
Trigger: Beginning of each month or supply shortage alert
Process Owner: Logistics Director
Responsible Party: Supply Chain Manager
```

### Case 3: Quarterly Drill Execution
```
Subject: Mass casualty incident simulation and drill
Timing: quarterly
Trigger: Scheduled drill date
Process Owner: Emergency Preparedness Coordinator
Responsible Party: Drill Exercise Manager
```

## Technical Notes

### Dictionary Access Restriction
- Main planning agents cannot access Dictionary.md
- Only translation/terminology agents access Dictionary.md
- This prevents terminology database interference with action extraction

### Guideline Documents
The following documents are always included (cannot be excluded):
- Comprehensive Health System Preparedness and Response Plan under Sanctions and War Conditions
- Checklist Template Guide
- National Health System Response Plan for Disasters and Emergencies_General Guides

### Timing Modification Logic
Actions are NOT modified if they contain:
- "hour", "minute", "day", "week", "month"
- "within", "after", "before", "during"
- Numeric ranges like "0-24", "1-7"
- "first", "second"

This preserves critical timing information while enhancing vague timings.

## Troubleshooting

### Issue: Timing not applied to actions
**Cause**: Actions have specific timeframes
**Solution**: This is expected - specific timings are preserved

### Issue: Missing organizational metadata
**Cause**: Fields left empty in UI
**Solution**: Fill in all desired fields before generating

### Issue: Cannot deselect guideline documents
**Cause**: By design - guidelines are always required
**Solution**: This is intentional for policy compliance

## Future Enhancements

Coming soon:
- Dynamic document selection from available corpus
- Role suggestion based on subject analysis
- Timing preset buttons (yearly, seasonal, monthly)
- CLI argument support for all parameters
- Batch generation with different configurations

## Support

For questions or issues:
1. Check this guide for common scenarios
2. Review IMPLEMENTATION_SUMMARY.md for technical details
3. Contact the development team

## Version
Enhanced Parameters v1.0 - October 2025

