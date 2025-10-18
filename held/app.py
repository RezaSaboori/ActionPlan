import re
import os
import sys
import json
import requests
from collections import defaultdict
from typing import List, Dict, Tuple
from neo4j import GraphDatabase

# Add parent directory to path to import from Agents modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from utils.ollama_embeddings import OllamaEmbeddingsClient

# --- (Constants for Neo4j and Ollama) ---
settings = get_settings()
NEO4J_URI = settings.neo4j_uri
NEO4J_USER = settings.neo4j_user
NEO4J_PASSWORD = settings.neo4j_password

OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "cogito:8b" 

# --- (Helper functions: escape_cypher_string, get_ollama_summary) ---

def escape_cypher_string(value: str) -> str:
    """Escapes a string for use in a Cypher query."""
    return value.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')

def get_ollama_summary(text: str, context: str = "") -> str:
    """Gets a summary from Ollama for the given text."""

    # --- (System Prompt: Defines the AI's persona and task) ---
    system_prompt = (
        "You are a highly skilled summarization expert. Your task is to provide a concise, "
        "neutral, and accurate summary of the provided text for a HEALTH MANAGER AND POLICY MAKER. Follow these guidelines strictly:\n"
        "- **Be Concise**: The summary must be as short as possible while retaining the core information.\n"
        "- ** List the described Guidelines and Tables in the summary.** \n"
        "- **No Chatter**: Do not include any introductory phrases like. Provide only the summary itself.\n"
        "- **Use Provided Context**: If context from subsections is provided, use it to inform your "
        "summary of the parent section, but do not repeat it. Synthesize, do not list.\n"
        "- **Stay Neutral**: Do not add any personal opinions or interpretations. The summary must be "
        "objective and based solely on the provided text."
    )

    # --- (User Prompt: The specific text and context for this request) ---
    user_prompt = f"**Text to Summarize:**\n{text}\n\n"
    if context:
        user_prompt += f"**Context from Subsections:**\n{context}"

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "system": system_prompt,
                "prompt": user_prompt,
                "stream": False
            },
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        summary = response.json().get('response', 'Error: No summary returned.')
        print(f"   - Summary generated for text chunk.")
        return summary.strip()
    except requests.exceptions.RequestException as e:
        print(f"   - Error connecting to Ollama: {e}")
        return f"Error: Could not connect to Ollama to generate summary. Is Ollama running?"

# --- (DocumentAnalyzer Class) ---

