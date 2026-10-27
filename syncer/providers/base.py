"""Base Provider Interface."""

from abc import ABC, abstractmethod
from typing import Optional
from syncer.core.models import CollectionResult


class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of provider (e.g. jiosaavn, youtube, spotify)."""
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Returns True if the provider can handle the given URL."""
        pass

    @abstractmethod
    def fetch_collection(self, url: str) -> Optional[CollectionResult]:
        """Fetches metadata and track list from the URL."""
        pass
