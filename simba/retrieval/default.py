"""
Default vector similarity retriever implementation.
"""

from typing import List, Optional

from langchain.schema import Document

from simba.auth.auth_service import AuthService, get_supabase_client
from simba.retrieval.base import BaseRetriever
from simba.vector_store import VectorStoreService

supabase = get_supabase_client()
class DefaultRetriever(BaseRetriever):
    """Default vector similarity search retriever."""

    def __init__(self, vector_store: Optional[VectorStoreService] = None, k: int = 5, **kwargs):
        """
        Initialize the default retriever.

        Args:
            vector_store: Optional vector store to use
            k: Default number of documents to retrieve
            **kwargs: Additional parameters
        """
        super().__init__(vector_store)
        self.default_k = k

    def retrieve(self, query: str, user_id: str = None, **kwargs) -> List[Document]:
        """
        Retrieve documents using default similarity search.

        Args:
            query: The query string
            user_id: User ID for multi-tenant filtering
            **kwargs: Additional parameters including:
                - k: Number of documents to retrieve (overrides instance default)
                - score_threshold: Minimum score threshold for results
                - filter: Filter criteria

        Returns:
            List of relevant documents
        """
        k = 20
        # For local development with mock auth, use mock user ID
        # In production, this would get the actual user from Supabase
        current_user_id = user_id or "mock-user-id"

        # For local development with mock auth, user_id is ignored by local FAISS
        # but we pass the query and k to the wrapper method
        return self.store.similarity_search(query, k=k)
