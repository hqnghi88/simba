import uuid
from datetime import datetime
from typing import List, Union

from docling.chunking import HybridChunker
from langchain_docling import DoclingLoader

from simba.core.config import settings
from simba.models.simbadoc import SimbaDoc
from simba.parsing.base import BaseParser


class DoclingParser(BaseParser):
    """
    A parser that uses Docling to chunk and parse documents.
    """

    def parse(self, document: SimbaDoc) -> Union[SimbaDoc, List[SimbaDoc]]:
        try:
            file_path = document.metadata.file_path
            lower_path = str(file_path).lower()
            
            # Use TextLoader for simple text files to avoid Docling restrictions
            if lower_path.endswith('.txt') or lower_path.endswith('.md'):
                from langchain_community.document_loaders import TextLoader
                loader = TextLoader(file_path)
                docs = loader.load()
            else:
                # Use Docling for rich documents
                loader = DoclingLoader(
                    file_path=file_path,
                    chunker=HybridChunker(
                        tokenizer="sentence-transformers/all-MiniLM-L6-v2",
                        device=settings.embedding.device,
                    ),
                )
                docs = loader.load()

            # Create new IDs for each parsed document
            for doc in docs:
                doc.id = str(uuid.uuid4())

            # Update metadata to reflect successful parsing
            document.metadata.parsing_status = "SUCCESS"
            document.metadata.parser = "docling" if not (lower_path.endswith('.txt') or lower_path.endswith('.md')) else "text_loader"
            document.metadata.parsed_at = datetime.now()

            new_document = SimbaDoc(id=document.id, documents=docs, metadata=document.metadata)
            return new_document

        except Exception as e:
            print(f"Error parsing document {document.metadata.filename}: {e}")
            document.metadata.parsing_status = "FAILED"
            # Return the document with status FAILED so downstream knows
            return document
