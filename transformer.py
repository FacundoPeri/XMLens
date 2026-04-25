import hashlib
import re
import sys
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests
from lxml import etree

from resolver import XsltHttpResolver

if getattr(sys, 'frozen', False):
    DEFAULT_OUTPUT_DIR = Path.home() / "Documents" / "XMLens" / "converted"
    _CACHE_DIR = Path.home() / "Documents" / "XMLens" / "xslt_cache"
else:
    DEFAULT_OUTPUT_DIR = Path(__file__).parent / "converted"
    _CACHE_DIR = Path.home() / ".xmlens" / "xslt_cache"


class XmlTransformer:
    def __init__(self, xslt_url: Optional[str] = None, timeout: int = 15) -> None:
        self.xslt_url = xslt_url
        self.timeout = timeout
        self._cached_url: Optional[str] = None
        self._cached_mtime: Optional[float] = None
        self._cached_xslt: Optional[etree._ElementTree] = None

    @staticmethod
    def extract_xslt_url(xml_path: Path) -> Optional[str]:
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        for node in root.itersiblings(preceding=True):
            if isinstance(node, etree._ProcessingInstruction) and node.target == "xml-stylesheet":
                m = re.search(r'href=["\']([^"\']+)["\']', node.text or "")
                if m:
                    return m.group(1)
        return root.get("xsl-html")

    @staticmethod
    def is_local(url: str) -> bool:
        parsed = urlparse(url)
        return not parsed.scheme or len(parsed.scheme) == 1 or parsed.scheme == "file"

    def transform(
        self,
        xml_path: Path,
        output_dir: Optional[Path] = DEFAULT_OUTPUT_DIR,
    ) -> Tuple[Path, List[str]]:
        xml_path = Path(xml_path)
        if not xml_path.exists():
            raise FileNotFoundError(f"El archivo XML no existe: {xml_path}")
        if not self.xslt_url:
            raise ValueError("No se especificó una URL de XSLT.")

        xslt_root = self._load_xslt_cached()
        xml_tree = etree.parse(str(xml_path))
        transform_fn = etree.XSLT(xslt_root)

        try:
            result = transform_fn(xml_tree)
        except etree.XSLTApplyError as exc:
            details = "\n".join(
                f"  línea {e.line}: {e.message}" for e in transform_fn.error_log
            )
            raise RuntimeError(f"Falló la transformación XSLT.\n{details}") from exc

        warnings = [f"línea {e.line}: {e.message}" for e in transform_fn.error_log]

        output_path = self._output_path(xml_path, output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(etree.tostring(result, pretty_print=True, method="html", encoding="utf-8"))

        return output_path, warnings

    def _load_xslt_cached(self) -> etree._ElementTree:
        url = self.xslt_url

        if self.is_local(url):
            path = Path(url.replace("file:///", "").replace("file://", ""))
            mtime = path.stat().st_mtime if path.exists() else None
            if url == self._cached_url and mtime == self._cached_mtime:
                return self._cached_xslt
            parser = etree.XMLParser()
            parser.resolvers.add(XsltHttpResolver("", self.timeout))
            self._cached_xslt = etree.parse(str(path), parser)
            self._cached_mtime = mtime
        else:
            if url == self._cached_url:
                return self._cached_xslt
            self._cached_xslt = self._load_xslt_http(url)
            self._cached_mtime = None

        self._cached_url = url
        return self._cached_xslt

    def _load_xslt_http(self, url: str) -> etree._ElementTree:
        cached_path = self._disk_cache_path(url)
        if cached_path.exists():
            content = cached_path.read_bytes()
        else:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            content = resp.content
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cached_path.write_bytes(content)
        parser = etree.XMLParser()
        parser.resolvers.add(XsltHttpResolver(url, self.timeout))
        return etree.parse(BytesIO(content), parser)

    @staticmethod
    def _disk_cache_path(url: str) -> Path:
        return _CACHE_DIR / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.xsl"

    @staticmethod
    def clear_disk_cache() -> int:
        if not _CACHE_DIR.exists():
            return 0
        files = list(_CACHE_DIR.glob("*.xsl"))
        for f in files:
            f.unlink()
        return len(files)

    @staticmethod
    def _output_path(xml_path: Path, output_dir: Optional[Path] = None) -> Path:
        output_folder = Path(output_dir) if output_dir is not None else xml_path.parent
        return output_folder / f"{xml_path.stem}_HTML.html"
