from simba.auth.auth_service import get_supabase_client
from simba.core.factories.vector_store_factory import VectorStoreFactory

# Initialize vector store for reranking
vector_store = VectorStoreFactory.get_vector_store()
supabase = get_supabase_client()

def rerank(state):
    """
    Rerank documents using cross-encoder

    Args:
        state (dict): The current graph state containing retrieved documents

    Returns:
        state (dict): Updated state with reranked documents
    """
    try:
        print("---RERANK---")
        question = state["question"]
        documents = state["documents"]
        
        print(f"Reranking {len(documents)} documents")
        
        # Apply reranking using our cross-encoder
        reranked_docs = vector_store.rerank_results(
            query=question,
            initial_results=documents,
            top_k=20  # Get top 20 documents after reranking
        )
        
        print(f"Reranked to {len(reranked_docs)} documents")
        
        # Store reranked documents in their own field, preserving original documents
        return {"reranked_documents": reranked_docs}
    except KeyError as e:
        print(f"Error reranking documents: {e}")
        # Return empty reranked documents if reranking fails
        return {"reranked_documents": []}
