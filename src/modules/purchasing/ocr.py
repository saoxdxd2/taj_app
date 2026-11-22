"""Offline OCR for scanned supplier papers.

Uses Windows' built-in OCR engine (winocr / WinRT) so no model has to be
bundled and nothing is uploaded: the fr-FR language pack ships with Windows.
A page is returned as word boxes, which is what the table extraction needs.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.modules.purchasing.invoice_extraction import Word


class OcrUnavailable(RuntimeError):
    """The OCR engine or its French language pack is missing."""


@dataclass
class OcrPage:
    width: float
    height: float
    words: List[Word]


LANGUAGE = "fr-FR"


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_image(path: Path, page_index: int):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise OcrUnavailable("Reading scans needs Pillow (pip install pillow).") from exc

    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise OcrUnavailable("Reading scanned PDFs needs pypdf (pip install pypdf).") from exc
        reader = PdfReader(str(path))
        if not reader.pages:
            raise OcrUnavailable("The PDF has no pages.")
        if page_index >= len(reader.pages):
            raise OcrUnavailable(f"The PDF has only {len(reader.pages)} page(s).")
        images = reader.pages[page_index].images
        if not images:
            raise OcrUnavailable(
                "This PDF has no embedded image, so it is probably digital. "
                "A digital PDF should be imported by another route; a scan must "
                "carry the page as an image."
            )
        biggest = max(images, key=lambda item: len(item.data))
        image = Image.open(io.BytesIO(biggest.data))
    else:
        image = Image.open(path)

    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def read_page(path, page_index: int = 0, language: str = LANGUAGE) -> OcrPage:
    """OCR one page (PDF or image) into word boxes."""
    path = Path(path)
    if not path.is_file():
        raise OcrUnavailable(f"File not found: {path}")
    try:
        import winocr
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise OcrUnavailable(
            "Windows OCR is not installed (pip install winocr). "
            "It runs locally; nothing leaves the machine."
        ) from exc

    image = _load_image(path, page_index)
    try:
        result = winocr.recognize_pil_sync(image, language)
    except Exception as exc:  # noqa: BLE001 - WinRT raises platform-specific types
        raise OcrUnavailable(
            f"Windows OCR could not read the page ({exc}). "
            f"Check that the {language} language pack is installed in Windows settings."
        ) from exc

    words: List[Word] = []
    for line in result.get("lines", []):
        for word in line.get("words", []):
            box = word["bounding_rect"]
            text = (word.get("text") or "").strip()
            if not text:
                continue
            words.append(Word(
                text=text,
                x=float(box["x"]),
                y=float(box["y"]),
                width=float(box["width"]),
                height=float(box["height"]),
            ))
    if not words:
        raise OcrUnavailable(
            "No text was recognized on this page. Scan it again with more light "
            "and less skew, or check that the page is not blank."
        )
    return OcrPage(width=float(image.width), height=float(image.height), words=words)


def load_page_image(path, page_index: int = 0):
    """The page as a PIL image, for previewing what OCR actually saw."""
    return _load_image(Path(path), page_index)
