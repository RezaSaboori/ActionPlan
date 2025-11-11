"""Formatter Agent for creating final action plan documents."""

import logging
from typing import Dict, Any, List
from datetime import datetime
from utils.llm_client import LLMClient
from config.prompts import get_prompt

logger = logging.getLogger(__name__)


class FormatterAgent:
    """Formatter agent for compiling final action plan."""
    
    def __init__(self, agent_name: str, dynamic_settings, markdown_logger=None):
        """
        Initialize Formatter Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("formatter")
        logger.info(f"Initialized FormatterAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> str:
        """
        Execute formatter logic.
        
        Enhanced to integrate formulas, tables, and references from extractor.
        
        Args:
            data: Dictionary containing:
                - assigned_actions: Actions with role assignments
                - formulas: List of formula objects with computations
                - tables: List of table/checklist objects
                - formatted_output: Pre-formatted output from extractor (optional)
                - context: Rules and context information
                - problem_statement: Problem/objective statement
                - user_config: User configuration
            
        Returns:
            Formatted markdown action plan with integrated formulas and tables
        """
        logger.info("Formatter creating final action plan")
        
        subject = data.get("subject", "Health Emergency Action Plan")
        assigned_actions = data.get("assigned_actions", [])
        formulas = data.get("formulas", [])
        tables = data.get("tables", [])
        formatted_output = data.get("formatted_output", "")
        context = data.get("rules_context", {})
        
        # Extract problem statement and user config
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        
        logger.info(f"Formatter input: {len(assigned_actions)} actions, {len(formulas)} formulas, {len(tables)} tables")
        
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
        plan = self._format_checklist(subject, assigned_actions, context, problem_statement, user_config, formulas, tables, formatted_output)
        
        logger.info("Formatter completed action plan generation")
        return plan
    
    def _format_checklist(
        self,
        subject: str,
        actions: List[Dict[str, Any]],
        context: Dict[str, Any],
        problem_statement: str = "",
        user_config: Dict[str, Any] = None,
        formulas: List[Dict[str, Any]] = None,
        tables: List[Dict[str, Any]] = None,
        formatted_output: str = ""
    ) -> str:
        """Format the complete action checklist with formulas and tables."""
        
        if user_config is None:
            user_config = {}
        if formulas is None:
            formulas = []
        if tables is None:
            tables = []
        
        plan = f"""### **1. Checklist Specifications** 

{self._create_checklist_specifications(subject, actions, context, problem_statement, user_config)}

---

### **2. Executive Steps** 

{self._create_executive_steps(actions)}

---

### **3. Checklist Content by Executive Steps**

{self._create_checklist_content(actions)}

---
"""
        
        # Add formulas section if any formulas exist
        if formulas:
            plan += f"""
### **4. Relevant Formulas and Calculations**

{self._create_formulas_section(formulas)}

---
"""
        
        # Add tables/checklists section if any exist
        if tables:
            plan += f"""
### **5. Reference Tables and Checklists**

{self._create_tables_section(tables)}

---
"""
        
        # Add implementation approval section (renumber based on what's included)
        section_num = 4
        if formulas:
            section_num += 1
        if tables:
            section_num += 1
        
        plan += f"""
### **{section_num}. Implementation Approval**

{self._create_implementation_approval()}
"""
        
        # Optionally add formatted extractor output as an appendix
        if formatted_output:
            plan += f"""

---

### **Appendix: Detailed Extraction Report**