class DocumentAnalyzer:
    def __init__(self, content: str, doc_name: str = "Document"):
        self.content = content
        self.doc_name = doc_name
        self.lines = content.split('\n')
        self.hierarchy = []
        # Initialize embedding client
        self.embedding_client = OllamaEmbeddingsClient()
        
    def extract_hierarchy(self) -> List[Dict]:
        """Extract heading hierarchy and associate content with each heading."""
        headings = []
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        
        # First, find all headings and their line numbers
        for i, line in enumerate(self.lines):
            match = re.match(heading_pattern, line.strip())
            if match:
                headings.append({
                    'level': len(match.group(1)),
                    'title': match.group(2).strip(),
                    'start_line': i,
                    'end_line': 0, # Will be determined in the next step
                    'type': 'heading',
                    'children': [],
                    'content': '',
                    'summary': ''
                })

        # Second, determine the content range and end line for each heading
        for i, heading in enumerate(headings):
            start_line_content = heading['start_line'] + 1
            end_line_content = len(self.lines)
            
            # Determine the end line of the section
            # It's the line before the next heading, or the end of the document
            if i + 1 < len(headings):
                end_line_content = headings[i+1]['start_line']
                heading['end_line'] = headings[i+1]['start_line'] - 1
            else:
                heading['end_line'] = len(self.lines) - 1
            
            heading['content'] = "\n".join(self.lines[start_line_content:end_line_content]).strip()

        return headings
    
    def build_document_tree(self, headings: List[Dict]) -> Dict:
        """Builds a hierarchical tree from a flat list of headings."""
        root = {'level': 0, 'children': [], 'title': self.doc_name}
        parent_stack = [root]

        for heading in headings:
            while parent_stack[-1]['level'] >= heading['level']:
                parent_stack.pop()
            
            parent_stack[-1]['children'].append(heading)
            parent_stack.append(heading)
        
        return root

    def summarize_nodes_recursively(self, node: Dict):
        """Recursively generates summaries from the bottom up."""
        child_summaries = []
        for child in node.get('children', []):
            self.summarize_nodes_recursively(child)
            if child['summary']:
                child_summaries.append(f"Child section '{child['title']}': {child['summary']}")

        context_for_summary = ""
        if child_summaries:
            context_for_summary = "Use the following summaries of its subsections as context for your summary."
            context_for_summary += "\n\n" + "\n".join(child_summaries)
        
        # Don't summarize the root node, but do summarize headings with no content
        if node['level'] > 0:
            if node['content'] or child_summaries: # Only summarize if there's something to summarize
                text_to_summarize = node['content']
                node['summary'] = get_ollama_summary(text_to_summarize, context_for_summary)

    def generate_cypher_statements(self) -> List[str]:
        """Generate Neo4j Cypher commands including summaries and embeddings."""
        headings = self.extract_hierarchy()
        doc_tree = self.build_document_tree(headings)
        print("Starting hierarchical summarization with Ollama...")
        self.summarize_nodes_recursively(doc_tree)
        print("Summarization complete.")
        
        cypher_commands = []
        all_nodes = doc_tree.get('children', []) # Start with top-level headings

        # --- PHASE 1: Create all nodes with unique IDs and summaries ---
        doc_name = escape_cypher_string(self.doc_name)
        doc_prefix = self.doc_name.lower().replace(' ', '_').replace('.', '_').replace('-', '_')
        cypher_commands.append(f"CREATE (:Document {{name: '{doc_name}', type: 'root'}})")

        # Flatten the tree to a list of nodes for easier processing
        flat_nodes = []
        nodes_to_visit = list(reversed(all_nodes)) # Use a stack for DFS
        while nodes_to_visit:
            node = nodes_to_visit.pop() # Pop from the end
            flat_nodes.append(node)
            # Add children in reverse order to maintain document order
            children = node.get('children', [])
            for child in reversed(children):
                nodes_to_visit.append(child)
        
        # Generate embeddings for all summaries in batch
        print("Generating embeddings for summaries...")
        summaries = [item['summary'] for item in flat_nodes if item['summary']]
        embeddings = self.embedding_client.embed_batch(summaries) if summaries else []
        print(f"Generated {len(embeddings)} embeddings.")
        
        # Create nodes with embeddings
        embedding_idx = 0
        for i, item in enumerate(flat_nodes):
            base_id = f"h{i + 1}"
            node_id = f"{doc_prefix}_{base_id}"
            title = escape_cypher_string(item['title'])
            summary = escape_cypher_string(item['summary'])
            item['id'] = node_id # Store id for relationship phase
            
            # Get embedding for this summary
            if item['summary'] and embedding_idx < len(embeddings):
                embedding = embeddings[embedding_idx]
                embedding_idx += 1
                # Convert embedding to Cypher list format
                embedding_str = '[' + ','.join([str(val) for val in embedding]) + ']'
                cypher_commands.append(
                    f"CREATE (:Heading {{id: '{node_id}', title: '{title}', level: {item['level']}, start_line: {item['start_line']}, end_line: {item['end_line']}, summary: '{summary}', summary_embedding: {embedding_str}}})"
                )
            else:
                # No embedding available, create without it
                cypher_commands.append(
                    f"CREATE (:Heading {{id: '{node_id}', title: '{title}', level: {item['level']}, start_line: {item['start_line']}, end_line: {item['end_line']}, summary: '{summary}'}})"
                )
        
        # --- PHASE 2: Create all relationships by matching on unique IDs ---
        parent_stack = [{'id': 'doc', 'level': 0, 'dummy': True}] # Add dummy field to avoid KeyError
        for i, item in enumerate(flat_nodes):
            while parent_stack[-1]['level'] >= item['level']:
                parent_stack.pop()
            parent_id = parent_stack[-1]['id']

            if parent_id == 'doc':
                cypher_commands.append(f"MATCH (p:Document {{name: '{doc_name}'}}), (c:Heading {{id: '{item['id']}'}}) CREATE (p)-[:HAS_SUBSECTION]->(c)")
            else:
                cypher_commands.append(f"MATCH (p:Heading {{id: '{parent_id}'}}), (c:Heading {{id: '{item['id']}'}}) CREATE (p)-[:HAS_SUBSECTION]->(c)")
            
            parent_stack.append(item)
        
        return cypher_commands

