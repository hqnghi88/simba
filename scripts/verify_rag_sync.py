import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simba.core.factories.vector_store_factory import VectorStoreFactory
from simba.core.factories.database_factory import get_database

def verify_sync_status():
    print("--- Verifying DB vs Vector Store Sync ---")
    
    # 1. Check Database for Enabled Documents
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    print(f"\n1. Database Status:")
    print(f"   Total Documents: {len(all_docs)}")
    print(f"   Enabled Documents: {len(enabled_docs)}")
    for doc in enabled_docs:
        print(f"   - [ENABLED] {doc.metadata.filename} (ID: {doc.id})")
    
    disabled_docs = [d for d in all_docs if not d.metadata.enabled]
    for doc in disabled_docs:
        print(f"   - [DISABLED] {doc.metadata.filename} (ID: {doc.id})")

    # 2. Check Vector Store content
    print(f"\n2. Vector Store Content Check:")
    vs = VectorStoreFactory.get_vector_store()
    
    # We'll search for content from the DISABLED documents to see if they're still there
    for doc in disabled_docs:
        print(f"   Checking if '{doc.metadata.filename}' is in Vector Store...")
        # Try to find chunks from this doc using a metadata filter or broad search
        # Since we can't search by ID easily without exact ID, we'll search by filename text if content allows,
        # OR just do a broad search and check source metadata.
        
        results = vs.similarity_search("the a an", k=50) # Get many chunks
        
        found_chunks = [r for r in results if r.metadata.get('source') and doc.metadata.filename in r.metadata.get('source')]
        
        if found_chunks:
             print(f"   ❌ ALERT: Found {len(found_chunks)} chunks for DISABLED document {doc.metadata.filename}!")
             print(f"      This means the Vector Store is out of sync.")
        else:
             print(f"   ✅ OK: No chunks found for {doc.metadata.filename} (in top 50 sample).")

if __name__ == "__main__":
    verify_sync_status()
