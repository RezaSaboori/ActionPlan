"""Unified ingestion pipeline for building dual-embedding vector store from graph nodes."""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import hashlib
from neo4j import GraphDatabase
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient
# from rag_tools.graph_aware_rag import GraphAwareRAG # This is no longer needed directly

logger = logging.getLogger(__name__)


class GraphVectorBuilder:
    """
    Build ChromaDB vector store with dual embeddings from Neo4j graph nodes.
    
    Aligns chunks with graph node line ranges and generates both
    summary and content embeddings.
    """
    
    def __init__(self, summary_collection: str = "summaries", content_collection: str = "documents"):
        """
        Initialize GraphVectorBuilder.
        
        Args:
            summary_collection: ChromaDB collection name for summaries
            content_collection: ChromaDB collection name for content
        """
        self.settings = get_settings()
        self.summary_collection_name = summary_collection
        self.content_collection_name = content_collection
        
        # Initialize components
        self.embedding_client = OllamaEmbeddingsClient()
        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.summary_collection = self.chroma_client.get_or_create_collection(self.summary_collection_name)
        self.content_collection = self.chroma_client.get_or_create_collection(self.content_collection_name)
        
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        
        logger.info(f"Initialized GraphVectorBuilder for collections: summary='{self.summary_collection_name}', content='{self.content_collection_name}'")
    
    def close(self):
        """Close database connections."""
        self.neo4j_driver.close()
        # self.graph_rag.close() # This line is no longer needed
    
    def build_from_graph(self, docs_dir: str, clear_existing: bool = False) -> None:
        """
        Build vector store from Neo4j graph and markdown documents.
        
        Args:
            docs_dir: Directory containing markdown source files
            clear_existing: Whether to clear existing collection
        """
        logger.info(f"Building vector store from graph and documents in {docs_dir}")
        
        # Create or clear collections
        if clear_existing:
            try:
                self.chroma_client.delete_collection(self.summary_collection_name)
                logger.info(f"Cleared existing collection: '{self.summary_collection_name}'")
            except Exception as e:
                logger.warning(f"Could not clear summary collection (it may not exist): {e}")
            try:
                self.chroma_client.delete_collection(self.content_collection_name)
                logger.info(f"Cleared existing collection: '{self.content_collection_name}'")
            except Exception as e:
                logger.warning(f"Could not clear content collection (it may not exist): {e}")

            # Re-create them to ensure they are fresh
            self.summary_collection = self.chroma_client.get_or_create_collection(self.summary_collection_name)
            self.content_collection = self.chroma_client.get_or_create_collection(self.content_collection_name)

        # Get all documents from Neo4j
        documents = self._get_documents_from_graph()
        logger.info(f"Found {len(documents)} documents in graph")
        
        # Process each document
        total_points = 0
        for doc_name in documents:
            logger.info(f"\nProcessing document: {doc_name}")
            
            # Find corresponding markdown file
            md_file = self._find_md_file(docs_dir, doc_name)
            if not md_file:
                logger.warning(f"Could not find markdown file for: {doc_name}")
                continue
            
            # Read file content
            with open(md_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Get all nodes for this document
            nodes = self._get_document_nodes(doc_name)
            logger.info(f"  Found {len(nodes)} nodes in document")
            
            # Process each node and create data for ChromaDB
            summaries, contents, metadatas, ids = self._process_nodes(nodes, lines, doc_name)
            
            # Upload to ChromaDB
            if ids:
                self._upload_data(summaries, contents, metadatas, ids)
                total_points += len(ids)
                logger.info(f"  Uploaded {len(ids)} points for {doc_name}")
        
        logger.info(f"\n✓ Vector store build complete! Total points: {total_points}")
    
    def _get_documents_from_graph(self) -> List[str]:
        """Get list of all documents in Neo4j."""
        query = """
        MATCH (doc:Document)
        RETURN doc.name as name
        """
        
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            return [record['name'] for record in result]
    
    def _get_document_nodes(self, doc_name: str) -> List[Dict[str, Any]]:
        """
        Get all heading nodes for a document with their metadata.
        
        Args:
            doc_name: Document name
            
        Returns:
            List of node dictionaries
        """
        query = """
        MATCH (doc:Document {name: $doc_name})-[:HAS_SUBSECTION*]->(h:Heading)
        RETURN h.id as node_id, h.title as title, h.level as level,
               h.start_line as start_line, h.end_line as end_line,
               h.summary as summary
        ORDER BY h.start_line
        """
        
        with self.neo4j_driver.session() as session:
            result = session.run(query, doc_name=doc_name)
            nodes = []
            for record in result:
                nodes.append({
                    'node_id': record['node_id'],
                    'title': record['title'],
                    'level': record['level'],
                    'start_line': record['start_line'],
                    'end_line': record['end_line'],
                    'summary': record['summary'] or ''
                })
            return nodes
    
    def _find_md_file(self, docs_dir: str, doc_name: str) -> Optional[str]:
        """Find markdown file corresponding to document name."""
        # Try exact match first
        exact_path = os.path.join(docs_dir, f"{doc_name}.md")
        if os.path.exists(exact_path):
            return exact_path
        
        # Try case-insensitive search
        for file in os.listdir(docs_dir):
            if file.lower() == f"{doc_name.lower()}.md":
                return os.path.join(docs_dir, file)
        
        # Try partial match
        doc_name_clean = doc_name.replace('_', ' ').lower()
        for file in os.listdir(docs_dir):
            if file.lower().endswith('.md'):
                file_clean = file[:-3].replace('_', ' ').lower()
                if doc_name_clean in file_clean or file_clean in doc_name_clean:
                    return os.path.join(docs_dir, file)
        
        return None
    
    def _process_nodes(
        self,
        nodes: List[Dict[str, Any]],
        lines: List[str],
        doc_name: str
    ) -> Tuple[List[str], List[str], List[Dict[str, Any]], List[str]]:
        """
        Process nodes and create data for ChromaDB.
        
        Args:
            nodes: List of node dictionaries
            lines: Document lines
            doc_name: Document name
            
        Returns:
            Tuple of (summaries, contents, metadatas, ids)
        """
        all_summaries = []
        all_contents = []
        all_metadatas = []
        all_ids = []
        
        for node in nodes:
            # Extract content from lines
            start_line = node['start_line']
            end_line = node['end_line']
            
            # Validate line numbers
            if start_line < 0 or end_line >= len(lines):
                logger.warning(
                    f"Invalid line range for node {node['node_id']}: "
                    f"{start_line}-{end_line} (file has {len(lines)} lines)"
                )
                continue
            
            # Get section content (skip the heading line itself)
            content_start = start_line + 1
            content_lines = lines[content_start:end_line + 1]
            content = ''.join(content_lines).strip()
            
            if not content:
                # If no content, use summary only
                if node['summary']:
                    content = node['summary']
                else:
                    logger.debug(f"Skipping empty node: {node['node_id']}")
                    continue
            
            # Check content size and chunk if necessary
            chunks = self._chunk_content(content, node)
            
            # Create data for each chunk
            for chunk_idx, chunk_data in enumerate(chunks):
                chunk_content = chunk_data['content']
                summary = node['summary'] or chunk_content  # Use full content if no summary
                
                # Metadata is the same for both collections
                metadata = {
                    'node_id': node['node_id'],
                    'title': node['title'],
                    'level': node['level'],
                    'start_line': chunk_data['start_line'],
                    'end_line': chunk_data['end_line'],
                    'chunk_index': chunk_idx,
                    'total_chunks': len(chunks),
                    'summary': summary,
                    'content': chunk_content,
                    'source': doc_name
                }
                
                point_id = self._generate_point_id(doc_name, node['node_id'], chunk_idx)
                
                all_summaries.append(summary)
                all_contents.append(chunk_content)
                all_metadatas.append(metadata)
                all_ids.append(point_id)
        
        return all_summaries, all_contents, all_metadatas, all_ids
    
    def _chunk_content(
        self,
        content: str,
        node: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Chunk content if it exceeds max section tokens.
        
        Args:
            content: Content to chunk
            node: Node metadata
            
        Returns:
            List of chunk dictionaries
        """
        # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
        estimated_tokens = len(content) // 4
        max_tokens = self.settings.max_section_tokens
        
        if estimated_tokens <= max_tokens:
            # Single chunk
            return [{
                'content': content,
                'start_line': node['start_line'],
                'end_line': node['end_line']
            }]
        
        # Need to sub-chunk
        logger.debug(f"  Sub-chunking node {node['node_id']} ({estimated_tokens} tokens)")
        
        chunks = []
        words = content.split()
        chunk_size_words = max_tokens * 3  # Approximate: 1 token ≈ 0.75 words
        overlap_words = 50
        
        start_idx = 0
        chunk_num = 0
        
        while start_idx < len(words):
            end_idx = start_idx + chunk_size_words
            chunk_words = words[start_idx:end_idx]
            chunk_content = ' '.join(chunk_words)
            
            # Calculate approximate line range for this chunk
            progress = start_idx / len(words)
            line_range = node['end_line'] - node['start_line']
            chunk_start_line = node['start_line'] + int(progress * line_range)
            
            progress_end = min(end_idx / len(words), 1.0)
            chunk_end_line = node['start_line'] + int(progress_end * line_range)
            
            chunks.append({
                'content': chunk_content,
                'start_line': chunk_start_line,
                'end_line': chunk_end_line
            })
            
            start_idx += (chunk_size_words - overlap_words)
            chunk_num += 1
        
        logger.debug(f"  Created {len(chunks)} sub-chunks")
        return chunks
    
    def _generate_point_id(self, doc_name: str, node_id: str, chunk_idx: int) -> str:
        """Generate unique string ID for ChromaDB."""
        return f"{doc_name}_{node_id}_{chunk_idx}"
    
    def _upload_data(
        self,
        summaries: List[str],
        contents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
        batch_size: int = 50
    ) -> None:
        """
        Upload data to ChromaDB collections in batches.
        
        Args:
            summaries: List of summaries
            contents: List of contents
            metadatas: List of metadata dicts
            ids: List of IDs
            batch_size: Batch size for upload
        """
        total_batches = (len(ids) + batch_size - 1) // batch_size
        
        for i in range(0, len(ids), batch_size):
            batch_num = i // batch_size + 1
            logger.info(f"    Uploading batch {batch_num}/{total_batches} ({len(ids[i:i + batch_size])} points)")
            
            batch_ids = ids[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            
            # Embed and upload summaries
            batch_summaries = summaries[i:i + batch_size]
            summary_embeddings = self.embedding_client.embed_batch(batch_summaries, use_cache=True)
            if summary_embeddings:
                self.summary_collection.add(
                    ids=batch_ids,
                    embeddings=summary_embeddings,
                    metadatas=batch_metadatas
                )
            
            # Embed and upload contents
            batch_contents = contents[i:i + batch_size]
            content_embeddings = self.embedding_client.embed_batch(batch_contents, use_cache=True)
            if content_embeddings:
                self.content_collection.add(
                    ids=batch_ids,
                    embeddings=content_embeddings,
                    metadatas=batch_metadatas
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        """
        try:
            return {
                'summary_collection': {
                    'name': self.summary_collection_name,
                    'count': self.summary_collection.count()
                },
                'content_collection': {
                    'name': self.content_collection_name,
                    'count': self.content_collection.count()
                }
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}


def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build ChromaDB vector store from Neo4j graph and markdown documents"
    )
    parser.add_argument(
        "--summary-collection",
        default="summaries",
        help="ChromaDB collection name for summaries"
    )
    parser.add_argument(
        "--content-collection",
        default="documents",
        help="ChromaDB collection name for content"
    )
    parser.add_argument(
        "--docs-dir",
        default="/storage03/Saboori/ActionPlan/HELD/docs/",
        help="Directory containing markdown files"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing collections before building"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Build vector store
    builder = GraphVectorBuilder(
        summary_collection=args.summary_collection,
        content_collection=args.content_collection
    )
    
    try:
        builder.build_from_graph(
            docs_dir=args.docs_dir,
            clear_existing=args.clear
        )
        
        # Show stats
        stats = builder.get_stats()
        logger.info(f"\nFinal Statistics:")
        if stats:
            logger.info(f"  Summary Collection: {stats.get('summary_collection', {}).get('name')} ({stats.get('summary_collection', {}).get('count', 0)} points)")
            logger.info(f"  Content Collection: {stats.get('content_collection', {}).get('name')} ({stats.get('content_collection', {}).get('count', 0)} points)")
        
    finally:
        builder.close()


if __name__ == "__main__":
    main()

