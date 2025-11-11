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

### **2. Checklist Content by Responsible Actor**

{self._create_checklist_content(actions, tables)}

---
"""
        
        # Add formulas section if any formulas exist
        if formulas:
            plan += f"""
### **3. Relevant Formulas and Calculations**

{self._create_formulas_section(formulas)}

---
"""
        
        # Add tables/checklists section if any exist (only for non-action tables not already in actor sections)
        remaining_tables = [t for t in tables if t.get('table_type') != 'action_table']
        if remaining_tables:
            section_num = 4 if formulas else 3
            plan += f"""
### **{section_num}. Reference Tables and Checklists**

{self._create_tables_section(remaining_tables)}

---
"""
        
        # Add implementation approval section (renumber based on what's included)
        section_num = 3
        if formulas:
            section_num += 1
        if remaining_tables:
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
        num_actions = len(actions) if actions else 0
        
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
| **Number of Actions:** | {num_actions} |
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
    
    def _group_actions_by_actor(self, actions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group actions by responsible actor (who field).
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            Dictionary mapping actor names to their assigned actions
        """
        actions_by_actor = {}
        
        for action in actions:
            who = action.get('who', '').strip()
            
            # Handle missing or empty who field
            if not who or who.lower() in ['tbd', 'n/a', 'undefined']:
                who = "Unassigned"
            
            if who not in actions_by_actor:
                actions_by_actor[who] = []
            
            actions_by_actor[who].append(action)
        
        return actions_by_actor
    
    def _parse_timing(self, when: str) -> tuple:
        """
        Parse timing string to extract start time in minutes and priority weight.
        
        Args:
            when: Timing string (e.g., "0-30min", "Immediate", "first 2 hours")
            
        Returns:
            Tuple of (start_minutes, priority_weight) for sorting
        """
        import re
        
        if not when or not isinstance(when, str):
            return (999999, 3)  # Sort to end if no timing
        
        when_lower = when.lower().strip()
        
        # Priority weight mapping
        priority_weight = 2  # default to medium priority
        if any(word in when_lower for word in ['immediate', 'urgent', 'asap', 'critical']):
            priority_weight = 1
        elif any(word in when_lower for word in ['long-term', 'continuous', 'ongoing', 'sustained']):
            priority_weight = 3
        
        # Extract time in minutes
        start_minutes = 0
        
        # Match patterns like "0-30min", "30-60min", "1-2hr"
        range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*(min|hr|hour|h)', when_lower)
        if range_match:
            start_time = int(range_match.group(1))
            unit = range_match.group(3)
            if unit in ['hr', 'hour', 'h']:
                start_minutes = start_time * 60
            else:
                start_minutes = start_time
            return (start_minutes, priority_weight)
        
        # Match patterns like "30min", "2hr", "1 hour"
        single_match = re.search(r'(\d+)\s*(min|hr|hour|h)', when_lower)
        if single_match:
            time_val = int(single_match.group(1))
            unit = single_match.group(2)
            if unit in ['hr', 'hour', 'h']:
                start_minutes = time_val * 60
            else:
                start_minutes = time_val
            return (start_minutes, priority_weight)
        
        # Handle text descriptions
        if 'immediate' in when_lower or 'first 30' in when_lower:
            return (0, 1)
        elif 'first hour' in when_lower or 'within 1 hour' in when_lower:
            return (0, 1)
        elif 'first 2 hour' in when_lower or 'within 2 hour' in when_lower:
            return (30, 2)
        elif 'first day' in when_lower or 'within 24' in when_lower:
            return (120, 2)
        elif 'continuous' in when_lower or 'ongoing' in when_lower:
            return (0, 3)
        
        # Default: sort to middle
        return (60, priority_weight)
    
    def _sort_actions_by_timing(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort actions by timing (chronologically) and priority.
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            Sorted list of actions
        """
        def sort_key(action):
            when = action.get('when', '')
            start_minutes, priority_weight = self._parse_timing(when)
            
            # Get priority level from action
            priority_level = action.get('priority_level', 'short-term')
            priority_map = {
                'immediate': 1,
                'short-term': 2,
                'long-term': 3
            }
            priority_num = priority_map.get(priority_level, 2)
            
            # Sort by: (1) start time, (2) priority level, (3) priority weight from timing
            return (start_minutes, priority_num, priority_weight)
        
        return sorted(actions, key=sort_key)
    
    def _extract_actions_from_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract actions from tables marked as action tables.
        
        Args:
            tables: List of table dictionaries
            
        Returns:
            List of action dictionaries extracted from tables
        """
        extracted_actions = []
        
        for table in tables:
            table_type = table.get('table_type', '')
            
            # Only extract from action tables
            if table_type != 'action_table':
                continue
            
            headers = table.get('headers', [])
            rows = table.get('rows', [])
            table_title = table.get('table_title', '')
            
            # Try to infer actor from table title or context
            inferred_actor = self._infer_actor_from_table(table)
            
            # Find column indices for action fields
            action_col = self._find_column_index(headers, ['action', 'step', 'task', 'activity'])
            who_col = self._find_column_index(headers, ['who', 'responsible', 'actor', 'role'])
            when_col = self._find_column_index(headers, ['when', 'timing', 'deadline', 'timeframe'])
            
            # Extract actions from rows
            for row in rows:
                if not row or len(row) == 0:
                    continue
                
                action_text = row[action_col] if action_col < len(row) else ''
                who = row[who_col] if who_col is not None and who_col < len(row) else inferred_actor
                when = row[when_col] if when_col is not None and when_col < len(row) else 'TBD'
                
                if action_text and str(action_text).strip():
                    extracted_actions.append({
                        'action': str(action_text).strip(),
                        'who': str(who).strip() if who else inferred_actor,
                        'when': str(when).strip(),
                        'what': '',
                        'priority_level': 'short-term',
                        'sources': [f"Table: {table_title}"],
                        'from_table': True
                    })
        
        logger.info(f"Extracted {len(extracted_actions)} actions from tables")
        return extracted_actions
    
    def _infer_actor_from_table(self, table: Dict[str, Any]) -> str:
        """
        Infer the responsible actor from table context and title.
        
        Args:
            table: Table dictionary
            
        Returns:
            Inferred actor name or "Unassigned"
        """
        table_title = table.get('table_title', '').lower()
        reference = table.get('reference', {})
        node_title = reference.get('node_title', '').lower()
        
        # Common patterns in titles
        patterns = {
            'icu': 'Head of ICU',
            'emergency': 'Emergency Response Coordinator',
            'surgical': 'Surgical Team Lead',
            'triage': 'Triage Officer',
            'pharmacy': 'Pharmacy Director',
            'nursing': 'Head Nurse',
            'laboratory': 'Laboratory Director',
            'radiology': 'Radiology Department Head',
            'administration': 'Hospital Administrator',
            'director': 'Hospital Director'
        }
        
        # Check title and node title for patterns
        for pattern, actor in patterns.items():
            if pattern in table_title or pattern in node_title:
                return actor
        
        return "Unassigned"
    
    def _find_column_index(self, headers: List[str], possible_names: List[str]) -> int:
        """
        Find column index by matching against possible column names.
        
        Args:
            headers: List of column headers
            possible_names: List of possible names for this column
            
        Returns:
            Column index or None if not found
        """
        if not headers:
            return None
        
        headers_lower = [str(h).lower().strip() for h in headers]
        
        for name in possible_names:
            if name in headers_lower:
                return headers_lower.index(name)
        
        # Return first column as default for action column, None for others
        if 'action' in possible_names or 'step' in possible_names:
            return 0
        return None
    
    def _identify_reference_tables(
        self, 
        tables: List[Dict[str, Any]], 
        actions_by_actor: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify reference tables (non-action tables) and map them to relevant actors.
        
        Args:
            tables: List of all tables
            actions_by_actor: Dictionary mapping actors to their actions
            
        Returns:
            Dictionary mapping actor names to their relevant reference tables
        """
        reference_tables_by_actor = {}
        
        for table in tables:
            table_type = table.get('table_type', '')
            
            # Skip action tables (they've been extracted)
            if table_type == 'action_table':
                continue
            
            table_title = table.get('table_title', '').lower()
            
            # Try to match table to actors based on keywords
            matched_actors = []
            
            for actor, actions in actions_by_actor.items():
                # Check if any action from this actor references this table
                for action in actions:
                    action_text = action.get('action', '').lower()
                    if table_title in action_text or self._table_matches_action(table, action):
                        matched_actors.append(actor)
                        break
            
            # If no specific match, try keyword matching
            if not matched_actors:
                matched_actors = self._match_table_to_actors_by_keywords(table, actions_by_actor)
            
            # Add table to matched actors
            for actor in matched_actors:
                if actor not in reference_tables_by_actor:
                    reference_tables_by_actor[actor] = []
                reference_tables_by_actor[actor].append(table)
        
        return reference_tables_by_actor
    
    def _table_matches_action(self, table: Dict[str, Any], action: Dict[str, Any]) -> bool:
        """
        Check if a table is relevant to a specific action.
        
        Args:
            table: Table dictionary
            action: Action dictionary
            
        Returns:
            True if table is relevant to action
        """
        table_title = table.get('table_title', '').lower()
        table_type = table.get('table_type', '').lower()
        action_text = action.get('action', '').lower()
        action_what = action.get('what', '').lower()
        
        # Check for direct mention of table title
        if table_title and table_title in action_text:
            return True
        
        # Check for type-based keywords
        type_keywords = {
            'checklist': ['checklist', 'protocol', 'procedure'],
            'decision_matrix': ['matrix', 'decision', 'criteria', 'prioritize', 'triage'],
            'other': ['template', 'form', 'reference', 'guide']
        }
        
        keywords = type_keywords.get(table_type, [])
        for keyword in keywords:
            if keyword in action_text or keyword in action_what:
                return True
        
        return False
    
    def _match_table_to_actors_by_keywords(
        self, 
        table: Dict[str, Any], 
        actions_by_actor: Dict[str, List[Dict[str, Any]]]
    ) -> List[str]:
        """
        Match table to actors based on keyword analysis.
        
        Args:
            table: Table dictionary
            actions_by_actor: Dictionary mapping actors to actions
            
        Returns:
            List of actor names that match
        """
        table_title = table.get('table_title', '').lower()
        reference = table.get('reference', {})
        node_title = reference.get('node_title', '').lower()
        
        matched_actors = []
        
        # Extract keywords from table
        table_text = f"{table_title} {node_title}"
        
        for actor in actions_by_actor.keys():
            actor_lower = actor.lower()
            
            # Check for actor name in table text
            actor_keywords = actor_lower.split()
            for keyword in actor_keywords:
                if len(keyword) > 3 and keyword in table_text:
                    matched_actors.append(actor)
                    break
        
        return matched_actors
    
    def _generate_appendix_title(self, table: Dict[str, Any]) -> str:
        """
        Generate a professional title for an appendix.
        
        Args:
            table: Table dictionary
            
        Returns:
            Professional appendix title
        """
        table_title = table.get('table_title', 'Reference Table')
        table_type = table.get('table_type', 'other')
        
        # If title is already professional, use it
        if table_title and not table_title.startswith('Table'):
            return table_title
        
        # Generate based on type
        type_labels = {
            'checklist': 'Checklist',
            'decision_matrix': 'Decision Matrix',
            'action_table': 'Action Table',
            'other': 'Reference Table'
        }
        
        label = type_labels.get(table_type, 'Reference Table')
        
        if table_title and table_title != 'Reference Table':
            return f"{table_title}"
        
        return label
    
    def _format_appendix(
        self, 
        appendix: Dict[str, Any], 
        appendix_id: str, 
        related_action_numbers: List[int]
    ) -> str:
        """
        Format an appendix with table content and metadata.
        
        Args:
            appendix: Table/appendix dictionary
            appendix_id: Appendix identifier (e.g., "A", "B", "C")
            related_action_numbers: List of action numbers that reference this appendix
            
        Returns:
            Formatted markdown appendix section
        """
        title = self._generate_appendix_title(appendix)
        
        content = f"\n#### Appendix {appendix_id}: {title}\n\n"
        
        # Add table content
        markdown_content = appendix.get('markdown_content', '')
        headers = appendix.get('headers', [])
        rows = appendix.get('rows', [])
        
        if markdown_content:
            content += markdown_content + "\n\n"
        elif headers and rows:
            # Generate markdown table
            content += "| " + " | ".join(str(h) for h in headers) + " |\n"
            content += "| " + " | ".join(["---"] * len(headers)) + " |\n"
            for row in rows:
                content += "| " + " | ".join(str(cell) for cell in row) + " |\n"
            content += "\n"
        else:
            content += "*Table content not available*\n\n"
        
        # Add reference information
        reference = appendix.get('reference', {})
        doc = reference.get('document', 'Source document')
        line_range = reference.get('line_range', 'N/A')
        
        content += f"**Reference**: {doc} ({line_range})\n"
        
        # Add related actions
        if related_action_numbers:
            action_refs = ", ".join(f"#{num}" for num in related_action_numbers)
            content += f"**Related Actions**: {action_refs}\n"
        
        return content
    
    def _link_actions_to_appendices(
        self, 
        actions: List[Dict[str, Any]], 
        tables: List[Dict[str, Any]]
    ) -> Dict[int, List[str]]:
        """
        Create mapping between actions and appendices they reference.
        
        Args:
            actions: List of actions
            tables: List of reference tables
            
        Returns:
            Dictionary mapping action index to list of appendix IDs
        """
        links = {}
        
        # Create table title index
        table_titles = {}
        for idx, table in enumerate(tables):
            if table.get('table_type') != 'action_table':
                table_titles[table.get('table_title', '').lower()] = idx
        
        # Check each action for table references
        for action_idx, action in enumerate(actions):
            action_text = action.get('action', '').lower()
            action_what = action.get('what', '').lower()
            
            referenced_tables = []
            
            for title_lower, table_idx in table_titles.items():
                if title_lower and (title_lower in action_text or title_lower in action_what):
                    referenced_tables.append(table_idx)
            
            if referenced_tables:
                links[action_idx] = referenced_tables
        
        return links

    def _create_checklist_content(
        self, 
        actions: List[Dict[str, Any]], 
        tables: List[Dict[str, Any]] = None
    ) -> str:
        """
        Create the Checklist Content section organized by actor.
        
        Args:
            actions: List of assigned actions
            tables: List of tables (for extraction and appendices)
            
        Returns:
            Formatted checklist content organized by responsible actor
        """
        if tables is None:
            tables = []
        
        # Step 1: Extract actions from action tables
        table_actions = self._extract_actions_from_tables(tables)
        
        # Step 2: Merge table actions with main actions
        all_actions = actions + table_actions
        
        if not all_actions:
            return "*No actions available.*\n"
        
        # Step 3: Group actions by actor
        actions_by_actor = self._group_actions_by_actor(all_actions)
        
        # Step 4: Sort actions within each actor group
        for actor in actions_by_actor:
            actions_by_actor[actor] = self._sort_actions_by_timing(actions_by_actor[actor])
        
        # Step 5: Identify reference tables for each actor
        reference_tables_by_actor = self._identify_reference_tables(tables, actions_by_actor)
        
        # Step 6: Build content - organized actors, then Unassigned last
        content = ""
        
        # Sort actors alphabetically, but keep Unassigned for last
        sorted_actors = sorted([a for a in actions_by_actor.keys() if a != "Unassigned"])
        if "Unassigned" in actions_by_actor:
            sorted_actors.append("Unassigned")
        
        # Format each actor section
        for actor in sorted_actors:
            actor_actions = actions_by_actor[actor]
            actor_appendices = reference_tables_by_actor.get(actor, [])
            
            content += self._format_actor_section(actor, actor_actions, actor_appendices)
            content += "\n"
        
        return content

    def _format_action_table(
        self, 
        actions: List[Dict[str, Any]], 
        appendix_refs: Dict[int, str] = None
    ) -> str:
        """
        Formats a list of actions into a markdown table with timeline and appendix references.
        
        Args:
            actions: List of action dictionaries
            appendix_refs: Optional mapping of action index to appendix reference text
            
        Returns:
            Formatted markdown table
        """
        if appendix_refs is None:
            appendix_refs = {}
        
        header = """
| No. | Action | Timeline | Status | Remarks |
| :-- | :--- | :--- | :--- | :--- |
"""
        rows = []
        if not actions:
            rows.append("| | | | | |")

        for i, action in enumerate(actions, 1):
            action_text = action.get('action', 'N/A')
            
            # Add appendix reference if exists
            if i - 1 in appendix_refs:
                action_text += f" {appendix_refs[i - 1]}"
            
            timeline = action.get('when', 'TBD')
            rows.append(f"| {i} | {action_text} | {timeline} | | |")
            
        return header + "\n".join(rows)
    
    def _format_actor_section(
        self, 
        actor: str, 
        actions: List[Dict[str, Any]], 
        appendices: List[Dict[str, Any]]
    ) -> str:
        """
        Format a complete actor section with actions and appendices.
        
        Args:
            actor: Actor/role name
            actions: List of actions for this actor
            appendices: List of appendices for this actor
            
        Returns:
            Formatted markdown section for the actor
        """
        content = f"\n### {actor}\n\n"
        
        # Build appendix references for actions
        appendix_refs = {}
        appendix_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 
                           'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
        
        # Create mapping of table to appendix ID
        appendix_map = {}
        for idx, appendix in enumerate(appendices):
            if idx < len(appendix_letters):
                appendix_id = appendix_letters[idx]
                appendix_map[id(appendix)] = appendix_id
        
        # Check which actions reference which appendices
        for action_idx, action in enumerate(actions):
            action_text = action.get('action', '').lower()
            action_what = action.get('what', '').lower()
            
            referenced_appendices = []
            for appendix in appendices:
                table_title = appendix.get('table_title', '').lower()
                if table_title and (table_title in action_text or table_title in action_what):
                    appendix_id = appendix_map.get(id(appendix))
                    if appendix_id:
                        referenced_appendices.append(appendix_id)
            
            if referenced_appendices:
                refs_text = ", ".join(f"Appendix {aid}" for aid in referenced_appendices)
                appendix_refs[action_idx] = f"(See {refs_text})"
        
        # Format actions table
        content += self._format_action_table(actions, appendix_refs)
        content += "\n"
        
        # Add appendices if any
        if appendices:
            for idx, appendix in enumerate(appendices):
                if idx < len(appendix_letters):
                    appendix_id = appendix_letters[idx]
                    
                    # Find which actions reference this appendix
                    related_actions = []
                    for action_idx, action in enumerate(actions):
                        if action_idx in appendix_refs:
                            if appendix_id in appendix_refs[action_idx]:
                                related_actions.append(action_idx + 1)
                    
                    content += self._format_appendix(appendix, appendix_id, related_actions)
                    content += "\n"
        
        content += "---\n"
        return content
    
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

