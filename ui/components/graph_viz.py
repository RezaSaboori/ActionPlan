"""Neo4j graph visualization component."""

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config
from neo4j import GraphDatabase
from config.settings import get_settings
import logging

logger = logging.getLogger(__name__)


def render_graph_explorer():
    """Render interactive Neo4j graph explorer."""
    st.header("📊 Graph Explorer")
    
    st.markdown("""
    Explore the knowledge graph structure. Filter by document type and search for specific nodes.
    Click on nodes to view detailed information.
    """)
    
    # Filters
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search Nodes",
            placeholder="Enter node title...",
            help="Search for nodes by title"
        )
    
    with col2:
        max_nodes = st.number_input(
            "Max Nodes",
            min_value=10,
            max_value=500,
            value=50,
            help="Maximum nodes to display"
        )
    
    # Fetch and display graph
    try:
        nodes, edges, id_mapping = fetch_graph_data(search_query, max_nodes)
        
        # Store ID mapping in session state for node selection
        st.session_state.element_id_mapping = id_mapping
        
        if not nodes:
            st.warning("⚠️ No nodes found in the graph.")
            st.info("""
            **Possible reasons:**
            - No documents have been ingested yet
            - The search query doesn't match any nodes
            - The graph database is empty
            
            **To fix this:**
            1. Go to the **Document Manager** tab
            2. Upload and ingest documents
            3. Come back to Graph Explorer
            """)
            return
        
        # Check if we hit the limit
        limit_warning = ""
        if len(nodes) >= max_nodes:
            limit_warning = f"⚠️ Display limit reached ({max_nodes} nodes). Increase 'Max Nodes' to see more."
        
        st.caption(f"Displaying {len(nodes)} nodes and {len(edges)} relationships")
        if limit_warning:
            st.warning(limit_warning)
        
        # Debug: Show edge details if edges exist but might not be rendering
        with st.expander("🔍 Debug: Edge Information", expanded=False):
            st.write(f"**Total nodes:** {len(nodes)}")
            st.write(f"**Total edges:** {len(edges)}")
            
            # Show database statistics if available
            if hasattr(st.session_state, 'graph_debug_info'):
                debug_info = st.session_state.graph_debug_info
                st.write("**Database Statistics:**")
                st.write(f"- Total relationships in Neo4j: {debug_info.get('total_rels_in_db', 'N/A')}")
                st.write(f"- Relationships fetched: {debug_info.get('total_rels_fetched', 'N/A')}")
                st.write(f"- Relationships matching our nodes: {debug_info.get('matching_rels', 'N/A')}")
                st.write(f"- Skipped (nodes not in set): {debug_info.get('skipped_not_in_set', 'N/A')}")
                st.write(f"- Skipped (ID mapping failed): {debug_info.get('skipped_no_mapping', 'N/A')}")
                st.write(f"- Edges created: {debug_info.get('edges_created', 'N/A')}")
                
                # Show diagnosis
                if debug_info.get('total_rels_in_db', 0) == 0:
                    st.error("❌ **Problem:** No relationships exist in the Neo4j database!")
                    st.info("**Solution:** You need to ingest documents to create relationships. Go to Document Manager and ingest documents.")
                elif debug_info.get('total_rels_fetched', 0) == 0:
                    st.error("❌ **Problem:** Relationships exist but query didn't fetch any!")
                elif debug_info.get('matching_rels', 0) == 0:
                    st.warning("⚠️ **Problem:** Relationships fetched but none match the displayed nodes!")
                    st.info("**This might happen if:** The nodes displayed are not connected to each other (they might connect to nodes not in the current view). Try increasing 'Max Nodes' to see more connected nodes.")
                elif debug_info.get('edges_created', 0) == 0:
                    st.warning("⚠️ **Problem:** Relationships matched but no edges were created!")
                    st.info("**This might be an ID mapping issue.** Check the logs for details.")
            
            if nodes:
                node_ids_set = {node.id for node in nodes}
                st.write(f"**Node IDs in graph (simple IDs for visualization):** {len(node_ids_set)}")
                st.write("**Sample node IDs (first 5):**")
                sample_node_ids = list(node_ids_set)[:5]
                for nid in sample_node_ids:
                    st.code(nid)
                
                # Show custom IDs being used for matching
                if hasattr(st.session_state, 'graph_debug_info'):
                    debug_info = st.session_state.graph_debug_info
                    if 'custom_ids_sample' in debug_info:
                        st.write("**Sample custom IDs used for matching (first 5):**")
                        for cid in debug_info['custom_ids_sample']:
                            st.code(cid)
            
            if edges and len(edges) > 0:
                st.write("**Sample edges (first 5):**")
                for i, edge in enumerate(edges[:5]):
                    edge_to = getattr(edge, 'to', getattr(edge, 'target', 'N/A'))
                    st.code(f"Edge {i+1}:\n  Source: {edge.source}\n  To: {edge_to}\n  Label: {getattr(edge, 'label', 'N/A')}")
                
                # Check if node IDs match
                if nodes:
                    node_ids_set = {node.id for node in nodes}
                    edge_sources = {edge.source for edge in edges}
                    edge_targets = {getattr(edge, 'to', getattr(edge, 'target', None)) for edge in edges}
                    edge_targets = {t for t in edge_targets if t is not None}
                    missing_sources = edge_sources - node_ids_set
                    missing_targets = edge_targets - node_ids_set
                    
                    st.write(f"**Edge sources:** {len(edge_sources)}")
                    st.write(f"**Edge targets:** {len(edge_targets)}")
                    
                    if missing_sources:
                        st.error(f"❌ {len(missing_sources)} edge sources don't match any node IDs")
                        st.code(f"Missing sources (first 5): {list(missing_sources)[:5]}")
                    if missing_targets:
                        st.error(f"❌ {len(missing_targets)} edge targets don't match any node IDs")
                        st.code(f"Missing targets (first 5): {list(missing_targets)[:5]}")
                    if not missing_sources and not missing_targets:
                        st.success("✅ All edge sources and targets match node IDs")
                    else:
                        st.warning("⚠️ Some edges won't display due to ID mismatches")
            else:
                st.warning("⚠️ No edges found! This might be why relationships aren't showing.")
        
        # Render graph
        render_interactive_graph(nodes, edges)
        
        st.divider()
        
        # Selected node details
        if st.session_state.selected_node:
            render_node_details(st.session_state.selected_node)
        
    except Exception as e:
        st.error(f"❌ Failed to load graph: {e}")
        logger.error(f"Graph loading error: {e}", exc_info=True)