{formatted_output}
"""
        
        return plan

    def _create_checklist_specifications(
        self, 
        subject: str, 
        actions: List[Dict[str, Any]],
        context: Dict[str, Any],
        problem_statement: str = "",
        user_config: Dict[str, Any] = None
    ) -> str:
        """Create the Checklist Specifications table with auto-populated fields."""
        if user_config is None:
            user_config = {}
        
        metadata = context.get("metadata", {})
        
        # Extract organizational level, phase, and subject from user_config
        level = user_config.get("level", "center")
        phase = user_config.get("phase", "response")
        crisis_subject = user_config.get("subject", "war")
        
        # Auto-populate fields using helper methods
        department_jurisdiction = self._extract_department_jurisdiction(actions)
        crisis_area = self._map_crisis_area(crisis_subject)
        checklist_type = self._map_checklist_type(phase)
        process_owner = self._get_department_from_level(level)
        responsible_parties = self._extract_unique_roles(actions)
        incident_commander = self._get_incident_commander_from_level(level)
        checklist_objective = problem_statement if problem_statement else metadata.get("objective", "...")
        num_executive_steps = len(actions) if actions else 0
        
        # Use metadata values if they exist, otherwise use auto-populated values
        table = f"""
| Field | Description |
| :--- | :--- |
| **Checklist Name:** | {subject} |
| **Relevant Department/Jurisdiction:** | {metadata.get("jurisdiction", department_jurisdiction)} |
| **Crisis Area:** | {metadata.get("crisis_area", crisis_area)} |
| **Checklist Type:** | {metadata.get("checklist_type", checklist_type)} |
| **Reference Protocol(s):** | {metadata.get("reference_protocols", "...")} |
| **Operational Setting:** | {metadata.get("operational_setting", "...")} |
| **Process Owner:** | {metadata.get("process_owner", process_owner)} |
| **Acting Individual(s)/Responsible Party:** | {metadata.get("responsible_party", responsible_parties)} |
| **Incident Commander:** | {metadata.get("incident_commander", incident_commander)} |
| **Checklist Activation Trigger:** | {metadata.get("activation_trigger", "...")} |
| **Checklist Objective:** | {checklist_objective} |
| **Number of Executive Steps:** | {num_executive_steps} |
| **Document Code (Proposed):** | *Do not complete this section* |
| **Last Updated:** | *Do not complete this section* |
"""
        return table
    
    def _extract_unique_roles(self, actions: List[Dict[str, Any]]) -> str:
        """
        Extract all unique 'who' roles from assigned actions.
        
        Args:
            actions: List of assigned actions
            
        Returns:
            Comma-separated string of unique roles
        """
        roles = set()
        for action in actions:
            who = action.get('who', '').strip()
            if who and who != 'TBD':
                roles.add(who)
        
        if not roles:
            return "..."
        
        # Sort and join with commas
        sorted_roles = sorted(roles)
        return ", ".join(sorted_roles)
    
    def _extract_department_jurisdiction(self, actions: List[Dict[str, Any]]) -> str:
        """
        Extract department/jurisdiction from assigned actions based on the most common roles.
        
        Args:
            actions: List of assigned actions
            
        Returns:
            Department or jurisdiction name
        """
        if not actions:
            return "..."
        
        # Extract all roles
        roles = [action.get('who', '') for action in actions if action.get('who')]
        
        if not roles:
            return "..."
        
        # Try to identify the most senior department mentioned
        role_text = " ".join(roles).lower()
        
        # Check for ministry-level departments
        if "minister" in role_text or "ministry" in role_text:
            return "Ministry of Health"
        elif "general directorate" in role_text or "director general" in role_text:
            return "General Directorate"
        elif "vice-chancellor" in role_text or "university" in role_text:
            return "University Administration"
        elif "hospital" in role_text or "center" in role_text:
            return "Health Center/Hospital"
        
        # Default: use the most common role as the department
        return roles[0] if roles else "..."
    
    def _get_department_from_level(self, level: str) -> str:
        """
        Map organizational level to process owner (department).
        
        Args:
            level: Organizational level (ministry/university/center)
            
        Returns:
            Department name
        """
        mapping = {
            "ministry": "General Directorate",
            "university": "Vice-Chancellor's Office",
            "center": "Hospital Management"
        }
        return mapping.get(level, "...")
    
    def _get_incident_commander_from_level(self, level: str) -> str:
        """
        Map organizational level to incident commander (job title).
        
        Args:
            level: Organizational level (ministry/university/center)
            
        Returns:
            Job title for incident commander
        """
        mapping = {
            "ministry": "Director General",
            "university": "Vice-Chancellor",
            "center": "Hospital Director"
        }
        return mapping.get(level, "...")
    
    def _map_crisis_area(self, subject: str) -> str:
        """
        Map crisis subject to crisis area label.
        
        Args:
            subject: Crisis subject (war/sanction)
            
        Returns:
            Crisis area label
        """
        mapping = {
            "war": "War / Mass Casualty Incidents",
            "sanction": "Sanctions"
        }
        return mapping.get(subject, "...")
    
    def _map_checklist_type(self, phase: str) -> str:
        """
        Map phase to checklist type label.
        
        Args:
            phase: Plan phase (preparedness/response)
            
        Returns:
            Checklist type label
        """
        mapping = {
            "preparedness": "Preparedness",
            "response": "Action (Response)"
        }
        return mapping.get(phase, "Action (Response)")

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
    
    def _create_formulas_section(self, formulas: List[Dict[str, Any]]) -> str:
        """
        Create a formatted section for formulas with computation examples.
        
        Args:
            formulas: List of formula objects with computation examples and references
            
        Returns:
            Formatted markdown section with all formulas
        """
        if not formulas:
            return "*No formulas extracted.*"
        
        content = "This section contains all mathematical formulas, calculations, and quantitative methods extracted from the source documents.\n\n"
        
        for idx, formula_obj in enumerate(formulas, 1):
            formula = formula_obj.get("formula", "N/A")
            computation = formula_obj.get("computation_example", "N/A")
            result = formula_obj.get("sample_result", "N/A")
            formula_context = formula_obj.get("formula_context", "N/A")
            reference = formula_obj.get("reference", {})
            
            # Extract reference details
            doc = reference.get("document", "Unknown")
            line_range = reference.get("line_range", "Unknown")
            node_title = reference.get("node_title", "")
            
            content += f"""
