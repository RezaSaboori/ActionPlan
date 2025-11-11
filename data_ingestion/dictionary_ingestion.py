"""Dictionary ingestion pipeline for building separate vector store and graph from Dictionary.md."""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from neo4j import GraphDatabase
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient

logger = logging.getLogger(__name__)


class DictionaryIngestionPipeline:
    """
    Ingest Dictionary.md into separate ChromaDB collection and Neo4j graph.
    
    This ensures the dictionary data is completely isolated from main documents
    and only accessible to the DictionaryLookupAgent.
    """
    
    def __init__(
        self,
        dictionary_collection: str = "dictionary",
        dictionary_graph_prefix: str = "dictionary"
    ):
        """
        Initialize Dictionary Ingestion Pipeline.
        
        Args:
            dictionary_collection: ChromaDB collection name for dictionary
            dictionary_graph_prefix: Neo4j graph prefix for dictionary nodes
        """
        self.settings = get_settings()
        self.dictionary_collection_name = dictionary_collection
        self.dictionary_graph_prefix = dictionary_graph_prefix
        
        # Initialize components
        self.embedding_client = OllamaEmbeddingsClient()
        self.chroma_client = chromadb.PersistentClient(
            path=self.settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.dictionary_collection = self.chroma_client.get_or_create_collection(
            self.dictionary_collection_name
        )
        
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password)
        )
        
        logger.info(
            f"Initialized DictionaryIngestionPipeline: "
            f"collection='{self.dictionary_collection_name}', "
            f"graph_prefix='{self.dictionary_graph_prefix}'"
        )
    
    def close(self):
        """Close database connections."""
        self.neo4j_driver.close()
    
    def ingest_dictionary(
        self,
        dictionary_path: str,
        clear_existing: bool = False
    ) -> None:
        """
        Ingest dictionary from markdown file into ChromaDB and Neo4j.
        
        Args:
            dictionary_path: Path to Dictionary.md file
            clear_existing: Whether to clear existing collection/graph
        """
        logger.info(f"Ingesting dictionary from: {dictionary_path}")
        
        # Verify file exists
        if not os.path.exists(dictionary_path):
            raise FileNotFoundError(f"Dictionary file not found: {dictionary_path}")
        
        # Clear existing data if requested
        if clear_existing:
            self._clear_existing_data()
        
        # Parse dictionary entries
        entries = self._parse_dictionary(dictionary_path)
        logger.info(f"Parsed {len(entries)} dictionary entries")
        
        # Create graph structure in Neo4j
        self._create_graph_structure(entries)
        
        # Embed and store in ChromaDB
        self._embed_and_store(entries)
        
        logger.info(f"✓ Dictionary ingestion complete!")
    
    def _clear_existing_data(self):
        """Clear existing dictionary collection and graph nodes."""
        # Clear ChromaDB collection
        try:
            self.chroma_client.delete_collection(self.dictionary_collection_name)
            logger.info(f"Cleared existing collection: '{self.dictionary_collection_name}'")
            self.dictionary_collection = self.chroma_client.get_or_create_collection(
                self.dictionary_collection_name
            )
        except Exception as e:
            logger.warning(f"Could not clear dictionary collection: {e}")
        
        # Clear Neo4j graph nodes
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(f"""
                    MATCH (n)
                    WHERE n.id STARTS WITH '{self.dictionary_graph_prefix}_'
                    DETACH DELETE n
                    RETURN count(n) as deleted_count
                """)
                deleted = result.single()['deleted_count']
                logger.info(f"Deleted {deleted} dictionary nodes from Neo4j")
        except Exception as e:
            logger.warning(f"Could not clear dictionary graph nodes: {e}")
    
    def _parse_dictionary(self, dictionary_path: str) -> List[Dict[str, Any]]:
        """
        Parse Dictionary.md into structured entries.
        
        Each entry contains:
        - persian_term: The Persian term
        - english_term: The English equivalent
        - definition: The term definition
        - explanation: Additional explanation
        - full_text: Complete entry text
        
        Args:
            dictionary_path: Path to Dictionary.md
            
        Returns:
            List of dictionary entry dictionaries
        """
        with open(dictionary_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        entries = []
        
        # Split by ## markers (each term starts with ##)
        sections = content.split('\n##')
        
        for idx, section in enumerate(sections):
            if not section.strip():
                continue
            
            lines = section.strip().split('\n')
            if not lines:
                continue
            
            # First line contains both Persian and English terms
            title_line = lines[0].strip()
            
            # Parse title (format: "Persian Term English Term")
            # Example: "خطر قابل قبول Acceptable risk"
            parts = title_line.split(' ')
            
            # Find where Persian ends and English begins (English starts with capital letter)
            persian_parts = []
            english_parts = []
            english_started = False
            
            for part in parts:
                if not english_started and part and part[0].isupper() and ord(part[0]) < 128:
                    english_started = True
                
                if english_started:
                    english_parts.append(part)
                else:
                    persian_parts.append(part)
            
            persian_term = ' '.join(persian_parts).strip()
            english_term = ' '.join(english_parts).strip()
            
            # Parse sections
            definition = ""
            explanation = ""
            current_section = None
            
            for line in lines[1:]:
                line = line.strip()
                if line.startswith('### تعريف واژه:'):
                    current_section = 'definition'
                elif line.startswith('### توضيح'):
                    current_section = 'explanation'
                elif line and current_section:
                    if current_section == 'definition':
                        definition += line + ' '
                    elif current_section == 'explanation':
                        explanation += line + ' '
            
            # Create entry
            entry = {
                'id': f"{self.dictionary_graph_prefix}_entry_{idx}",
                'persian_term': persian_term,
                'english_term': english_term,
                'definition': definition.strip(),
                'explanation': explanation.strip(),
                'full_text': section.strip()
            }
            
            entries.append(entry)
        
        return entries
    
    def _create_graph_structure(self, entries: List[Dict[str, Any]]):
        """
        Create graph structure in Neo4j for dictionary entries.
        
        Args:
            entries: List of dictionary entries
        """
        logger.info("Creating Neo4j graph structure for dictionary")
        
        with self.neo4j_driver.session() as session:
            # Create document node
            session.run(f"""
                MERGE (doc:Document {{
                    id: '{self.dictionary_graph_prefix}_dictionary',
                    name: 'Dictionary',
                    type: 'dictionary',
                    prefix: '{self.dictionary_graph_prefix}'
                }})
            """)
            
            # Create entry nodes
            for entry in entries:
                session.run("""
                    MATCH (doc:Document {id: $doc_id})
                    MERGE (term:DictionaryTerm {
                        id: $entry_id,
                        persian_term: $persian_term,
                        english_term: $english_term,
                        definition: $definition,
                        explanation: $explanation,
                        prefix: $prefix
                    })
                    MERGE (doc)-[:HAS_TERM]->(term)
                """, 
                    doc_id=f"{self.dictionary_graph_prefix}_dictionary",
                    entry_id=entry['id'],
                    persian_term=entry['persian_term'],
                    english_term=entry['english_term'],
                    definition=entry['definition'],
                    explanation=entry['explanation'],
                    prefix=self.dictionary_graph_prefix
                )
            
            logger.info(f"Created {len(entries)} dictionary term nodes in Neo4j")
    
    def _embed_and_store(self, entries: List[Dict[str, Any]], batch_size: int = 50):
        """
        Embed dictionary entries and store in ChromaDB.
        
        Args:
            entries: List of dictionary entries
            batch_size: Batch size for embedding
        """
        logger.info("Embedding and storing dictionary entries in ChromaDB")
        
        # Prepare data for embedding
        texts = []
        metadatas = []
        ids = []
        
        for entry in entries:
            # Create rich text for embedding (includes all information)
            text = f"""
Persian: {entry['persian_term']}
English: {entry['english_term']}
Definition: {entry['definition']}
Explanation: {entry['explanation']}
""".strip()
            
            texts.append(text)
            
            # Store full entry in metadata
            metadata = {
                'id': entry['id'],
                'persian_term': entry['persian_term'],
                'english_term': entry['english_term'],
                'definition': entry['definition'],
                'explanation': entry['explanation'],
                'source': 'Dictionary.md',
                'type': 'dictionary_entry'
            }
            metadatas.append(metadata)
            ids.append(entry['id'])
        
        # Embed and upload in batches
        total_batches = (len(ids) + batch_size - 1) // batch_size
        
        for i in range(0, len(ids), batch_size):
            batch_num = i // batch_size + 1
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            batch_texts = texts[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            
            # Generate embeddings
            embeddings = self.embedding_client.embed_batch(batch_texts, use_cache=True)
            
            if embeddings:
                # Upload to ChromaDB
                self.dictionary_collection.add(
                    ids=batch_ids,
                    embeddings=embeddings,
                    metadatas=batch_metadatas
                )
                
                # Update Neo4j nodes with embeddings
                self._update_neo4j_embeddings(batch_ids, embeddings)
        
        logger.info(f"Stored {len(entries)} dictionary entries in ChromaDB")
    
    def _update_neo4j_embeddings(
        self,
        entry_ids: List[str],
        embeddings: List[List[float]]
    ):
        """
        Update Neo4j dictionary term nodes with embeddings.
        
        Args:
            entry_ids: List of entry IDs
            embeddings: List of embedding vectors
        """
        with self.neo4j_driver.session() as session:
            for entry_id, embedding in zip(entry_ids, embeddings):
                try:
                    session.run("""
                        MATCH (term:DictionaryTerm {id: $entry_id})
                        SET term.embedding = $embedding
                    """, entry_id=entry_id, embedding=embedding)
                except Exception as e:
                    logger.warning(f"Failed to update embedding for {entry_id}: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about dictionary data."""
        stats = {
            'chroma_collection': {
                'name': self.dictionary_collection_name,
                'count': self.dictionary_collection.count()
            }
        }
        
        # Neo4j stats
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (term:DictionaryTerm)
                    WHERE term.id STARTS WITH $prefix
                    RETURN count(term) as total
                """, prefix=f"{self.dictionary_graph_prefix}_")
                total_terms = result.single()['total']
                
                result = session.run("""
                    MATCH (term:DictionaryTerm)
                    WHERE term.id STARTS WITH $prefix AND term.embedding IS NOT NULL
                    RETURN count(term) as with_embeddings
                """, prefix=f"{self.dictionary_graph_prefix}_")
                with_embeddings = result.single()['with_embeddings']
                
                stats['neo4j_graph'] = {
                    'total_terms': total_terms,
                    'terms_with_embeddings': with_embeddings,
                    'coverage_percentage': round(
                        (with_embeddings / total_terms * 100), 2
                    ) if total_terms > 0 else 0
                }
        except Exception as e:
            logger.warning(f"Could not get Neo4j stats: {e}")
            stats['neo4j_graph'] = {'error': str(e)}
        
        return stats


def main():
    """Main function for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest Dictionary.md into separate ChromaDB collection and Neo4j graph"
    )
    parser.add_argument(
        "--dictionary-path",
        default="translator_tools/Dictionary.md",
        help="Path to Dictionary.md file"
    )
    parser.add_argument(
        "--dictionary-collection",
        default="dictionary",
        help="ChromaDB collection name for dictionary"
    )
    parser.add_argument(
        "--dictionary-graph-prefix",
        default="dictionary",
        help="Neo4j graph prefix for dictionary nodes"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing dictionary data before ingesting"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create pipeline
    pipeline = DictionaryIngestionPipeline(
        dictionary_collection=args.dictionary_collection,
        dictionary_graph_prefix=args.dictionary_graph_prefix
    )
    
    try:
        # Ingest dictionary
        pipeline.ingest_dictionary(
            dictionary_path=args.dictionary_path,
            clear_existing=args.clear
        )
        
        # Show stats
        stats = pipeline.get_stats()
        logger.info(f"\nFinal Statistics:")
        logger.info(f"  ChromaDB Collection: {stats['chroma_collection']['name']} "
                   f"({stats['chroma_collection']['count']} entries)")
        if 'neo4j_graph' in stats and 'total_terms' in stats['neo4j_graph']:
            logger.info(f"  Neo4j Graph: {stats['neo4j_graph']['total_terms']} terms, "
                       f"{stats['neo4j_graph']['terms_with_embeddings']} with embeddings "
                       f"({stats['neo4j_graph']['coverage_percentage']}%)")
        
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()

