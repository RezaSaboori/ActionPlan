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
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        doc_filter = st.selectbox(
            "Document Type",
            ["All", "Guidelines (Rules)", "Protocols"],
            help="Filter by document type"
        )
    
    with col2:
        search_query = st.text_input(
            "Search Nodes",
            placeholder="Enter node title...",
            help="Search for nodes by title"
        )
    
    with col3:
        max_nodes = st.number_input(
            "Max Nodes",
            min_value=10,
            max_value=500,
            value=50,
            help="Maximum nodes to display"
        )
    
    # Fetch and display graph
    try:
        nodes, edges = fetch_graph_data(doc_filter, search_query, max_nodes)
        
        if not nodes:
            st.info("No nodes found. Try adjusting filters or ingesting documents.")
            return
        
        st.caption(f"Displaying {len(nodes)} nodes and {len(edges)} relationships")
        
        # Render graph
        render_interactive_graph(nodes, edges)
        
        st.divider()
        
        # Selected node details
        if st.session_state.selected_node:
            render_node_details(st.session_state.selected_node)
        
    except Exception as e:
        st.error(f"❌ Failed to load graph: {e}")
        logger.error(f"Graph loading error: {e}", exc_info=True)


def fetch_graph_data(doc_filter: str, search_query: str, max_nodes: int):
    """
    Fetch graph data from Neo4j.
    
    Args:
        doc_filter: Document type filter
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
    
    try:
        with driver.session() as session:
            # Build query based on filters
            where_clauses = []
            
            if doc_filter == "Guidelines (Rules)":
                where_clauses.append("d.is_rule = true")
            elif doc_filter == "Protocols":
                where_clauses.append("d.is_rule = false")
            
            if search_query:
                where_clauses.append(f"(d.name CONTAINS '{search_query}' OR h.title CONTAINS '{search_query}')")
            
            where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
            
            # Fetch documents and headings
            query = f"""
                MATCH (d:Document)
                OPTIONAL MATCH (d)-[r:HAS_SUBSECTION]->(h:Heading)
                {where_clause}
                RETURN d, h, r
                LIMIT {max_nodes}
            """
            
            result = session.run(query)
            
            node_ids = set()
            
            for record in result:
                # Document node
                doc = record['d']
                if doc and doc.element_id not in node_ids:
                    nodes.append(Node(
                        id=doc.element_id,
                        label=doc.get('name', 'Document'),
                        size=25,
                        color="#4CAF50" if doc.get('is_rule') else "#2196F3",
                        shape="dot",
                        title=f"Document: {doc.get('name')}\nType: {'Guideline' if doc.get('is_rule') else 'Protocol'}"
                    ))
                    node_ids.add(doc.element_id)
                
                # Heading node
                heading = record['h']
                if heading and heading.element_id not in node_ids:
                    nodes.append(Node(
                        id=heading.element_id,
                        label=heading.get('title', 'Heading')[:30],
                        size=15,
                        color="#FF9800",
                        shape="dot",
                        title=f"Heading: {heading.get('title')}\nLevel: {heading.get('level')}"
                    ))
                    node_ids.add(heading.element_id)
                
                # Relationship
                rel = record['r']
                if rel and doc and heading:
                    edges.append(Edge(
                        source=doc.element_id,
                        target=heading.element_id,
                        type="HAS_SUBSECTION"
                    ))
    
    finally:
        driver.close()
    
    return nodes, edges


def render_interactive_graph(nodes, edges):
    """Render interactive graph using streamlit-agraph."""
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
        link={'labelProperty': 'label', 'renderLabel': False}
    )
    
    return_value = agraph(nodes=nodes, edges=edges, config=config)
    
    # Handle node selection
    if return_value:
        st.session_state.selected_node = return_value


def render_node_details(node_id: str):
    """Render details for selected node."""
    st.subheader("📄 Node Details")
    
    try:
        node_data = fetch_node_details(node_id)
        
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
            if 'is_rule' in node_data:
                st.markdown("**Document Type:**")
                st.text("Guideline" if node_data['is_rule'] else "Protocol")
            
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

