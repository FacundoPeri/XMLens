import re
import sys
from pathlib import Path
from typing import Optional

from lxml import etree

from resolver import XsltHttpResolver

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).parent

DEFAULT_OUTPUT_DIR = BASE_DIR / "converted"


class XmlTransformer:
    def __init__(self, xslt_url: Optional[str] = None, timeout: int = 15) -> None:
        self.xslt_url = xslt_url
        self.timeout = timeout

    @staticmethod
    def extract_xslt_url(xml_path: Path) -> Optional[str]:
        """Return the XSLT URL declared in <?xml-stylesheet?>, or the xsl-html attribute."""
        tree = etree.parse(str(xml_path))
        root = tree.getroot()
        for node in root.itersiblings(preceding=True):
            if isinstance(node, etree._ProcessingInstruction) and node.target == "xml-stylesheet":
                m = re.search(r'href=["\']([^"\']+)["\']', node.text or "")
                if m:
                    return m.group(1)
        return root.get("xsl-html")

    def transform(
        self,
        xml_path: Path,
        output_dir: Optional[Path] = DEFAULT_OUTPUT_DIR,
    ) -> Path:
        xml_path = Path(xml_path)
        if not xml_path.exists():
            raise FileNotFoundError(f"El archivo XML no existe: {xml_path}")
        if not self.xslt_url:
            raise ValueError("No se especificó una URL de XSLT.")

        xslt_root = self._load_xslt()
        xml_tree = etree.parse(str(xml_path))
        transform = etree.XSLT(xslt_root)
        result = transform(xml_tree)

        output_path = self._output_path(xml_path, output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as output_file:
            output_file.write(
                etree.tostring(result, pretty_print=True, method="html", encoding="utf-8")
            )

        return output_path

    def _load_xslt(self) -> etree._ElementTree:
        parser = etree.XMLParser()
        parser.resolvers.add(XsltHttpResolver(self.xslt_url, self.timeout))
        return etree.parse(self.xslt_url, parser)

    @staticmethod
    def _output_path(xml_path: Path, output_dir: Optional[Path] = None) -> Path:
        base_name = xml_path.stem
        output_folder = Path(output_dir) if output_dir is not None else Path(xml_path.parent)
        return output_folder / f"{base_name}_HTML.html"
