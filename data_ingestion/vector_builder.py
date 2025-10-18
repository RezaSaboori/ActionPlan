"""Build ChromaDB vector store from markdown documents."""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow INFO and WARNING messages

import logging
from pathlib import Path
from typing import List, Dict, Any
import hashlib
from config.settings import get_settings
from utils.document_parser import DocumentParser
from rag_tools.vector_rag import VectorRAG

logger = logging.getLogger(__name__)


class VectorBuilder:
    """Build ChromaDB vector store from markdown documents."""
    
    def __init__(self, collection_name: str = "rules_documents"):
        """
        Initialize VectorBuilder.
        
        Args:
            collection_name: ChromaDB collection name
        """
        self.settings = get_settings()
        self.collection_name = collection_name
        self.vector_rag = VectorRAG(collection_name=collection_name)
        self.parser = DocumentParser()
        logger.info(f"Initialized VectorBuilder for: {collection_name}")
    
    def build_from_directory(self, docs_dir: str) -> None:
        """
        Build vector store from all markdown files in directory.
        
        Args:
            docs_dir: Path to directory containing markdown files
        """
        if not os.path.exists(docs_dir):
            logger.error(f"Directory not found: {docs_dir}")
            return
        
        # Create collection
        self.vector_rag.create_collection()
        
        # Get all markdown files
        md_files = list(Path(docs_dir).glob("**/*.md"))
        logger.info(f"Found {len(md_files)} markdown files in {docs_dir}")
        
        all_documents = []
        
        for md_file in md_files:
            logger.info(f"Processing: {md_file}")
            docs = self.build_from_file(str(md_file))
            all_documents.extend(docs)
        
        # Add all documents to vector store
        if all_documents:
            logger.info(f"Adding {len(all_documents)} chunks to vector store...")
            self.vector_rag.add_documents(all_documents)
            logger.info("Vector store building complete!")
    
    def build_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Build vector documents from a single markdown file.
        
        Args:
            file_path: Path to markdown file
            
        Returns:
            List of document dictionaries ready for vector store
        """
        doc_name = Path(file_path).stem
        documents = []
        
        # Extract headings to get structure
        headings = self.parser.extract_headings(file_path)
        
        if not headings:
            logger.warning(f"No headings found in {file_path}")
            return documents
        
        # Process each heading section
        for heading in headings:
            content = self.parser.get_content_by_lines(
                file_path,
                heading['line_start'],
                heading['line_end']
            )
            
            if not content.strip():
                continue
            
            # Chunk the content
            chunks = self.parser.chunk_text(
                content,
                chunk_size=self.settings.chunk_size,
                chunk_overlap=self.settings.chunk_overlap
            )
            
            # Create document for each chunk
            for idx, chunk in enumerate(chunks):
                # Normalize node_id to match Neo4j format (lowercase with underscores)
                normalized_node_id = self._normalize_node_id(heading['id'])
                
                # Generate unique ID
                chunk_id = self._generate_chunk_id(doc_name, normalized_node_id, idx)
                
                doc = {
                    'text': chunk,
                    'metadata': {
                        'source': doc_name,
                        'node_id': normalized_node_id,
                        'line_range': f"{heading['line_start']}-{heading['line_end']}",
                        'heading': heading['title'],
                        'chunk_index': idx,
                        'chunk_id': chunk_id
                    }
                }
                documents.append(doc)
        
        logger.info(f"Created {len(documents)} document chunks from {file_path}")
        return documents
    
    def _normalize_node_id(self, node_id: str) -> str:
        """
        Normalize node ID to match Neo4j format.
        Converts to lowercase and replaces spaces, dots, and dashes with underscores.
        
        Args:
            node_id: Original node ID (e.g., "Document Name_h1")
            
        Returns:
            Normalized node ID (e.g., "document_name_h1")
        """
        return node_id.lower().replace(' ', '_').replace('.', '_').replace('-', '_')
    
    def _generate_chunk_id(self, doc_name: str, heading_id: str, chunk_idx: int) -> str:
        """Generate unique chunk ID."""
        base = f"{doc_name}_{heading_id}_{chunk_idx}"
        return hashlib.md5(base.encode()).hexdigest()[:16]
    
    def clear_collection(self) -> None:
        """Clear the vector collection."""
        try:
            self.vector_rag.delete_collection()
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Could not clear collection: {e}")


def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build ChromaDB vector store from markdown documents")
    parser.add_argument("--collection", required=True, help="Collection name (e.g., rules_documents)")
    parser.add_argument("--docs-dir", required=True, help="Directory containing markdown files")
    parser.add_argument("--clear", action="store_true", help="Clear existing data first")
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    builder = VectorBuilder(collection_name=args.collection)
    
    if args.clear:
        logger.info("Clearing existing data...")
        builder.clear_collection()
    
    builder.build_from_directory(args.docs_dir)
    
    logger.info("Vector store building complete!")


if __name__ == "__main__":
    main()