#### **Formula {idx}: {formula_context}**

**Formula:**
```
{formula}
```

**Example Computation:**
```
{computation}
```

**Sample Result:** `{result}`

**Source Reference:** {doc} ({line_range})"""
            
            if node_title:
                content += f" - Section: {node_title}"
            
            content += "\n\n---\n"
        
        return content
    
    def _create_tables_section(self, tables: List[Dict[str, Any]]) -> str:
        """
        Create a formatted section for tables and checklists.
        
        Args:
            tables: List of table objects with structure and references
            
        Returns:
            Formatted markdown section with all tables
        """
        if not tables:
            return "*No tables or checklists extracted.*"
        
        content = "This section contains all tables, checklists, and structured data extracted from the source documents.\n\n"
        
        for idx, table_obj in enumerate(tables, 1):
            title = table_obj.get("table_title", f"Table {idx}")
            table_type = table_obj.get("table_type", "other")
            headers = table_obj.get("headers", [])
            rows = table_obj.get("rows", [])
            markdown_content = table_obj.get("markdown_content", "")
            reference = table_obj.get("reference", {})
            
            # Extract reference details
            doc = reference.get("document", "Unknown")
            line_range = reference.get("line_range", "Unknown")
            node_title = reference.get("node_title", "")
            
            # Type badge
            type_badge = {
                "checklist": "📋 CHECKLIST",
                "action_table": "✅ ACTION TABLE",
                "decision_matrix": "🔀 DECISION MATRIX",
                "other": "📊 TABLE"
            }.get(table_type, "📊 TABLE")
            
            content += f"""
#### **{type_badge}: {title}**

"""
            # Use provided markdown content or generate from structure
            if markdown_content:
                content += markdown_content + "\n"
            elif headers and rows:
                # Generate markdown table
                content += "| " + " | ".join(headers) + " |\n"
                content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                for row in rows:
                    content += "| " + " | ".join(str(cell) for cell in row) + " |\n"
                content += "\n"
            else:
                content += "*Table structure not available*\n\n"
            
            content += f"""
**Source Reference:** {doc} ({line_range})"""
            
            if node_title:
                content += f" - Section: {node_title}"
            
            content += "\n\n---\n"
        
        return content

