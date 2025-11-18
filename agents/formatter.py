"""Formatter Agent for creating final action plan documents."""

import logging
from typing import Dict, Any, List
from datetime import datetime
from config.prompts import get_prompt
from utils.llm_client import LLMClient

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
        
        Generates final formatted output with actions and tables.
        Note: Formulas are now integrated directly into action descriptions.
        
        Args:
            data: Dictionary containing:
                - assigned_actions: Actions from deduplicator (refined_actions) with role assignments
                - tables: List of table/checklist objects (from deduplicator)
                - formatted_output: Pre-formatted output from extractor (optional, deprecated)
                - rules_context: Rules and context information
                - problem_statement: Problem/objective statement
                - user_config: User configuration
            
        Returns:
            Formatted markdown action plan with integrated tables
        """
        logger.info("Formatter creating final action plan")
        
        subject = data.get("subject", "Health Emergency Action Plan")
        assigned_actions = data.get("assigned_actions", [])
        tables = data.get("tables", [])
        formatted_output = data.get("formatted_output", "")
        context = data.get("rules_context", {})
        
        # Extract problem statement and user config
        problem_statement = data.get("problem_statement", "")
        user_config = data.get("user_config", {})
        
        # Validate and normalize actions from deduplicator
        assigned_actions = self._validate_and_normalize_actions(assigned_actions)
        
        logger.info(f"Formatter input: {len(assigned_actions)} actions, {len(tables)} tables")
        
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
        plan = self._format_checklist(subject, assigned_actions, context, problem_statement, user_config, tables, formatted_output)
        
        logger.info("Formatter completed action plan generation")
        return plan
    
    def _format_checklist(
        self,
        subject: str,
        actions: List[Dict[str, Any]],
        context: Dict[str, Any],
        problem_statement: str = "",
        user_config: Dict[str, Any] = None,
        tables: List[Dict[str, Any]] = None,
        formatted_output: str = ""
    ) -> str:
        """Format the complete action checklist with tables. Formulas are integrated into actions."""
        
        if user_config is None:
            user_config = {}
        if tables is None:
            tables = []
        
        plan = f"""### **1. Checklist Specifications** 

{self._create_checklist_specifications(subject, actions, context, problem_statement, user_config)}

---

### **2. Checklist Content by Responsible Actor**

{self._create_checklist_content(actions, tables)}

---
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

    def _validate_and_normalize_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate and normalize actions from deduplicator output.
        
        Ensures all actions have required fields and handles merged actions properly.
        
        Args:
            actions: List of action dictionaries from deduplicator
            
        Returns:
            Validated and normalized list of actions
        """
        validated_actions = []
        
        for idx, action in enumerate(actions):
            if not isinstance(action, dict):
                logger.warning(f"Action at index {idx} is not a dictionary, skipping")
                continue
            
            # Ensure required fields exist with defaults
            normalized_action = {
                'id': action.get('id', f'action_{idx}'),
                'action': action.get('action', 'N/A'),
                'who': action.get('who', '').strip() if action.get('who') else '',
                'when': action.get('when', 'TBD'),
                'reference': action.get('reference', {}),
            }
            
            # Preserve optional fields (merged_from, merge_rationale, flags, etc.)
            for key in ['merged_from', 'merge_rationale', 'timing_flagged', 'actor_flagged']:
                if key in action:
                    normalized_action[key] = action[key]
            
            # Normalize 'who' field to match deduplicator's "Undefined Actor"
            # Deduplicator uses "Undefined Actor", formatter uses "Unassigned" for consistency
            who = normalized_action['who']
            if not who or who.lower() in ['tbd', 'n/a', 'undefined', 'unknown', 'undefined actor', '']:
                normalized_action['who'] = "Unassigned"
            
            # Ensure reference is a dict
            if not isinstance(normalized_action['reference'], dict):
                normalized_action['reference'] = {}
            
            validated_actions.append(normalized_action)
        
        return validated_actions
    
    def _group_actions_by_actor(self, actions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group actions by responsible actor (who field).
        
        Compatible with deduplicator output which may have "Undefined Actor" or empty who fields.
        
        Args:
            actions: List of action dictionaries (should be validated first)
            
        Returns:
            Dictionary mapping actor names to their assigned actions
        """
        actions_by_actor = {}

        for action in actions:
            who = action.get('who', '').strip()
            
            # Handle missing or empty who field (consistent with deduplicator)
            if not who or who.lower() in ['tbd', 'n/a', 'undefined', 'unknown', 'undefined actor', '']:
                who = "Unassigned"
            
            if who not in actions_by_actor:
                actions_by_actor[who] = []
            
            actions_by_actor[who].append(action)
        
        return actions_by_actor
    
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
            if keyword in action_text:
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
            
            referenced_tables = []
            
            for title_lower, table_idx in table_titles.items():
                if title_lower and title_lower in action_text:
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
        
        if not actions:
            return "*No actions available.*\n"
        
        # Step 3: Group actions by actor
        actions_by_actor = self._group_actions_by_actor(actions)
        
        # Step 4: Sort actions within each actor group
        for actor in actions_by_actor:
            # The _parse_timing and _sort_actions_by_timing methods are removed,
            # so we'll just sort by action text for now, or remove if no sorting is needed.
            # For now, we'll keep the structure but acknowledge the missing logic.
            # If sorting by timing is required, this method needs to be re-implemented
            # or the actions need to be pre-sorted.
            pass # No sorting by timing as _parse_timing and _sort_actions_by_timing are removed
        
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
| No. | ID | Action | Timeline | Reference | Status | Remarks |
| :-- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        rows = []
        if not actions:
            rows.append("| | | | | | | |")

        for i, action in enumerate(actions, 1):
            action_text = action.get('action', 'N/A')
            action_id = action.get('id', 'N/A')
            reference_obj = action.get('reference', {})
            
            # Handle reference safely (may be empty dict or missing)
            if isinstance(reference_obj, dict):
                doc = reference_obj.get('document', 'Unknown')
                line_range = reference_obj.get('line_range', 'N/A')
                reference = f"{doc} (lines {line_range})" if doc != 'Unknown' else "N/A"
            else:
                reference = "N/A"

            # Add appendix reference if exists
            if i - 1 in appendix_refs:
                action_text += f" {appendix_refs[i - 1]}"
            
            # Handle merged actions - add note if merged
            merged_from = action.get('merged_from', [])
            if merged_from and isinstance(merged_from, list) and len(merged_from) > 0:
                # Note: merged actions are already consolidated, just preserve the info
                pass
            
            timeline = action.get('when', 'TBD')
            rows.append(f"| {i} | {action_id} | {action_text} | {timeline} | {reference} | | |")
            
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
            
            referenced_appendices = []
            for appendix in appendices:
                table_title = appendix.get('table_title', '').lower()
                if table_title and table_title in action_text:
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