def fetch_graph_data(search_query: str, max_nodes: int):
    """
    Fetch graph data from Neo4j.
    
    Args:
        search_query: Search query for node titles
        max_nodes: Maximum nodes to fetch
        
    Returns:
        Tuple of (nodes, edges)
    """
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    nodes = []
    edges = []
    node_ids = set()  # Will store custom 'id' property values for matching
    edge_ids = set()
    # Map Neo4j element_id to simple string ID for streamlit-agraph
    element_id_to_simple_id = {}
    # Map custom 'id' property to simple_id for relationship matching
    custom_id_to_simple_id = {}
    simple_id_counter = 0
    
    try:
        with driver.session() as session:
            # Step 1: Fetch nodes that have relationships (connected nodes)
            # This ensures we get nodes that are actually connected to each other
            if search_query:
                # With search filter - get nodes with relationships
                node_query = """
                    MATCH (n)-[:HAS_SUBSECTION]-()
                    WHERE (n:Document OR n:Heading)
                    AND (
                        (n:Document AND n.name CONTAINS $search)
                        OR (n:Heading AND n.title CONTAINS $search)
                    )
                    RETURN DISTINCT n
                    LIMIT $limit
                """
                logger.debug(f"Fetching connected nodes with search: {search_query}, limit: {max_nodes}")
                node_result = session.run(node_query, search=search_query, limit=max_nodes)
            else:
                # Without search filter - get nodes that have relationships
                # This ensures we get connected nodes, not isolated ones
                node_query = """
                    MATCH (n)-[:HAS_SUBSECTION]-()
                    WHERE n:Document OR n:Heading
                    RETURN DISTINCT n
                    LIMIT $limit
                """
                logger.debug(f"Fetching connected nodes, limit: {max_nodes}")
                node_result = session.run(node_query, limit=max_nodes)
            
            # Process nodes
            # Use custom 'id' property for matching (relationships use this, not element_id)
            for record in node_result:
                node = record['n']
                if not node:
                    continue
                
                # Use custom id property if available, fallback to element_id
                # Neo4j node properties are accessed via dict conversion
                node_dict = dict(node)
                custom_id = node_dict.get('id') if 'id' in node_dict else None
                
                if not custom_id:
                    # For Document nodes, use name as ID
                    if 'Document' in node.labels:
                        custom_id = node_dict.get('name') if 'name' in node_dict else None
                    if not custom_id:
                        # Fallback to element_id if no custom id
                        custom_id = node.element_id
                
                # Debug first few nodes
                if len(nodes) < 5:
                    logger.debug(f"Node {len(nodes)+1}: custom_id={custom_id}, element_id={node.element_id}, labels={node.labels}, dict_keys={list(node_dict.keys())[:5]}")
                
                # Use custom_id as the key for matching
                if custom_id in node_ids:
                    continue
                
                element_id = node.element_id  # Keep element_id for mapping
                
                # Create simple ID for streamlit-agraph compatibility
                simple_id = f"node_{simple_id_counter}"
                simple_id_counter += 1
                element_id_to_simple_id[element_id] = simple_id
                custom_id_to_simple_id[custom_id] = simple_id  # Map custom_id for relationship matching
                node_ids.add(custom_id)  # Use custom_id for matching!
                
                node_dict = dict(node)  # Reuse dict conversion
                if 'Document' in node.labels:
                    nodes.append(Node(
                        id=simple_id,
                        label=node_dict.get('name', 'Document'),
                        size=25,
                        color="#4CAF50",
                        shape="dot",
                        title=f"Document: {node_dict.get('name')}"
                    ))
                elif 'Heading' in node.labels:
                    nodes.append(Node(
                        id=simple_id,
                        label=node_dict.get('title', 'Heading')[:30],
                        size=15,
                        color="#FF9800",
                        shape="dot",
                        title=f"Heading: {node_dict.get('title')}\nLevel: {node_dict.get('level', 'N/A')}"
                    ))
            
            logger.info(f"Found {len(nodes)} nodes")
            
            # Step 2: Fetch relationships involving our nodes
            # Strategy: Fetch relationships where at least ONE node is in our set
            # Then add any missing connected nodes (up to limit)
            if node_ids:
                logger.debug(f"Fetching relationships for {len(node_ids)} nodes")
                
                # First, let's check if relationships exist at all
                count_query = """
                    MATCH (n)-[r:HAS_SUBSECTION]->(m)
                    WHERE (n:Document OR n:Heading) AND (m:Document OR m:Heading)
                    RETURN count(r) as rel_count
                """
                count_result = session.run(count_query)
                rel_count_record = count_result.single()
                total_rels_in_db = rel_count_record['rel_count'] if rel_count_record else 0
                logger.info(f"Total HAS_SUBSECTION relationships in database: {total_rels_in_db}")
                
                # Fetch relationships where at least one node is in our set
                # This ensures we get relationships involving our displayed nodes
                if search_query:
                    # For search, fetch relationships matching the search
                    rel_query = """
                        MATCH (n)-[r:HAS_SUBSECTION]->(m)
                        WHERE (n:Document OR n:Heading) AND (m:Document OR m:Heading)
                        AND (
                            (n:Document AND n.name CONTAINS $search)
                            OR (n:Heading AND n.title CONTAINS $search)
                            OR (m:Document AND m.name CONTAINS $search)
                            OR (m:Heading AND m.title CONTAINS $search)
                        )
                        RETURN n, r, m
                    """
                    rel_result = session.run(rel_query, search=search_query)
                else:
                    # Fetch relationships where source OR target is in our node set
                    # We'll use a different approach: fetch all relationships and include
                    # nodes connected to our set
                    rel_query = """
                        MATCH (n)-[r:HAS_SUBSECTION]->(m)
                        WHERE (n:Document OR n:Heading) AND (m:Document OR m:Heading)
                        RETURN n, r, m
                    """
                    rel_result = session.run(rel_query)
                
                # Process relationships - include relationships where at least one node is in our set
                # Add missing connected nodes if we haven't hit the limit
                total_rels_fetched = 0
                matching_rels = 0
                skipped_not_in_set = 0
                skipped_no_mapping = 0
                nodes_added_from_rels = 0
                
                # Set to track nodes we need to add from relationships
                nodes_to_add = {}
                
                for record in rel_result:
                    total_rels_fetched += 1
                    source_node = record['n']
                    target_node = record['m']
                    rel = record['r']
                    
                    if not source_node or not target_node or not rel:
                        continue
                    
                    # Get custom IDs (what relationships actually use for matching)
                    # Neo4j nodes are accessed via dict conversion
                    source_dict = dict(source_node)
                    source_custom_id = source_dict.get('id') if 'id' in source_dict else None
                    if not source_custom_id and 'Document' in source_node.labels:
                        source_custom_id = source_dict.get('name') if 'name' in source_dict else None
                    if not source_custom_id:
                        source_custom_id = source_node.element_id
                    
                    target_dict = dict(target_node)
                    target_custom_id = target_dict.get('id') if 'id' in target_dict else None
                    if not target_custom_id and 'Document' in target_node.labels:
                        target_custom_id = target_dict.get('name') if 'name' in target_dict else None
                    if not target_custom_id:
                        target_custom_id = target_node.element_id
                    
                    source_in_set = source_custom_id in node_ids
                    target_in_set = target_custom_id in node_ids
                    
                    # Debug first few relationships to see what's happening
                    if total_rels_fetched <= 5:
                        logger.debug(f"Rel {total_rels_fetched}: source_custom_id={source_custom_id}, target_custom_id={target_custom_id}")
                        logger.debug(f"  source_in_set={source_in_set}, target_in_set={target_in_set}")
                        if not source_in_set and not target_in_set:
                            logger.debug(f"  Neither node in set - sample node_ids: {list(node_ids)[:3]}")
                    
                    # If at least one node is in our set, include this relationship
                    if source_in_set or target_in_set:
                        # Add missing nodes if we haven't hit the limit
                        # Allow overflow to complete relationships (up to 2x limit)
                        max_allowed_nodes = max_nodes * 2
                        if not source_in_set:
                            if source_custom_id not in nodes_to_add and source_custom_id not in node_ids:
                                if len(nodes) + len(nodes_to_add) < max_allowed_nodes:
                                    nodes_to_add[source_custom_id] = source_node
                                    nodes_added_from_rels += 1
                                    if total_rels_fetched <= 5:
                                        logger.debug(f"  → Adding source node: {source_custom_id}")
                        if not target_in_set:
                            if target_custom_id not in nodes_to_add and target_custom_id not in node_ids:
                                if len(nodes) + len(nodes_to_add) < max_allowed_nodes:
                                    nodes_to_add[target_custom_id] = target_node
                                    nodes_added_from_rels += 1
                                    if total_rels_fetched <= 5:
                                        logger.debug(f"  → Adding target node: {target_custom_id}")
                
                # Add all collected nodes before processing edges
                logger.info(f"Adding {len(nodes_to_add)} nodes from relationships")
                for custom_id, node in nodes_to_add.items():
                    if custom_id not in node_ids:
                        element_id = node.element_id
                        simple_id = f"node_{simple_id_counter}"
                        simple_id_counter += 1
                        element_id_to_simple_id[element_id] = simple_id
                        custom_id_to_simple_id[custom_id] = simple_id
                        node_ids.add(custom_id)
                        
                        node_dict = dict(node)
                        if 'Document' in node.labels:
                            nodes.append(Node(
                                id=simple_id,
                                label=node_dict.get('name', 'Document'),
                                size=25,
                                color="#4CAF50",
                                shape="dot",
                                title=f"Document: {node_dict.get('name')}"
                            ))
                        elif 'Heading' in node.labels:
                            nodes.append(Node(
                                id=simple_id,
                                label=node_dict.get('title', 'Heading')[:30],
                                size=15,
                                color="#FF9800",
                                shape="dot",
                                title=f"Heading: {node_dict.get('title')}\nLevel: {node_dict.get('level', 'N/A')}"
                            ))
                    else:
                        logger.debug(f"Node {custom_id} already in set, skipping")
                
                logger.info(f"After adding nodes: total nodes = {len(nodes)}, node_ids count = {len(node_ids)}")
                sample_custom_ids = list(node_ids)[:5]
                logger.info(f"Sample custom IDs in node_ids: {sample_custom_ids}")
                
                # Store sample custom IDs for debug display
                if 'graph_debug_info' not in st.session_state:
                    st.session_state.graph_debug_info = {}
                st.session_state.graph_debug_info['custom_ids_sample'] = sample_custom_ids
                
                # Now process relationships again to create edges
                # Reset the result iterator by re-running the query
                if search_query:
                    rel_query = """
                        MATCH (n)-[r:HAS_SUBSECTION]->(m)
                        WHERE (n:Document OR n:Heading) AND (m:Document OR m:Heading)
                        AND (
                            (n:Document AND n.name CONTAINS $search)
                            OR (n:Heading AND n.title CONTAINS $search)
                            OR (m:Document AND m.name CONTAINS $search)
                            OR (m:Heading AND m.title CONTAINS $search)
                        )
                        RETURN n, r, m
                    """
                    rel_result = session.run(rel_query, search=search_query)
                else:
                    rel_query = """
                        MATCH (n)-[r:HAS_SUBSECTION]->(m)
                        WHERE (n:Document OR n:Heading) AND (m:Document OR m:Heading)
                        RETURN n, r, m
                    """
                    rel_result = session.run(rel_query)
                
                # Process relationships to create edges
                edges_processed = 0
                for record in rel_result:
                    edges_processed += 1
                    source_node = record['n']
                    target_node = record['m']
                    rel = record['r']
                    
                    if not source_node or not target_node or not rel:
                        continue
                    
                    # Get custom IDs for matching
                    # Neo4j nodes are accessed via dict conversion
                    source_dict = dict(source_node)
                    source_custom_id = source_dict.get('id') if 'id' in source_dict else None
                    if not source_custom_id and 'Document' in source_node.labels:
                        source_custom_id = source_dict.get('name') if 'name' in source_dict else None
                    if not source_custom_id:
                        source_custom_id = source_node.element_id
                    
                    target_dict = dict(target_node)
                    target_custom_id = target_dict.get('id') if 'id' in target_dict else None
                    if not target_custom_id and 'Document' in target_node.labels:
                        target_custom_id = target_dict.get('name') if 'name' in target_dict else None
                    if not target_custom_id:
                        target_custom_id = target_node.element_id
                    
                    # Debug first few - show what we're comparing
                    if edges_processed <= 5:
                        logger.debug(f"Edge {edges_processed}:")
                        logger.debug(f"  source_custom_id={source_custom_id} (type: {type(source_custom_id)})")
                        logger.debug(f"  source in node_ids: {source_custom_id in node_ids}")
                        logger.debug(f"  target_custom_id={target_custom_id} (type: {type(target_custom_id)})")
                        logger.debug(f"  target in node_ids: {target_custom_id in node_ids}")
                        if source_custom_id not in node_ids:
                            logger.debug(f"  Sample node_ids: {list(node_ids)[:3]}")
                    
                    # Only create edge if both nodes are in our set (using custom_id)
                    if source_custom_id in node_ids and target_custom_id in node_ids:
                        matching_rels += 1
                        # Map to simple IDs using custom_id mapping
                        source_simple_id = custom_id_to_simple_id.get(source_custom_id)
                        target_simple_id = custom_id_to_simple_id.get(target_custom_id)
                        
                        if source_simple_id and target_simple_id:
                            edge_key = f"{source_simple_id}->{target_simple_id}"
                            if edge_key not in edge_ids:
                                # Create Edge object - use 'to' instead of 'target'!
                                new_edge = Edge(
                                    source=source_simple_id,
                                    to=target_simple_id,  # streamlit-agraph uses 'to', not 'target'
                                    label="HAS_SUBSECTION"
                                )
                                edges.append(new_edge)
                                edge_ids.add(edge_key)
                                logger.debug(f"Added edge: {source_simple_id} -> {target_simple_id}")
                            else:
                                logger.debug(f"Skipped duplicate edge: {edge_key}")
                        else:
                            skipped_no_mapping += 1
                            if skipped_no_mapping <= 3:
                                logger.warning(f"Could not map IDs: source={source_element_id} (mapped: {source_simple_id}), target={target_element_id} (mapped: {target_simple_id})")
                    else:
                        skipped_not_in_set += 1
                
                logger.info(f"First pass: Fetched {total_rels_fetched} relationships from DB")
                logger.info(f"  - Added {nodes_added_from_rels} nodes from relationships")
                logger.info(f"Second pass: Processed {edges_processed} relationships for edge creation")
                logger.info(f"  - {matching_rels} relationships matched (both nodes in set)")
                logger.info(f"  - {skipped_not_in_set} skipped (both nodes outside our set)")
                logger.info(f"  - {skipped_no_mapping} skipped (ID mapping failed)")
                logger.info(f"  - Created {len(edges)} edges")
                logger.info(f"  - Total nodes now: {len(nodes)}")
                
                # Store debug info in session state for display
                st.session_state.graph_debug_info = {
                    'total_rels_in_db': total_rels_in_db,
                    'total_rels_fetched': total_rels_fetched,
                    'matching_rels': matching_rels,
                    'edges_created': len(edges),
                    'nodes_count': len(nodes),
                    'skipped_not_in_set': skipped_not_in_set,
                    'skipped_no_mapping': skipped_no_mapping
                }
            else:
                logger.warning("No nodes found, skipping relationship fetch")
                st.session_state.graph_debug_info = {
                    'total_rels_in_db': 0,
                    'total_rels_fetched': 0,
                    'matching_rels': 0,
                    'edges_created': 0,
                    'nodes_count': 0
                }
    
    except Exception as e:
        logger.error(f"Error fetching graph data: {e}", exc_info=True)
        raise
    
    finally:
        driver.close()
    
    logger.debug(f"Returning {len(nodes)} nodes and {len(edges)} edges")
    # Return reverse mapping (simple_id -> element_id) for node selection
    simple_id_to_element_id = {v: k for k, v in element_id_to_simple_id.items()}
    return nodes, edges, simple_id_to_element_id


