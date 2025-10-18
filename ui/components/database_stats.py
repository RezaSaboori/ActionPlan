"""Database statistics dashboard component."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from utils.db_init import get_database_statistics
from neo4j import GraphDatabase
from config.settings import get_settings
import logging

logger = logging.getLogger(__name__)


def render_database_stats():
    """Render database statistics dashboard."""
    st.header("📊 Database Statistics")
    
    # Refresh button
    col1, col2, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    try:
        stats = get_database_statistics()
        
        # Overview metrics
        render_overview_metrics(stats)
        
        st.divider()
        
        # Detailed statistics
        col1, col2 = st.columns(2)
        
        with col1:
            render_neo4j_stats(stats.get('neo4j', {}))
        
        with col2:
            render_chromadb_stats(stats.get('chromadb', {}))
        
        st.divider()
        
        # Visualizations
        render_visualizations()
        
    except Exception as e:
        st.error(f"❌ Failed to load statistics: {e}")
        logger.error(f"Stats loading error: {e}", exc_info=True)


def render_overview_metrics(stats: dict):
    """Render overview metrics cards."""
    st.subheader("Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    neo4j_stats = stats.get('neo4j', {})
    chroma_stats = stats.get('chromadb', {})
    
    with col1:
        st.metric(
            "Neo4j Status",
            "Connected" if neo4j_stats.get('status') == 'connected' else "Disconnected",
            delta=None,
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "Total Nodes",
            neo4j_stats.get('nodes', 0),
            help="Total nodes in Neo4j graph"
        )
    
    with col3:
        st.metric(
            "Relationships",
            neo4j_stats.get('relationships', 0),
            help="Total relationships in Neo4j"
        )
    
    with col4:
        st.metric(
            "Vector Documents",
            chroma_stats.get('documents', 0),
            help="Documents in ChromaDB"
        )


def render_neo4j_stats(neo4j_stats: dict):
    """Render Neo4j statistics."""
    st.subheader("🔷 Neo4j Graph Database")
    
    if neo4j_stats.get('status') != 'connected':
        st.error("🔴 Not connected")
        return
    
    st.success("🟢 Connected")
    
    # Basic metrics
    st.metric("Total Nodes", neo4j_stats.get('nodes', 0))
    st.metric("Total Relationships", neo4j_stats.get('relationships', 0))
    
    # Get detailed node breakdown
    try:
        node_breakdown = get_neo4j_node_breakdown()
        if node_breakdown:
            st.subheader("Node Types")
            for node_type, count in node_breakdown.items():
                st.text(f"{node_type}: {count}")
    except Exception as e:
        logger.error(f"Error getting node breakdown: {e}")


def render_chromadb_stats(chroma_stats: dict):
    """Render ChromaDB statistics."""
    st.subheader("🔶 ChromaDB Vector Store")
    
    if chroma_stats.get('status') != 'connected':
        st.error("🔴 Not connected")
        return
    
    st.success("🟢 Connected")
    
    # Basic metrics
    st.metric("Collections", chroma_stats.get('collections', 0))
    st.metric("Total Documents", chroma_stats.get('documents', 0))
    
    # Collection details
    if 'collection_details' in chroma_stats:
        st.subheader("Collections")
        for coll in chroma_stats['collection_details']:
            with st.expander(f"📁 {coll.get('name', 'Unknown')}"):
                st.metric("Documents", coll.get('count', 0))


def render_visualizations():
    """Render data visualizations."""
    st.subheader("📈 Visualizations")
    
    try:
        # Get document type distribution
        doc_distribution = get_document_type_distribution()
        
        if doc_distribution:
            col1, col2 = st.columns(2)
            
            with col1:
                # Pie chart for document types
                fig_pie = px.pie(
                    values=list(doc_distribution.values()),
                    names=list(doc_distribution.keys()),
                    title="Document Type Distribution",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # Bar chart for document types
                fig_bar = px.bar(
                    x=list(doc_distribution.keys()),
                    y=list(doc_distribution.values()),
                    title="Documents by Type",
                    labels={'x': 'Type', 'y': 'Count'},
                    color=list(doc_distribution.keys()),
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                st.plotly_chart(fig_bar, use_container_width=True)
        
        # Nodes per document
        nodes_per_doc = get_nodes_per_document()
        if nodes_per_doc:
            fig_nodes = px.bar(
                x=[d['name'] for d in nodes_per_doc[:10]],  # Top 10
                y=[d['count'] for d in nodes_per_doc[:10]],
                title="Top 10 Documents by Node Count",
                labels={'x': 'Document', 'y': 'Nodes'},
                color_discrete_sequence=['#2E86AB']
            )
            fig_nodes.update_xaxes(tickangle=45)  # Fixed: plural 'update_xaxes' not 'update_xaxis'
            st.plotly_chart(fig_nodes, use_container_width=True)
            
    except Exception as e:
        st.warning(f"Could not generate visualizations: {e}")
        logger.error(f"Visualization error: {e}", exc_info=True)


def get_neo4j_node_breakdown():
    """Get breakdown of nodes by type."""
    settings = get_settings()
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            # Get count by label
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            
            breakdown = {record['label']: record['count'] for record in result}
        
        driver.close()
        return breakdown
        
    except Exception as e:
        logger.error(f"Error getting node breakdown: {e}")
        return {}


def get_document_type_distribution():
    """Get distribution of document types (guidelines vs protocols)."""
    settings = get_settings()
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            result = session.run("""
                MATCH (d:Document)
                RETURN d.is_rule as is_rule, count(*) as count
            """)
            
            distribution = {}
            for record in result:
                is_rule = record['is_rule']
                count = record['count']
                if is_rule:
                    distribution['Guidelines'] = count
                else:
                    distribution['Protocols'] = count
        
        driver.close()
        return distribution
        
    except Exception as e:
        logger.error(f"Error getting document distribution: {e}")
        return {}


def get_nodes_per_document():
    """Get node count per document."""
    settings = get_settings()
    
    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            result = session.run("""
                MATCH (d:Document)-[:HAS_SUBSECTION*]->(h:Heading)
                RETURN d.name as name, count(h) as count
                ORDER BY count DESC
                LIMIT 20
            """)
            
            nodes_per_doc = [
                {'name': record['name'], 'count': record['count']}
                for record in result
            ]
        
        driver.close()
        return nodes_per_doc
        
    except Exception as e:
        logger.error(f"Error getting nodes per document: {e}")
        return []

