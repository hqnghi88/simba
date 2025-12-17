import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simba.core.factories.vector_store_factory import VectorStoreFactory
from simba.core.factories.database_factory import get_database

def verify_retrieval():
    print("--- Verifying RAG Pipeline ---")
    
    # 1. Check Database for Enabled Documents
    db = get_database()
    all_docs = db.get_all_documents()
    enabled_docs = [d for d in all_docs if d.metadata.enabled]
    
    print(f"\n1. Database Status:")
    print(f"   Total Documents: {len(all_docs)}")
    print(f"   Enabled Documents: {len(enabled_docs)}")
    
    if not enabled_docs:
        print("   ❌ No enabled documents found. Chatbot cannot answer.")
        return

    for doc in enabled_docs:
        print(f"   - {doc.metadata.filename} (ID: {doc.id})")

    # 2. Check Vector Store Retrieval
    print(f"\n2. Vector Store Retrieval Test:")
    vs = VectorStoreFactory.get_vector_store()
    
    # Use a generic query that should match most documents to verify indexing
    test_query = "summary introduction purpose" 
    
    try:
        results = vs.similarity_search(test_query, k=3)
        print(f"   Query: '{test_query}'")
        print(f"   Retrieved chunks: {len(results)}")
        
        if len(results) > 0:
            print("   ✅ SUCCESS: Content found in vector store.")
            print("\n   Sample retrieved content:")
            for i, res in enumerate(results):
                preview = res.page_content.replace('\n', ' ')[:200]
                source = res.metadata.get('source', 'unknown')
                print(f"   {i+1}. [{source}] {preview}...")
        else:
            print("   ❌ WARNING: No documents retrieved. Vector store might be empty or out of sync.")
            print("   Try running: poetry run python scripts/resync_vector_store.py")

    except Exception as e:
        print(f"   ❌ ERROR during retrieval: {e}")

if __name__ == "__main__":
    verify_retrieval()
