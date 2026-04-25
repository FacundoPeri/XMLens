from urllib.parse import urljoin, urlparse

import requests
from lxml import etree


class XsltHttpResolver(etree.Resolver):
    def __init__(self, base_url: str, timeout: int = 15) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def resolve(self, url: str, pubid: str, context):
        if url.startswith(("http://", "https://")):
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return self.resolve_string(response.content, context)

        if not urlparse(url).scheme:
            resolved = urljoin(self.base_url, url)
            if resolved.startswith(("http://", "https://")):
                response = requests.get(resolved, timeout=self.timeout)
                response.raise_for_status()
                return self.resolve_string(response.content, context)

        return None
