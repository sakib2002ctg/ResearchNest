"""Async academic search providers and normalized result contracts."""

from app.modules.discovery.providers.arxiv import ArxivProvider
from app.modules.discovery.providers.base import (
    DiscoveryProvider,
    ProviderCitation,
    ProviderPaper,
    ProviderUnavailable,
)
from app.modules.discovery.providers.crossref import CrossrefProvider
from app.modules.discovery.providers.openalex import OpenAlexProvider
from app.modules.discovery.providers.pubmed import PubMedProvider
from app.modules.discovery.providers.semantic_scholar import SemanticScholarProvider

__all__ = [
    "ArxivProvider",
    "CrossrefProvider",
    "DiscoveryProvider",
    "OpenAlexProvider",
    "ProviderPaper",
    "ProviderCitation",
    "ProviderUnavailable",
    "PubMedProvider",
    "SemanticScholarProvider",
]
