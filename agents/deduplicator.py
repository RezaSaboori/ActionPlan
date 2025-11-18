"""De-duplicator and Merger Agent for action consolidation."""

import logging
import json
from typing import Dict, Any, List, Optional
from utils.llm_client import LLMClient
from config.prompts import get_prompt, get_deduplicator_actor_prompt

logger = logging.getLogger(__name__)

# Define a batch size for processing actions to avoid overloading the LLM
ACTION_BATCH_SIZE = 15


class DeduplicatorAgent:
    """
    De-duplicator and Merger Agent for consolidating extracted actions.
    
    Workflow:
    - Receives unified list of actions from timing and assigner agents
    - Groups actions by actor (who field)
    - Uses LLM to identify and merge duplicate or similar actions within each actor group
    - Preserves all source citations when merging
    - Batches actors with >15 actions for efficient processing
    - Returns unified action list grouped by actor with merge metadata
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
    
    def _group_actions_by_actor(self, actions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group actions by responsible actor (who field).
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            Dictionary mapping actor names to their assigned actions
        """
        actor_groups = {}
        
        for action in actions:
            actor = action.get('who', '').strip()
            
            # Handle missing, empty, or invalid actors
            if not actor or actor.lower() in ['tbd', 'n/a', 'undefined', 'unknown', '']:
                actor = "Undefined Actor"
            
            if actor not in actor_groups:
                actor_groups[actor] = []
            
            actor_groups[actor].append(action)
        
        logger.info(f"Grouped {len(actions)} actions into {len(actor_groups)} actor groups")
        for actor, actor_actions in actor_groups.items():
            logger.info(f"  - {actor}: {len(actor_actions)} actions")
        
        return actor_groups
    
    def _batch_process_actor_group(
        self, 
        actor_name: str, 
        actions: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Process an actor's actions with conditional batching based on count.
        
        If the actor has ≤15 actions, process them all in one batch.
        If the actor has >15 actions, split into batches of 15.
        
        Args:
            actor_name: Name of the actor/role
            actions: List of actions for this actor
            
        Returns:
            Tuple of (refined_actions, actor_stats)
        """
        if not actions:
            return [], {
                "input_count": 0,
                "output_count": 0,
                "merges_performed": 0,
                "batches_used": 0
            }
        
        total_batches = 0
        
        if len(actions) <= ACTION_BATCH_SIZE:
            # Process all actions in one batch
            logger.info(f"Processing {actor_name}: {len(actions)} actions in 1 batch")
            refined_actions, batch_summary = self._llm_deduplicate_actor(actor_name, actions)
            total_batches = 1
        else:
            # Split into batches of ACTION_BATCH_SIZE
            refined_actions = []
            num_batches = (len(actions) + ACTION_BATCH_SIZE - 1) // ACTION_BATCH_SIZE
            logger.info(f"Processing {actor_name}: {len(actions)} actions in {num_batches} batches")
            
            for i in range(0, len(actions), ACTION_BATCH_SIZE):
                batch = actions[i:i + ACTION_BATCH_SIZE]
                batch_num = i // ACTION_BATCH_SIZE + 1
                logger.info(f"  - Batch {batch_num}/{num_batches}: {len(batch)} actions")
                
                batch_result, _ = self._llm_deduplicate_actor(actor_name, batch)
                refined_actions.extend(batch_result)
                total_batches += 1
        
        # Calculate statistics for this actor
        actor_stats = {
            "input_count": len(actions),
            "output_count": len(refined_actions),
            "merges_performed": len(actions) - len(refined_actions),
            "batches_used": total_batches
        }
        
        logger.info(f"  - {actor_name} complete: {len(actions)} → {len(refined_actions)} actions ({actor_stats['merges_performed']} merges)")
        
        return refined_actions, actor_stats
    
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute actor-based de-duplication and merging logic.
        
        Groups actions by actor, then deduplicates within each actor group.
        Uses batch processing for actors with >15 actions.
        
        Args:
            data: Dictionary containing:
                - actions: Unified list of actions
                - tables: List of table objects (optional)
                
        Returns:
            Dictionary with:
                - actions: Deduplicated actions (unified list grouped by actor)
                - tables: Deduplicated tables
        """
        actions = data.get("actions", [])
        tables = data.get("tables", [])
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT STARTING")
        logger.info(f"Input: {len(actions)} actions, {len(tables)} tables")
        logger.info(f"=" * 80)
        
        # Log input details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Input Summary",
                {
                    "total_actions": len(actions),
                    "tables_count": len(tables)
                }
            )
        
        # If no actions, return empty
        if not actions:
            logger.warning("No actions provided for de-duplication")
            return {
                "actions": [],
                "tables": tables
            }
        
        # Group actions by actor
        actor_groups = self._group_actions_by_actor(actions)
        
        # Process each actor group
        refined_actions = []
        actor_statistics = {}
        total_merges = 0
        total_batches = 0
        
        for actor_name, actor_actions in actor_groups.items():
            actor_refined, actor_stats = self._batch_process_actor_group(actor_name, actor_actions)
            refined_actions.extend(actor_refined)
            actor_statistics[actor_name] = actor_stats
            total_merges += actor_stats.get('merges_performed', 0)
            total_batches += actor_stats.get('batches_used', 0)
        
        # Remove redundant fields (source_node, source_lines) since they're in reference
        for action in refined_actions:
            action.pop('source_node', None)
            action.pop('source_lines', None)
        
        # Process tables for deduplication and merging
        logger.info(f"Processing {len(tables)} tables for deduplication and merging")
        final_tables = self._batch_process_tables(tables)
        
        # Calculate table merge statistics
        table_merges = len(tables) - len(final_tables)
        
        # Create final merge summary
        final_summary = {
            "total_input_actions": len(actions),
            "total_output_actions": len(refined_actions),
            "actors_processed": len(actor_groups),
            "actor_statistics": actor_statistics,
            "merges_performed": total_merges,
            "batches_used": total_batches,
            "total_input_tables": len(tables),
            "total_output_tables": len(final_tables),
            "table_merges_performed": table_merges
        }
        
        logger.info(f"=" * 80)
        logger.info(f"DEDUPLICATOR AGENT COMPLETED")
        logger.info(f"Output: {len(refined_actions)} refined actions across {len(actor_groups)} actors")
        logger.info(f"        {len(final_tables)} tables")
        logger.info(f"Action merges performed: {total_merges}")
        logger.info(f"Table merges performed: {table_merges}")
        logger.info(f"Total batches used: {total_batches}")
        logger.info(f"=" * 80)
        
        # Log output details to markdown
        if self.markdown_logger:
            self.markdown_logger.log_processing_step(
                "De-duplicator Output Summary",
                {
                    "actions_count": len(refined_actions),
                    "actors_processed": len(actor_groups),
                    "tables_count": len(final_tables),
                    "table_merges": table_merges,
                    "merge_summary": final_summary
                }
            )
            
            # Log detailed merge information
            self._log_merge_details(actor_statistics, refined_actions, final_summary)
        
        return {
            "actions": refined_actions,
            "tables": final_tables
        }

    def _llm_deduplicate_actor(
        self,
        actor_name: str,
        actions: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Use LLM to deduplicate and merge actions for a specific actor.
        
        Args:
            actor_name: Name of the actor/role
            actions: List of actions for this actor
            
        Returns:
            Tuple of (refined_actions, batch_summary)
        """
        logger.info(f"Performing LLM-based de-duplication for actor: {actor_name}")
        
        # Prepare input for LLM using centralized template
        prompt = get_deduplicator_actor_prompt(actor_name, actions)
        
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
                if "actions" not in result:
                    result["actions"] = actions
                    logger.warning("LLM didn't return actions, using original")
                
                refined_actions = result.get("actions", actions)
                
                # Validate: output should not have MORE actions than input
                if len(refined_actions) > len(actions):
                    logger.warning(f"LLM returned MORE actions ({len(refined_actions)}) than input ({len(actions)}). Using original.")
                    refined_actions = actions
                
                # Log if unexpectedly few actions returned (possible LLM error)
                expected_min = max(1, len(actions) // 2)  # Expect at least half, unless heavy merging
                if len(refined_actions) < expected_min:
                    logger.warning(f"LLM returned suspiciously few actions: {len(refined_actions)} from {len(actions)} input. Check for errors.")
                
                batch_summary = {
                    "input_count": len(actions),
                    "output_count": len(refined_actions),
                    "merges_performed": len(actions) - len(refined_actions)
                }
                
                logger.info(f"De-duplication successful for {actor_name}: {len(actions)} → {len(refined_actions)} actions")
                return refined_actions, batch_summary
            else:
                logger.warning(f"Unexpected LLM response format: {type(result)}")
                # Return original actions unchanged
                return actions, {
                    "input_count": len(actions),
                    "output_count": len(actions),
                    "merges_performed": 0
                }
                
        except Exception as e:
            logger.error(f"Error in LLM de-duplication for {actor_name}: {e}", exc_info=True)
            # Return original actions unchanged on error
            return actions, {
                "input_count": len(actions),
                "output_count": len(actions),
                "merges_performed": 0,
                "error": str(e)
            }
    
    def _log_merge_details(
        self,
        actor_statistics: Dict[str, Dict[str, Any]],
        refined_actions: List[Dict[str, Any]],
        merge_summary: Dict[str, Any]
    ):
        """
        Log detailed merge information to markdown logger with actor-based statistics.
        
        Args:
            actor_statistics: Dictionary mapping actor names to their statistics
            refined_actions: List of all refined actions
            merge_summary: Overall merge statistics
        """
        if not self.markdown_logger:
            return
        
        # Log overall merge statistics
        self.markdown_logger.add_text("### Merge Statistics", bold=True)
        self.markdown_logger.add_text("")
        self.markdown_logger.add_list_item(f"Total Input Actions: {merge_summary.get('total_input_actions', 0)}")
        self.markdown_logger.add_list_item(f"Total Output Actions: {merge_summary.get('total_output_actions', 0)}")
        self.markdown_logger.add_list_item(f"Actors Processed: {merge_summary.get('actors_processed', 0)}")
        self.markdown_logger.add_list_item(f"Total Merges Performed: {merge_summary.get('merges_performed', 0)}")
        self.markdown_logger.add_list_item(f"Total Batches Used: {merge_summary.get('batches_used', 0)}")
        self.markdown_logger.add_text("")
        
        # Log per-actor statistics
        if actor_statistics:
            self.markdown_logger.add_text("### Actor-wise Statistics", bold=True)
            self.markdown_logger.add_text("")
            for actor_name, stats in actor_statistics.items():
                self.markdown_logger.add_text(f"**{actor_name}:**")
                self.markdown_logger.add_list_item(f"Input Actions: {stats.get('input_count', 0)}", level=1)
                self.markdown_logger.add_list_item(f"Output Actions: {stats.get('output_count', 0)}", level=1)
                self.markdown_logger.add_list_item(f"Merges: {stats.get('merges_performed', 0)}", level=1)
                self.markdown_logger.add_list_item(f"Batches: {stats.get('batches_used', 0)}", level=1)
                self.markdown_logger.add_text("")
        
        # Log sample merged actions (up to 5)
        if refined_actions:
            self.markdown_logger.add_text("### Sample Refined Actions", bold=True)
            self.markdown_logger.add_text("")
            for idx, action in enumerate(refined_actions[:5], 1):
                merged_from = action.get("merged_from", [])
                if merged_from:
                    self.markdown_logger.add_text(f"**Action {idx} (Merged from {len(merged_from)} sources):**")
                else:
                    self.markdown_logger.add_text(f"**Action {idx}:**")
                self.markdown_logger.add_list_item(f"Who: {action.get('who', 'N/A')}", level=1)
                self.markdown_logger.add_list_item(f"Action: {action.get('action', 'N/A')[:100]}...", level=1)
                self.markdown_logger.add_list_item(f"When: {action.get('when', 'N/A')}", level=1)
                if merged_from:
                    self.markdown_logger.add_list_item(f"Merge Rationale: {action.get('merge_rationale', 'N/A')}", level=1)
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

