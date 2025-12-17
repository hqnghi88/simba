import asyncio
import os
import sys

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simba.embeddings.embedding_service import EmbeddingService
from simba.database.litedb_service import LiteDocumentDB
from simba.core.factories.database_factory import get_database

async def resync():
    print("Initialize services...")
    embedding_service = EmbeddingService()
    db = get_database()
    
    print("Clearing vector store...")
    try:
        embedding_service.clear_store()
        print("Vector store cleared.")
    except Exception as e:
        print(f"Error clearing store (might be empty): {e}")

    print("Fetching valid documents from database...")
    all_docs = db.get_all_documents()
    print(f"Found {len(all_docs)} documents in database.")
    
    if not all_docs:
        print("No documents to re-embed.")
        return

    print("Re-embedding documents...")
    # embed_all_documents handles chunking and adding to store
    # It might take a moment
    for doc in all_docs:
        if doc.metadata and doc.metadata.enabled:
            print(f"Embedding document: {doc.metadata.filename} ({doc.id})")
            try:
                embedding_service.embed_document(doc.id)
                print("  Success")
            except Exception as e:
                print(f"  Failed: {e}")
        else:
             print(f"Skipping disabled/invalid document: {doc.id}")

    print("Resync complete!")

if __name__ == "__main__":
    asyncio.run(resync())