def render_interactive_graph(nodes, edges):
    """Render interactive graph using streamlit-agraph."""
    # Ensure we have valid data
    if not nodes:
        st.warning("No nodes to display")
        return
    
    logger.info(f"Rendering graph with {len(nodes)} nodes and {len(edges)} edges")
    
    # Verify edge source/target match node IDs
    node_ids = {node.id for node in nodes}
    valid_edges = []
    invalid_count = 0
    
    for edge in edges:
        # Check if edge has required attributes - streamlit-agraph uses 'to', not 'target'
        if not hasattr(edge, 'source') or not hasattr(edge, 'to'):
            logger.warning(f"Edge missing source/to: {edge}")
            invalid_count += 1
            continue
        
        edge_to = getattr(edge, 'to', None)
        if not edge_to:
            logger.warning(f"Edge missing 'to' attribute: {edge}")
            invalid_count += 1
            continue
            
        if edge.source in node_ids and edge_to in node_ids:
            valid_edges.append(edge)
        else:
            logger.warning(f"Edge skipped: source={edge.source} (in nodes: {edge.source in node_ids}) or to={edge_to} (in nodes: {edge_to in node_ids})")
            invalid_count += 1
    
    if invalid_count > 0:
        logger.warning(f"Filtered {invalid_count} invalid edges out of {len(edges)} total")
        st.warning(f"⚠️ {invalid_count} edges were filtered out due to ID mismatches. Check debug info above.")
    
    if not valid_edges:
        st.warning("⚠️ No valid edges to display. Relationships won't be visible.")
        logger.warning("No valid edges found after filtering")
    
    # Convert nodes and edges to lists if they aren't already
    nodes_list = list(nodes) if not isinstance(nodes, list) else nodes
    edges_list = list(valid_edges) if not isinstance(valid_edges, list) else valid_edges
    
    # Log what we're about to render
    logger.info(f"Rendering {len(nodes_list)} nodes and {len(edges_list)} edges")
    if edges_list:
        first_edge_to = getattr(edges_list[0], 'to', 'N/A')
        logger.debug(f"First edge: source={edges_list[0].source}, to={first_edge_to}")
    
    config = Config(
        width="100%",
        height=600,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
        node={'labelProperty': 'label'},
        link={'labelProperty': 'label', 'renderLabel': True, 'color': '#848484'}  # Added color to make edges visible
    )
    
    try:
        return_value = agraph(nodes=nodes_list, edges=edges_list, config=config)
    except Exception as e:
        logger.error(f"Error rendering graph: {e}", exc_info=True)
        st.error(f"Failed to render graph: {e}")
        # Show more details about what we tried to render
        st.code(f"Nodes: {len(nodes_list)}, Edges: {len(edges_list)}")
        if edges_list:
            first_edge_to = getattr(edges_list[0], 'to', 'N/A')
            st.code(f"First edge example: source={edges_list[0].source}, to={first_edge_to}")
        raise
    
    # Handle node selection
    if return_value:
        st.session_state.selected_node = return_value