# --- (Other functions: find_parent_heading, execute_cypher, clear_database) ---
# find_parent_heading is no longer needed

def execute_cypher(driver, statements: List[str]):
    """Executes a list of Cypher statements against the database statement by statement in a transaction."""
    with driver.session() as session:
        print(f"   - Executing {len(statements)} Cypher statements in a transaction...")
        with session.begin_transaction() as tx:
            for statement in statements:
                if statement:
                    tx.run(statement)
        print("   - Script executed successfully.")

def clear_database(driver):
    """Clears all nodes and relationships from the database."""
    print("Clearing Neo4j database...")
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    print("Database cleared.")

# Example usage
def process_document(file_path: str) -> List[str]:
    """Process a markdown document and generate a list of Cypher statements"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    doc_name = os.path.splitext(os.path.basename(file_path))[0]
    analyzer = DocumentAnalyzer(content, doc_name=doc_name)
    statements = analyzer.generate_cypher_statements()
    
    # Print statistics
    # The tree is now built inside generate_cypher_statements, we don't have access to it here
    # without running it twice. For now, we can remove the stats.
    # print(f"Document Analysis Statistics:")
    # print(f"   - Headings: {len(tree['hierarchy'])}")
    print(f"\n{'='*60}\n")
    
    return statements

# --- (Main execution block: if __name__ == "__main__":) ---
if __name__ == "__main__":
    # Command-line argument to clear the database
    clear_db = '--clear' in sys.argv

    driver = None
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print("Connected to Neo4j database.")

        if clear_db:
            clear_database(driver)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        docs_dir = os.path.join(script_dir, "docs")
        
        # Find all markdown files in the docs directory
        doc_files = [f for f in os.listdir(docs_dir) if f.endswith('.md')]

        if not doc_files:
            print(f"No markdown documents found in '{docs_dir}'. Exiting.")
        
        for doc_file in doc_files:
            doc_path = os.path.join(docs_dir, doc_file)
            doc_name_base = os.path.splitext(doc_file)[0]
            output_path = os.path.join(script_dir, f"{doc_name_base.lower().replace(' ', '_')}_cypher.cypher")

            print("\n" + "="*80 + "\n")
            print(f"Processing Document: {doc_name_base}...\n")
            
            cypher_statements = process_document(doc_path)

            if cypher_statements:
                print(f"Importing '{doc_name_base}' into Neo4j...")
                execute_cypher(driver, cypher_statements)
                
                # Save to file
                with open(output_path, "w", encoding='utf-8') as f:
                    f.write(f"// {doc_name_base}\n")
                    f.write("// Neo4j Cypher Commands\n\n")
                    f.write(";\n".join(cypher_statements) + ";")
                
                print(f"\nCypher file generated successfully: {os.path.basename(output_path)}")
                print(f"Data for '{doc_name_base}' imported into Neo4j successfully!")
            else:
                print(f"\nNo statements were generated for '{doc_name_base}'. Check for errors.")

    except FileNotFoundError:
        print(f"\nError: The 'docs' directory was not found in '{os.path.dirname(os.path.abspath(__file__))}'. Please create it and add your markdown files.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if driver:
            driver.close()
            print("\nNeo4j connection closed.")
