"""Utilities for campaign generator exporters."""

from __future__ import annotations

import zipfile
from typing import Dict

def export_to_docx(campaign: Dict[str, str], filename: str) -> None:
    """Create a DOCX file containing the campaign information with styled headings and text."""
    # Escape special XML characters
    def xml_escape(text: str) -> str:
        """Handle xml escape."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&apos;")
            .replace('"', "&quot;")
        )

    # Build paragraphs with two runs: bold coloured heading and normal coloured description
    paragraphs = []
    for key, value in campaign.items():
        heading_run = f"<w:r><w:rPr><w:b/><w:color w:val='2C3E50'/><w:sz w:val='28'/></w:rPr><w:t>{xml_escape(key)}</w:t></w:r>"
        br = "<w:br/>"
        desc_run = f"<w:r><w:rPr><w:color w:val='34495E'/><w:sz w:val='24'/></w:rPr><w:t>{xml_escape(value)}</w:t></w:r>"
        # Add spacing after each paragraph
        paragraph = f"<w:p><w:pPr><w:spacing w:after='300'/></w:pPr>{heading_run}{br}{desc_run}</w:p>"
        paragraphs.append(paragraph)
    body_xml = "\n        ".join(paragraphs)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
        {body_xml}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="R1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    # Create the DOCX (a zip archive with specific files)
    with zipfile.ZipFile(filename, "w") as docx_zip:
        # Write content types
        docx_zip.writestr("[Content_Types].xml", content_types)
        # Write relationships
        docx_zip.writestr("_rels/.rels", rels_xml)
        # Write document
        docx_zip.writestr("word/document.xml", document_xml)
