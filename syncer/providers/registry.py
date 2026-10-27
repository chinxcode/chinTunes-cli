"""Provider registry and factory router."""

from typing import List, Optional
from syncer.providers.base import BaseProvider
from syncer.providers.jiosaavn import JioSaavnProvider
from syncer.providers.spotify import SpotifyProvider
from syncer.providers.youtube import YouTubeProvider


class ProviderRegistry:
    def __init__(self):
        self._providers: List[BaseProvider] = [
            JioSaavnProvider(),
            SpotifyProvider(),
            YouTubeProvider(),  # Fallback for youtube, gaana, soundcloud, general
        ]

    def register(self, provider: BaseProvider):
        self._providers.insert(0, provider)

    def get_provider_for_url(self, url: str) -> Optional[BaseProvider]:
        for provider in self._providers:
            if provider.can_handle(url):
                return provider
        return self._providers[-1]  # Default to generic/youtube provider

    @property
    def jiosaavn(self) -> JioSaavnProvider:
        for p in self._providers:
            if isinstance(p, JioSaavnProvider):
                return p
        return JioSaavnProvider()
