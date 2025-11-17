"""De-duplicator and Merger Agent for action consolidation."""

import logging
import json
from typing import Dict, Any, List, Optional
from utils.llm_client import LLMClient
from config.prompts import get_prompt, get_deduplicator_user_prompt

logger = logging.getLogger(__name__)

# Define a batch size for processing actions to avoid overloading the LLM
ACTION_BATCH_SIZE = 15


class DeduplicatorAgent:
    """
    De-duplicator and Merger Agent for consolidating extracted actions.
    
    Workflow:
    - Receives complete_actions (with who/when) and flagged_actions (missing who/when)
    - Uses LLM to identify and merge duplicate or similar actions
    - Preserves all source citations when merging
    - Maintains separation between complete and flagged actions
    - Returns refined action lists with merge metadata
    """
    
    def __init__(
        self,
        agent_name: str,
        dynamic_settings,
        markdown_logger=None
    ):
        """
        Initialize De-duplicator Agent.
        
        Args:
            agent_name: Name of this agent for LLM configuration
            dynamic_settings: DynamicSettingsManager for per-agent LLM configuration
            markdown_logger: Optional MarkdownLogger instance
        """
        self.agent_name = agent_name
        self.llm = LLMClient.create_for_agent(agent_name, dynamic_settings)
        self.markdown_logger = markdown_logger
        self.system_prompt = get_prompt("deduplicator")
        logger.info(f"Initialized DeduplicatorAgent with agent_name='{agent_name}', model={self.llm.model}")
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute de-duplication and merging logic using batch processing.
        
        Handles actions and tables. Formulas are now integrated into actions.
        Preserves all references when merging.
        
        Args:
            data: Dictionary containing:
                - complete_actions: List of actions with who/when defined
                - flagged_actions: List of actions missing who/when
                - tables: List of table objects (optional)
                
        Returns:
            Dictionary with:
                - refined_complete_actions: Merged complete actions
                - refined_flagged_actions: Merged flagged actions
                - tables: Tables (passed through)
                - merge_summary: Statistics about merging
        """
        complete_actions = data.get("complete_actions", [])
        flagged_actions = data.get("flagged_actions", [])
        tables = data.get("tables", [])
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT STARTING")
        logger.info(f"Input: {len(complete_actions)} complete actions, {len(flagged_actions)} flagged actions")
        logger.info(f"       {len(tables)} tables")
        logger.info(f"=" * 80)
        
        # Log input details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Input Summary",
                {
                    "complete_actions_count": len(complete_actions),
                    "flagged_actions_count": len(flagged_actions),
                    "total_actions": len(complete_actions) + len(flagged_actions),
                    "tables_count": len(tables)
                }
            )
        
        # If no actions, return empty
        if not complete_actions and not flagged_actions:
            logger.warning("No actions provided for de-duplication")
            return {
                "refined_complete_actions": [],
                "refined_flagged_actions": [],
                "tables": tables,  # Pass through tables
                "merge_summary": {
                    "total_input_complete": 0,
                    "total_input_flagged": 0,
                    "total_output_complete": 0,
                    "total_output_flagged": 0,
                    "merges_performed": 0,
                    "actions_unchanged": 0
                }
            }
        
        # Batch process complete actions
        final_complete_actions = self._batch_process_actions(complete_actions, "complete")
        
        # Batch process flagged actions
        final_flagged_actions = self._batch_process_actions(flagged_actions, "flagged")
        
        # Create final merge summary for actions
        merges_performed = (len(complete_actions) - len(final_complete_actions)) + \
                           (len(flagged_actions) - len(final_flagged_actions))
        
        # Process tables for deduplication and merging
        logger.info(f"Processing {len(tables)} tables for deduplication and merging")
        final_tables = self._batch_process_tables(tables)
        
        # Calculate table merge statistics
        table_merges = len(tables) - len(final_tables)
        
        final_summary = {
            "total_input_complete": len(complete_actions),
            "total_input_flagged": len(flagged_actions),
            "total_output_complete": len(final_complete_actions),
            "total_output_flagged": len(final_flagged_actions),
            "merges_performed": merges_performed,
            "actions_unchanged": len(final_complete_actions) + len(final_flagged_actions),
            "total_input_tables": len(tables),
            "total_output_tables": len(final_tables),
            "table_merges_performed": table_merges
        }
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT COMPLETED")
        logger.info(f"Output: {len(final_complete_actions)} complete actions, {len(final_flagged_actions)} flagged actions")
        logger.info(f"        {len(final_tables)} tables")
        logger.info(f"Action merges performed: {final_summary.get('merges_performed', 0)}")
        logger.info(f"Table merges performed: {final_summary.get('table_merges_performed', 0)}")
        logger.info(f"=" * 80)
        
        # Log output details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Output Summary",
                {
                    "refined_complete_actions_count": len(final_complete_actions),
                    "refined_flagged_actions_count": len(final_flagged_actions),
                    "tables_count": len(final_tables),
                    "table_merges": final_summary.get('table_merges_performed', 0),
                    "merge_summary": final_summary
                }
            )
            
            # Log detailed merge information
            self._log_merge_details(
                complete_actions, 
                flagged_actions, 
                final_complete_actions, 
                final_flagged_actions,
                final_summary
            )
        
        return {
            "refined_complete_actions": final_complete_actions,
            "refined_flagged_actions": final_flagged_actions,
            "tables": final_tables,
            "merge_summary": final_summary
        }

    def _batch_process_actions(self, actions: List[Dict[str, Any]], action_type: str) -> List[Dict[str, Any]]:
        """
        Process actions in batches to avoid LLM overload.
        
        Args:
            actions: The list of actions to process
            action_type: "complete" or "flagged" for logging purposes
            
        Returns:
            A list of refined (deduplicated) actions.
        """
        if not actions:
            return []

        refined_actions = []
        for i in range(0, len(actions), ACTION_BATCH_SIZE):
            batch = actions[i:i + ACTION_BATCH_SIZE]
            logger.info(f"Processing {action_type} actions batch {i//ACTION_BATCH_SIZE + 1}...")
            
            # Use the LLM to deduplicate the current batch
            if action_type == "complete":
                result = self._llm_deduplicate(batch, [])
                refined_actions.extend(result.get("complete_actions", batch))
            else:
                result = self._llm_deduplicate([], batch)
                refined_actions.extend(result.get("flagged_actions", batch))
        
        return refined_actions
    
    def _llm_deduplicate(
        self,
        complete_actions: List[Dict[str, Any]],
        flagged_actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to deduplicate and merge actions.
        
        Args:
            complete_actions: List of complete actions
            flagged_actions: List of flagged actions
            
        Returns:
            Dictionary with refined actions and merge summary
        """
        logger.info("Performing LLM-based de-duplication and merging")
        
        # Prepare input for LLM using centralized template
        prompt = get_deduplicator_user_prompt(complete_actions, flagged_actions)
        
        try:
            logger.debug("Sending de-duplication request to LLM")
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            logger.debug(f"LLM response type: {type(result)}")
            
            if isinstance(result, dict):
                # Validate response structure
                if "complete_actions" not in result:
                    result["complete_actions"] = complete_actions
                    logger.warning("LLM didn't return complete_actions, using original")
                
                if "flagged_actions" not in result:
                    result["flagged_actions"] = flagged_actions
                    logger.warning("LLM didn't return flagged_actions, using original")
                
                if "merge_summary" not in result:
                    result["merge_summary"] = {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "total_output_complete": len(result.get("complete_actions", [])),
                        "total_output_flagged": len(result.get("flagged_actions", [])),
                        "merges_performed": 0,
                        "actions_unchanged": len(complete_actions) + len(flagged_actions)
                    }
                
                logger.info(f"De-duplication successful: {len(result['complete_actions'])} complete, {len(result['flagged_actions'])} flagged")
                return result
            else:
                logger.warning(f"Unexpected LLM response format: {type(result)}")
                # Return original actions unchanged
                return {
                    "complete_actions": complete_actions,
                    "flagged_actions": flagged_actions,
                    "merge_summary": {
                        "total_input_complete": len(complete_actions),
                        "total_input_flagged": len(flagged_actions),
                        "total_output_complete": len(complete_actions),
                        "total_output_flagged": len(flagged_actions),
                        "merges_performed": 0,
                        "actions_unchanged": len(complete_actions) + len(flagged_actions)
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in LLM de-duplication: {e}", exc_info=True)
            # Return original actions unchanged on error
            return {
                "complete_actions": complete_actions,
                "flagged_actions": flagged_actions,
                "merge_summary": {
                    "total_input_complete": len(complete_actions),
                    "total_input_flagged": len(flagged_actions),
                    "total_output_complete": len(complete_actions),
                    "total_output_flagged": len(flagged_actions),
                    "merges_performed": 0,
                    "actions_unchanged": len(complete_actions) + len(flagged_actions),
                    "error": str(e)
                }
            }
    
    def _log_merge_details(
        self,
        original_complete: List[Dict[str, Any]],
        original_flagged: List[Dict[str, Any]],
        refined_complete: List[Dict[str, Any]],
        refined_flagged: List[Dict[str, Any]],
        merge_summary: Dict[str, Any]
    ):
        """
        Log detailed merge information to markdown logger.
        
        Args:
            original_complete: Original complete actions
            original_flagged: Original flagged actions
            refined_complete: Refined complete actions
            refined_flagged: Refined flagged actions
            merge_summary: Merge statistics
        """
        if not self.markdown_logger:
            return
        
        # Log merge statistics
        self.markdown_logger.add_text("### Merge Statistics", bold=True)
        self.markdown_logger.add_text("")
        self.markdown_logger.add_list_item(f"Input Complete Actions: {len(original_complete)}")
        self.markdown_logger.add_list_item(f"Input Flagged Actions: {len(original_flagged)}")
        self.markdown_logger.add_list_item(f"Output Complete Actions: {len(refined_complete)}")
        self.markdown_logger.add_list_item(f"Output Flagged Actions: {len(refined_flagged)}")
        self.markdown_logger.add_list_item(f"Merges Performed: {merge_summary.get('merges_performed', 0)}")
        self.markdown_logger.add_list_item(f"Actions Unchanged: {merge_summary.get('actions_unchanged', 0)}")
        self.markdown_logger.add_text("")
        
        # Log sample merged actions (up to 5)
        if refined_complete:
            self.markdown_logger.add_text("### Sample Merged Complete Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(refined_complete[:5], 1):
                merged_from = action.get("merged_from", [])
                if merged_from:
                    self.markdown_logger.add_text(f"**Action {idx} (Merged from {len(merged_from)} sources):**")
                else:
                    self.markdown_logger.add_text(f"**Action {idx}:**")
                self.markdown_logger.add_list_item(f"Who: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"When: {action.get('when', 'N/A')}", level=1)
                if merged_from:
                    self.markdown_logger.add_list_item(f"Merge Rationale: {action.get('merge_rationale', 'N/A')}", level=1)
                self.markdown_logger.add_text("")
        
        # Log sample flagged actions (up to 3)
        if refined_flagged:
            self.markdown_logger.add_text("### Sample Flagged Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(refined_flagged[:3], 1):
                self.markdown_logger.add_text(f"**Flagged Action {idx}:**")
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Missing Fields: {', '.join(action.get('missing_fields', []))}", level=1)
                self.markdown_logger.add_list_item(f"Flag Reason: {action.get('flag_reason', 'N/A')}", level=1)
                self.markdown_logger.add_text("")
    
    def _batch_process_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process tables in batches for deduplication and merging.
        
        Uses LLM-based semantic comparison to identify:
        - Exact duplicates (same content)
        - Similar tables (same purpose, compatible structure)
        - Mergeable tables (LLM determines if rows/content should be combined)
        
        Args:
            tables: List of table objects to process
            
        Returns:
            List of deduplicated/merged tables
        """
        if not tables:
            return []
        
        TABLE_BATCH_SIZE = 10  # Process 10 tables at a time
        refined_tables = []
        
        for i in range(0, len(tables), TABLE_BATCH_SIZE):
            batch = tables[i:i + TABLE_BATCH_SIZE]
            logger.info(f"Processing tables batch {i//TABLE_BATCH_SIZE + 1} ({len(batch)} tables)...")
            
            # Use LLM to deduplicate and merge the current batch
            result = self._llm_deduplicate_tables(batch)
            refined_tables.extend(result.get("tables", batch))
        
        logger.info(f"Table processing complete: {len(tables)} -> {len(refined_tables)} tables")
        return refined_tables
    
    def _llm_deduplicate_tables(self, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use LLM to deduplicate and merge tables based on semantic similarity.
        
        The LLM decides:
        - Whether tables are duplicates (same content)
        - Whether tables should be merged (compatible structure, related content)
        - How to merge table rows and content
        
        Args:
            tables: List of table objects
            
        Returns:
            Dictionary with deduplicated/merged tables
        """
        logger.info(f"Performing LLM-based table deduplication and merging on {len(tables)} tables")
        
        # Prepare input for LLM
        prompt = f"""You are given {len(tables)} tables/checklists/forums extracted from health policy documents.

Your task is to identify and merge duplicate or highly similar tables while preserving all source information.

TABLES:
{json.dumps(tables, indent=2)}

Please analyze these tables and:

1. **Identify Exact Duplicates**: Tables with identical or nearly identical content
2. **Identify Semantic Duplicates**: Tables serving the same purpose with similar structure
3. **Identify Mergeable Tables**: Tables with compatible structures that can be combined
4. **Merge Strategy**: For mergeable tables, decide how to combine:
   - Combine rows if headers match
   - Preserve unique content from each table
   - Keep the most comprehensive version
5. **Preserve Sources**: When merging, combine all source references

**Merging Criteria:**
- Tables with the same title and similar content → MERGE
- Tables with compatible headers (same columns) → CONSIDER MERGING rows
- Tables serving the same purpose (e.g., "Contact List") → MERGE
- Tables with different purposes → KEEP SEPARATE

**When Merging:**
- Choose the most complete title
- Combine all rows (remove duplicates)
- Preserve all source references in a "sources" array
- Add a "merged_from" field listing original table IDs if available
- Keep all headers, preferring the most comprehensive set

Return a JSON object with:
{{
    "tables": [/* array of deduplicated/merged tables */],
    "merge_summary": {{
        "total_input": {len(tables)},
        "total_output": /* number after deduplication */,
        "merges_performed": /* number of merge operations */,
        "merge_details": [/* optional: descriptions of what was merged */]
    }}
}}"""
        
        try:
            logger.debug("Sending table deduplication request to LLM")
            result = self.llm.generate_json(
                prompt=prompt,
                system_prompt=self.system_prompt,
                temperature=0.2
            )
            
            logger.debug(f"LLM response type: {type(result)}")
            
            if isinstance(result, dict):
                # Validate response structure
                if "tables" not in result:
                    result["tables"] = tables
                    logger.warning("LLM didn't return tables, using original")
                
                if "merge_summary" not in result:
                    result["merge_summary"] = {
                        "total_input": len(tables),
                        "total_output": len(result.get("tables", [])),
                        "merges_performed": 0
                    }
                
                logger.info(f"Table deduplication complete: {len(tables)} -> {len(result['tables'])} tables")
                if result.get("merge_summary", {}).get("merge_details"):
                    logger.info(f"Merge details: {result['merge_summary']['merge_details']}")
                
                return result
            else:
                logger.error(f"Unexpected LLM response type: {type(result)}")
                return {"tables": tables, "merge_summary": {"merges_performed": 0}}
                
        except Exception as e:
            logger.error(f"Error during table deduplication: {e}", exc_info=True)
            return {"tables": tables, "merge_summary": {"merges_performed": 0}}

