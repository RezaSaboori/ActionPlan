# Temporary file with table filtering methods to be added to selector.py

def _filter_tables(
    self,
    tables: List[Dict[str, Any]],
    problem_statement: str,
    user_config: Dict[str, Any],
    selected_action_ids: List[str]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filter tables using dual criteria:
    1. LLM-based relevance scoring against problem statement
    2. Check if table is referenced by any selected actions
    
    Tables pass filter if EITHER:
    - Relevance score >= threshold (7/10)
    - OR referenced by any selected action
    
    Args:
        tables: List of table objects to filter
        problem_statement: Problem/objective statement for relevance scoring
        user_config: User configuration
        selected_action_ids: IDs of actions that were selected
        
    Returns:
        Tuple of (selected_tables, discarded_tables)
    """
    if not tables:
        return [], []
    
    logger.info(f"Filtering {len(tables)} tables with dual criteria...")
    
    # First, identify tables referenced by selected actions
    referenced_table_ids = set()
    for table in tables:
        table_id = table.get('id', '')
        # Check if any selected action references this table
        if table.get('extracted_actions'):
            for action_id in table.get('extracted_actions', []):
                if action_id in selected_action_ids:
                    referenced_table_ids.add(table_id)
                    break
    
    logger.info(f"Found {len(referenced_table_ids)} tables referenced by selected actions")
    
    # Then, score remaining tables for relevance
    selected_tables = []
    discarded_tables = []
    
    RELEVANCE_THRESHOLD = 7.0  # Minimum score out of 10
    
    for table in tables:
        table_id = table.get('id', '')
        
        # Criterion 1: Referenced by selected action -> automatically keep
        if table_id in referenced_table_ids:
            table['kept_reason'] = 'referenced_by_selected_action'
            table['relevance_score'] = 10.0  # Max score for referenced tables
            selected_tables.append(table)
            logger.debug(f"Table '{table.get('table_title', 'Untitled')}' kept (referenced by action)")
            continue
        
        # Criterion 2: LLM-based relevance scoring
        relevance_score = self._score_table_relevance(table, problem_statement, user_config)
        table['relevance_score'] = relevance_score
        
        if relevance_score >= RELEVANCE_THRESHOLD:
            table['kept_reason'] = f'relevance_score_{relevance_score:.1f}'
            selected_tables.append(table)
            logger.debug(f"Table '{table.get('table_title', 'Untitled')}' kept (score: {relevance_score:.1f})")
        else:
            table['discard_reason'] = f'low_relevance_score_{relevance_score:.1f}'
            discarded_tables.append(table)
            logger.debug(f"Table '{table.get('table_title', 'Untitled')}' discarded (score: {relevance_score:.1f})")
    
    logger.info(f"Table filtering complete: {len(selected_tables)} selected, {len(discarded_tables)} discarded")
    return selected_tables, discarded_tables

def _score_table_relevance(
    self,
    table: Dict[str, Any],
    problem_statement: str,
    user_config: Dict[str, Any]
) -> float:
    """
    Score a table's relevance to the problem statement using LLM.
    
    Args:
        table: Table object to score
        problem_statement: Problem/objective statement
        user_config: User configuration
        
    Returns:
        Relevance score (0-10)
    """
    table_title = table.get('table_title', 'Untitled')
    table_type = table.get('table_type', 'Unknown')
    headers = table.get('headers', [])
    row_count = len(table.get('rows', []))
    
    # Build table summary for LLM
    table_summary = f"Title: {table_title}\nType: {table_type}\nHeaders: {', '.join(headers)}\nRow count: {row_count}"
    
    prompt = f"""Score the relevance of this table to the given problem statement.

PROBLEM STATEMENT:
{problem_statement}

USER CONTEXT:
- Level: {user_config.get('level', 'unknown')}
- Phase: {user_config.get('phase', 'unknown')}
- Subject: {user_config.get('subject', 'unknown')}

TABLE TO SCORE:
{table_summary}

Rate the table's relevance on a scale of 0-10:
- 10: Highly relevant, essential for addressing the problem
- 7-9: Relevant, provides useful supporting information
- 4-6: Somewhat relevant, tangentially related
- 0-3: Not relevant, unrelated to the problem

Provide ONLY a number between 0 and 10 as your response."""
    
    try:
        result = self.llm.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
            temperature=0.3
        )
        
        # Extract number from result
        match = re.search(r'\d+\.?\d*', result)
        if match:
            score = float(match.group())
            return min(10.0, max(0.0, score))  # Clamp between 0-10
        else:
            logger.warning(f"Could not parse relevance score from LLM response: {result}")
            return 5.0  # Default to neutral score
            
    except Exception as e:
        logger.error(f"Error scoring table relevance: {e}")
        return 5.0  # Default to neutral score on error

