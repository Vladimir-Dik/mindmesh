# ============================================================
# Project: MindMesh
# File: pdf_extractor.py
# Version: v0.1
# Date: 2026-07-02
# Name: PDF Extractor (извлекатель текста из PDF)
# ============================================================

import io
import re
from pypdf import PdfReader


def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def extract_pdf_text(raw: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(raw))

        pages_text = []
        page_count = len(reader.pages)

        for index, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            page_text = clean_text(page_text)

            if page_text:
                pages_text.append(
                    f"\n\n--- PDF PAGE {index + 1} ---\n{page_text}"
                )

        text = clean_text("\n".join(pages_text))

        if len(text) < 200:
            return {
                "text": text,
                "ok": False,
                "page_count": page_count,
                "processing_state": "requires_ocr",
                "warning": "PDF has no usable embedded text. OCR is required."
            }

        return {
            "text": text,
            "ok": True,
            "page_count": page_count,
            "processing_state": "ready",
            "warning": None
        }

    except Exception as e:
        return {
            "text": "",
            "ok": False,
            "page_count": 0,
            "processing_state": "pdf_extract_error",
            "warning": str(e)
        }