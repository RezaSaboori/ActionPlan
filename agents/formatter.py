"""Formatter Agent for creating final action plan documents."""

import logging
from typing import Dict, Any, List
from datetime import datetime
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class FormatterAgent:
    """Formatter agent for compiling final action plan."""
    
    def __init__(self, llm_client: LLMClient, markdown_logger=None):
        """
        Initialize Formatter Agent.
        
        Args:
            llm_client: Ollama client instance
            markdown_logger: Optional MarkdownLogger instance
        """
        self.llm = llm_client
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("formatter")
        logger.info("Initialized FormatterAgent")
    
    def execute(self, data: Dict[str, Any]) -> str:
        """
        Execute formatter logic.
        
        Args:
            data: Dictionary containing assigned actions, context, and user parameters
            
        Returns:
            Formatted markdown action plan
        """
        logger.info("Formatter creating final action plan")
        
        subject = data.get("subject", "Health Emergency Action Plan")
        assigned_actions = data.get("assigned_actions", [])
        context = data.get("rules_context", {})
        
        # Extract user-specified parameters
        trigger = data.get("trigger")
        responsible_party = data.get("responsible_party")
        process_owner = data.get("process_owner")
        
        # Add to context metadata
        if not context:
            context = {}
        if "metadata" not in context:
            context["metadata"] = {}
        
        if trigger:
            context["metadata"]["activation_trigger"] = trigger
        if responsible_party:
            context["metadata"]["responsible_party"] = responsible_party
        if process_owner:
            context["metadata"]["process_owner"] = process_owner
        
        # Generate plan sections
        plan = self._format_checklist(subject, assigned_actions, context)
        
        logger.info("Formatter completed action plan generation")
        return plan
    
    def _format_checklist(
        self,
        subject: str,
        actions: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> str:
        """Format the complete action checklist."""
        
        plan = f"""### **1. Checklist Specifications** 

{self._create_checklist_specifications(subject, context)}

---

### **2. Executive Steps** 

{self._create_executive_steps(actions)}

---

### **3. Checklist Content by Executive Steps**

{self._create_checklist_content(actions)}

---

### **4.Implementation Approval**

{self._create_implementation_approval()}
"""
        
        return plan

    def _create_checklist_specifications(self, subject: str, context: Dict[str, Any]) -> str:
        """Create the Checklist Specifications table."""
        metadata = context.get("metadata", {})
        
        table = f"""
| Field | Description |
| :--- | :--- |
| **Checklist Name:** | {subject} |
| **Relevant Department/Jurisdiction:** | {metadata.get("jurisdiction", "...")} |
| **Crisis Area:** | {metadata.get("crisis_area", "...")} |
| **Checklist Type:** | {metadata.get("checklist_type", "Action (Response)")} |
| **Reference Protocol(s):** | {metadata.get("reference_protocols", "...")} |
| **Operational Setting:** | {metadata.get("operational_setting", "...")} |
| **Process Owner:** | {metadata.get("process_owner", "...")} |
| **Acting Individual(s)/Responsible Party:** | {metadata.get("responsible_party", "...")} |
| **Incident Commander:** | {metadata.get("incident_commander", "...")} |
| **Checklist Activation Trigger:** | {metadata.get("activation_trigger", "...")} |
| **Checklist Objective:** | {metadata.get("objective", "...")} |
| **Number of Executive Steps:** | ... |
| **Document Code (Proposed):** | *Do not complete this section* |
| **Last Updated:** | *Do not complete this section* |
"""
        return table

    def _create_executive_steps(self, actions: List[Dict[str, Any]]) -> str:
        """Create the Executive Steps table."""
        header = """
| Executive Step | Responsible for Implementation | Deadline/Timeframe |
| :--- | :--- | :--- |
"""
        rows = []
        if not actions:
            rows.append("| | | |")

        for action in actions:
            step = action.get('action', 'N/A')
            responsible = action.get('who', 'TBD')
            deadline = action.get('when', 'TBD')
            rows.append(f"| {step} | {responsible} | {deadline} |")
            
        return header + "\n".join(rows)

    def _create_checklist_content(self, actions: List[Dict[str, Any]]) -> str:
        """Create the Checklist Content section."""
        immediate_actions = [a for a in actions if a.get("priority_level") == "immediate"]
        urgent_actions = [a for a in actions if a.get("priority_level") == "short-term"]
        continuous_actions = [a for a in actions if a.get("priority_level") == "long-term"]

        content = "#### **Part 1: Immediate Actions (e.g., first 30 minutes)**\n"
        content += "**Assigned to:** ...\n\n"
        content += self._format_action_table(immediate_actions)
        content += "\n"
        
        content += "#### **Part 2: Urgent Actions (e.g., first 2 hours)**\n"
        content += "**Assigned to:** ...\n\n"
        content += self._format_action_table(urgent_actions)
        content += "\n---\n\n"

        content += "#### **Part 3: Continuous Actions**\n"
        content += "**Assigned to:** ...\n\n"
        content += self._format_action_table(continuous_actions)
        
        return content

    def _format_action_table(self, actions: List[Dict[str, Any]]) -> str:
        """Formats a list of actions into a markdown table."""
        header = """
| No. | Action | Status | Remarks/Report |
| :-- | :--- | :--- | :--- |
"""
        rows = []
        if not actions:
            rows.append("| | | | |")

        for i, action in enumerate(actions, 1):
            rows.append(f"| {i} | {action.get('action', 'N/A')} | | |")
            
        return header + "\n".join(rows)
    
    def _create_implementation_approval(self) -> str:
        """Create the Implementation Approval table."""
        table = """
| Role | Full Name | Date and Time | Signature |
| :--- | :--- | :--- | :--- |
| **Lead Responder:** | ... | ... | ... |
| **Incident Commander:** | ... | ... | ... |
"""
        return table

