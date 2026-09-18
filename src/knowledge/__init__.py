"""
Knowledge retrieval over the curated source indexes in docs/knowledge/.

The engine never invents citations: it retrieves entries (title, summary,
categories, confidence status, source file) from the project's own knowledge
documents and passes them to the LLM as the only citable references.

The public-domain library (data/library/) extends this with verbatim passages
from freely redistributable classical editions, cited with locators.
"""

from .retrieval import (
    KnowledgeEntry, KnowledgeIndex, get_knowledge_index,
    retrieve_references, reference_lines, TOPIC_CATEGORY_MAP,
)
from .library import (
    LibraryIndex, LibraryPassage, LibrarySource, get_library_index,
    library_reference_lines, load_catalog, search_library,
)

__all__ = [
    "KnowledgeEntry", "KnowledgeIndex", "get_knowledge_index",
    "retrieve_references", "reference_lines", "TOPIC_CATEGORY_MAP",
    "LibraryIndex", "LibraryPassage", "LibrarySource", "get_library_index",
    "library_reference_lines", "load_catalog", "search_library",
]
