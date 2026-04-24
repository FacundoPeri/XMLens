from urllib.parse import urljoin

import requests
from lxml import etree


class XsltHttpResolver(etree.Resolver):
    def __init__(self, base_url: str, timeout: int = 15) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def resolve(self, url: str, pubid: str, context):
        resolved_url = url if url.startswith("http") else urljoin(self.base_url, url)
        response = requests.get(resolved_url, timeout=self.timeout)
        response.raise_for_status()
        return self.resolve_string(response.content, context)