def render_node_details(node_id: str):
    """Render details for selected node."""
    st.subheader("📄 Node Details")
    
    try:
        # Convert simple_id back to element_id if we have the mapping
        element_id = node_id
        if hasattr(st.session_state, 'element_id_mapping'):
            element_id = st.session_state.element_id_mapping.get(node_id, node_id)
        
        node_data = fetch_node_details(element_id)
        
        if not node_data:
            st.warning("No details available for this node.")
            return
        
        # Display properties
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Type:**")
            st.text(node_data.get('type', 'Unknown'))
            
            st.markdown("**Title/Name:**")
            st.text(node_data.get('title', node_data.get('name', 'N/A')))
            
            if 'level' in node_data:
                st.markdown("**Level:**")
                st.text(node_data['level'])
        
        with col2:
            if 'start_line' in node_data and 'end_line' in node_data:
                st.markdown("**Line Range:**")
                st.text(f"{node_data['start_line']} - {node_data['end_line']}")
        
        # Summary
        if 'summary' in node_data and node_data['summary']:
            st.markdown("**Summary:**")
            st.text_area("", node_data['summary'], height=150, disabled=True)
        
        # Relationships
        relationships = fetch_node_relationships(node_id)
        if relationships:
            st.markdown("**Relationships:**")
            for rel in relationships:
                st.text(f"→ {rel['type']}: {rel['target']}")
        
    except Exception as e:
        st.error(f"Failed to load node details: {e}")
        logger.error(f"Node details error: {e}", exc_info=True)


def fetch_node_details(node_id: str):
    """Fetch detailed information for a node."""
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (n)
                WHERE elementId(n) = $node_id
                RETURN n, labels(n) as labels
            """, node_id=node_id)
            
            record = result.single()
            if not record:
                return None
            
            node = record['n']
            labels = record['labels']
            
            node_data = dict(node)
            node_data['type'] = labels[0] if labels else 'Unknown'
            
            return node_data
    
    finally:
        driver.close()


def fetch_node_relationships(node_id: str):
    """Fetch relationships for a node."""
    settings = get_settings()
    
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    relationships = []
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (n)-[r]->(m)
                WHERE elementId(n) = $node_id
                RETURN type(r) as rel_type, labels(m)[0] as target_type, 
                       coalesce(m.title, m.name) as target_name
                LIMIT 20
            """, node_id=node_id)
            
            for record in result:
                relationships.append({
                    'type': record['rel_type'],
                    'target': f"{record['target_type']}: {record['target_name']}"
                })
    
    finally:
        driver.close()
    
    return relationships

