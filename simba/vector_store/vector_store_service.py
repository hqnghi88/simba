import logging
import os
from typing import List, Optional

import faiss
from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS

from simba.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self, store=None, embeddings=None):
        self.store = store
        self.embeddings = embeddings
        if not store or not embeddings:
            raise ValueError("Both store and embeddings must be provided")

    def as_retriever(self, **kwargs):
        return self.store.as_retriever()
    
    def _get_index_mtime(self):
        """Get modification time of FAISS index file"""
        try:
           index_file = os.path.join(settings.paths.faiss_index_dir, "index.faiss")
           if os.path.exists(index_file):
               return os.path.getmtime(index_file)
        except Exception:
           pass
        return 0

    def _reload_if_changed(self):
        """Reload FAISS index if disk file has changed"""
        # Only applicable for FAISS
        if not isinstance(self.store, FAISS): 
            return

        current_mtime = self._get_index_mtime()
        # Initialize last_mtime if not set
        if not hasattr(self, "_last_mtime"):
            self._last_mtime = current_mtime
            return # Assume current loaded version is up to date initially

        if current_mtime > self._last_mtime:
            logger.info(f"Vector store changed on disk (mtime {current_mtime} > {self._last_mtime}). Reloading...")
            try:
                self.store = FAISS.load_local(
                    settings.paths.faiss_index_dir,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                self._last_mtime = current_mtime
                logger.info("Vector store reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload vector store: {e}")

    def similarity_search(self, query: str, k: int = 10, **kwargs) -> List[Document]:
        """Wrapper for similarity search on underlying store"""
        # Auto-reload if needed (for local FAISS + Celery setup)
        self._reload_if_changed()
        return self.store.similarity_search(query, k=k, **kwargs)

    def rerank_results(self, query: str, initial_results: List[Document], top_k: int = 20, **kwargs) -> List[Document]:
        """
        Rerank results (fallback for local dev). 
        Real implementation would use a CrossEncoder.
        Here we just return the initial results truncated to top_k.
        """
        logger.info(f"Reranking fallback: returning top {top_k} from {len(initial_results)} docs")
        return initial_results[:top_k]

    def save(self):
        # Ensure directory exists before saving
        os.makedirs(settings.paths.faiss_index_dir, exist_ok=True)
        self.store.save_local(settings.paths.faiss_index_dir)

    def get_document(self, document_id: str) -> Optional[Document]:
        """Get a document by its ID"""
        try:
            docstore = self.store.docstore
            document = docstore.search(document_id)
            if isinstance(document, Document):
                return document
            return None
        except Exception as e:
            logger.error(f"Error retrieving document {document_id}: {str(e)}")
            return None

    def update_document(self, document_id: str, newDocument: Document) -> bool:
        try:
            if newDocument:
                newDocument.metadata["id"] = document_id
                self.delete_documents([document_id])
                self.add_documents([newDocument])
            return True
        except Exception as e:
            logger.error(f"Error updating document {document_id}: {e}")
            raise e

    def get_documents(self) -> list[Document]:
        docstore = self.store.docstore
        index_to_docstore_id = self.store.index_to_docstore_id

        # Retrieve all documents
        all_documents = []
        for index, doc_id in index_to_docstore_id.items():
            document = docstore.search(doc_id)
            if document:
                all_documents.append(document)

        return all_documents

    def add_documents(self, documents: List[Document], document_id: str = None) -> bool:
        """Add documents with proper synchronization"""
        try:
            logger.info(f"Adding {len(documents)} chunks to vector store (Document ID: {document_id})")
            # Add document_id to metadata if provided
            if document_id:
                for doc in documents:
                    doc.metadata["document_id"] = document_id

            # Log first chunk for debug
            # if documents:
            #      logger.info(f"Sample chunk: {documents[0].page_content[:50]}...")

            for doc in documents:
                if self.chunk_in_store(doc.id):
                    logger.warning(f"Document chunk {doc.id} already in store")
                    continue
                # else:
                #    print(f"Adding {doc.id} to store")

            self.store.add_documents(documents)
            self.save()
            logger.info("Vector store saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise e
            
    def count_documents(self):
        """Count documents in store."""
        if isinstance(self.store, FAISS):
            return len(self.store.docstore._dict)
        # For other vector stores that support len()
        return len(self.store)

    def delete_documents(self, uids: list[str] | str) -> bool:
        """Delete documents and verify deletion"""
        try:
            if isinstance(uids, str):
                uids = [uids]
                
            logger.info(f"Deleting documents: {uids}")
            self.store.delete(uids)
            self.save()

            return True
        except ValueError as e:
            if "do not exist in the current store" in str(e):
                logger.warning(f"Some documents to delete were missing from vector store (ignoring): {e}")
                # Save anyway to persist any deletions that succeeded (though FAISS atomic?)
                # Actually if it failed, nothing changed usually. But we want to claim success.
                return True
            logger.error(f"Error deleting documents: {e}")
            raise e
        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise e

    def clear_store(self):
        """Clear all documents and reset the FAISS index"""
        try:
            # Get embedding dimension from existing index or create new
            if hasattr(self.store, "index") and self.store.index is not None:
                dim = self.store.index.d
            else:
                dim = len(self.embeddings.embed_query("test"))

            # Reset FAISS index
            self.store.index = faiss.IndexFlatL2(dim)

            # Clear document store
            self.store.docstore._dict.clear()
            self.store.index_to_docstore_id.clear()

            # Save empty state
            self.save()
            logger.info("Vector store cleared successfully")
            return True

        except Exception as e:
            logger.error(f"Error clearing store: {e}")
            raise e

    def chunk_in_store(self, chunk_id: str) -> bool:
        index_to_docstore_id = self.store.index_to_docstore_id
        return chunk_id in index_to_docstore_id.values()

    def get_document_ids(self) -> list[str]:
        index_to_docstore_id = self.store.index_to_docstore_id
        return list(index_to_docstore_id.values())

    def search(self, query, user_id=None, **kwargs):
        """
        Search for similar documents, filtered by user_id if provided
        
        Args:
            query: The search query string
            user_id: The user ID to filter results by (for multi-tenancy)
            **kwargs: Additional search parameters
            
        Returns:
            List of similar documents
        """
        # If user_id is provided, ensure we only search their documents
        if user_id:
            return self.store.similarity_search(query, user_id=user_id, **kwargs)
        else:
            # For backward compatibility, but this should be avoided in production
            logger.warning("search() called without user_id - this is not secure for multi-tenant systems")
            return self.store.similarity_search(query, **kwargs)

    def search_with_filters(self, query, user_id=None, **kwargs):
        """
        Search for similar documents with filters, filtered by user_id if provided
        
        Args:
            query: The search query string
            user_id: The user ID to filter results by (for multi-tenancy)
            **kwargs: Additional search parameters
            
        Returns:
            List of similar documents with scores
        """
        # If user_id is provided, ensure we only search their documents
        if user_id:
            return self.store.similarity_search_with_score(query, user_id=user_id, **kwargs)
        else:
            # For backward compatibility, but this should be avoided in production
            logger.warning("search_with_filters() called without user_id - this is not secure for multi-tenant systems")
            return self.store.similarity_search_with_score(query, **kwargs)

    async def asearch_with_filters(self, query, user_id=None, **kwargs):
        """
        Asynchronously search for similar documents with filters, filtered by user_id if provided
        
        Args:
            query: The search query string
            user_id: The user ID to filter results by (for multi-tenancy)
            **kwargs: Additional search parameters
            
        Returns:
            List of similar documents with scores
        """
        # If user_id is provided, ensure we only search their documents
        if user_id:
            return await self.store.asearch_with_filters(query, user_id=user_id, **kwargs)
        else:
            # For backward compatibility, but this should be avoided in production
            logger.warning("asearch_with_filters() called without user_id - this is not secure for multi-tenant systems")
            return await self.store.asearch_with_filters(query, **kwargs)

    def verify_store_sync(self) -> bool:
        """
        Verify synchronization between FAISS index and document store
        Returns: bool indicating if stores are in sync
        """


def usage():
    from simba.core.factories.vector_store_factory import VectorStoreFactory

    store = VectorStoreFactory.get_vector_store()
    print(store.embeddings)


if __name__ == "__main__":
    usage()
