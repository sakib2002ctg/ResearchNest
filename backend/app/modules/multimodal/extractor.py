"""Bounded, deterministic PDF asset extraction without inference or file writes.

Captions and equation labels are layout heuristics. Extracted strings are source
text, not claims of OCR accuracy, mathematical validity or chart digitization.
"""

from __future__ import annotations

import json
import math
import multiprocessing
import re
from time import monotonic

import fitz

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENT_PAGES = 1000
MAX_ASSETS = 200
MAX_TOTAL_TEXT = 100000
MAX_PAGE_CHARACTERS = 200000
MAX_CROP_PIXELS = 4000000
MAX_PNG_BYTES = 4 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 32 * 1024 * 1024
MAX_DRAWINGS_PER_PAGE = 10000
MAX_TABLE_CELLS = 5000
EXTRACTION_TIMEOUT_SECONDS = 60

_CAPTION = re.compile(
    r"^(?P<kind>Fig(?:ure)?\.?|Chart|Diagram|Table)\s*"
    r"(?P<number>\d+(?:[.-]\d+)*[a-z]?|[IVX]+)(?=\s|[:.)-]|$)",
    re.IGNORECASE,
)
_NUMBERED_EQUATION = re.compile(
    r"(?:\b(?:Eq(?:uation)?\.?)[ \t]*\(?[ \t]*(?P<prefix>\d+)\)?[ \t]*[:.]?"
    r"|\([ \t]*(?P<suffix>\d+(?:\.\d+)*)[ \t]*\)[ \t]*$)",
    re.IGNORECASE,
)
_MATH = re.compile(r"[=±×÷∑∫√≈≤≥≠∞∂∇]|\\(?:frac|sum|int|sqrt)\b")


class _Budget:
    def __init__(self):
        self.assets = 0
        self.text_size = 0
        self.image_size = 0

    def consume(self, asset):
        self.assets += 1
        self.text_size += (
            len(asset["caption"] or "")
            + len(asset["extracted_text_or_latex"] or "")
            + len(json.dumps(asset["structured_data"], ensure_ascii=False))
        )
        self.image_size += len(asset["image_bytes"] or b"")
        if (
            self.assets > MAX_ASSETS
            or self.text_size > MAX_TOTAL_TEXT
            or self.image_size > MAX_TOTAL_IMAGE_BYTES
        ):
            raise ValueError("PDF assets exceed the extraction limit.")


def _text(value, *, limit=10000):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Unsupported PDF text value.")
    value = " ".join(value.replace("\x00", "").split())
    if len(value) > limit:
        raise ValueError("PDF asset text exceeds the extraction limit.")
    return value


def _rect(value, bounds):
    rectangle = fitz.Rect(value)
    if not all(math.isfinite(v) for v in rectangle):
        raise ValueError("Invalid PDF asset bounds.")
    rectangle = rectangle & bounds
    if rectangle.is_empty or rectangle.is_infinite:
        return None
    return rectangle


def _overlap(left, right):
    common = left & right
    area = max(0, common.width) * max(0, common.height)
    return area / max(1, min(left.width * left.height, right.width * right.height))


def _lines(page):
    # Omitting TEXT_PRESERVE_IMAGES avoids materializing every source image merely
    # to read caption geometry. Actual visual crops are rendered under pixel caps.
    flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
    blocks = page.get_text("dict", flags=flags).get("blocks", [])
    lines, total = [], 0
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            value = "".join(span.get("text", "") for span in line.get("spans", []))
            total += len(value)
            if total > MAX_PAGE_CHARACTERS or len(lines) >= 20000:
                raise ValueError("PDF page text exceeds the extraction limit.")
            text = _text(value, limit=MAX_PAGE_CHARACTERS)
            box = _rect(line["bbox"], page.rect)
            if text and box:
                lines.append({"bbox": box, "text": text})
    return sorted(lines, key=lambda line: (line["bbox"].y0, line["bbox"].x0))


def _captions(lines):
    captions = []
    for line in lines:
        match = _CAPTION.match(line["text"])
        if match:
            kind = match["kind"].lower().rstrip(".")
            captions.append(
                {
                    **line,
                    "kind": "figure" if kind in {"fig", "figure"} else kind,
                    "label": match.group(0).rstrip(" .:)-"),
                }
            )
    return captions


def _near_caption(box, captions, *, table=False):
    candidates = []
    for caption in captions:
        if (caption["kind"] == "table") != table:
            continue
        other = caption["bbox"]
        horizontal = max(0, min(box.x1, other.x1) - max(box.x0, other.x0))
        if horizontal / max(1, min(box.width, other.width)) < 0.2:
            continue
        below = other.y0 >= box.y1 - 5
        distance = max(0, other.y0 - box.y1) if below else max(0, box.y0 - other.y1)
        if distance > (100 if below else 70):
            continue
        # A body line inside an image is not a caption merely because it starts Fig.
        if _overlap(box, other) > 0.3:
            continue
        preferred_side = not below if table else below
        candidates.append((distance + (0 if preferred_side else 20), other.y0, caption))
    return min(candidates, key=lambda item: item[:2])[2] if candidates else None


def _render(page, box):
    if box.width <= 0 or box.height <= 0:
        raise ValueError("Invalid PDF crop.")
    scale = min(
        1.7,
        3000 / max(box.width, box.height),
        math.sqrt(MAX_CROP_PIXELS / (box.width * box.height)),
    )
    # Native pixmap dimensions round up; leave a small margin below the pixel cap.
    scale *= 0.995
    image = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=box, alpha=False)
    if image.width * image.height > MAX_CROP_PIXELS:
        raise ValueError("PDF crop exceeds the pixel limit.")
    data = image.tobytes("png")
    if len(data) > MAX_PNG_BYTES:
        raise ValueError("PDF crop exceeds the image limit.")
    return data


def _base(page, box, asset_type, method, caption=None):
    return {
        "asset_type": asset_type,
        "asset_label": caption["label"] if caption else None,
        "page_number": page.number + 1,
        "caption": caption["text"] if caption else None,
        "extracted_text_or_latex": None,
        "structured_data": {
            "bbox": [round(float(v), 3) for v in box],
            "extraction_method": method,
            "coordinate_space": "pdf_points_unrotated",
        },
        "image_bytes": _render(page, box),
    }


def _markdown(headers, rows):
    def cell(value):
        return (value or "").replace("\\", "\\\\").replace("|", r"\|")

    if not headers:
        return ""
    output = [
        "| " + " | ".join(cell(v) for v in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    output.extend("| " + " | ".join(cell(v) for v in row) + " |" for row in rows)
    return "\n".join(output)


def _tables(page, captions, drawings, budget):
    try:
        finder = page.find_tables(paths=drawings)
    except Exception:
        raise ValueError("PDF table detection failed.") from None
    if len(finder.tables) > MAX_ASSETS:
        raise ValueError("PDF assets exceed the extraction limit.")
    result, boxes = [], []
    for table in finder.tables:
        box = _rect(table.bbox, page.rect)
        if box is None:
            continue
        if table.row_count * table.col_count > MAX_TABLE_CELLS:
            raise ValueError("PDF table exceeds the cell limit.")
        cells = [[_text(cell) for cell in row] for row in table.extract()]
        if not cells or not any(any(cell for cell in row) for row in cells):
            continue
        headers = [_text(value) for value in table.header.names]
        # Preserve unknown/merged cells as None; no invented data or header names.
        if not headers:
            headers = [None] * table.col_count
        external = bool(table.header.external)
        rows = cells if external else cells[1:]
        asset = _base(
            page,
            box,
            "table",
            "pymupdf.find_tables",
            _near_caption(box, captions, table=True),
        )
        asset["extracted_text_or_latex"] = _markdown(headers, rows)
        asset["structured_data"].update(
            headers=headers,
            rows=rows,
            header_external=external,
            column_count=table.col_count,
            row_count=len(rows),
            raw_cells=cells,
            values_status="extracted_text",
        )
        budget.consume(asset)
        result.append(asset)
        boxes.append(box)
    return result, boxes


def _visual(page, box, captions, method, budget):
    caption = _near_caption(box, captions)
    kind = caption["kind"] if caption else "figure"
    if kind == "figure" and caption:
        if re.search(r"\b(?:chart|plot|graph)\b", caption["text"], re.IGNORECASE):
            kind = "chart"
        elif re.search(
            r"\b(?:diagram|architecture|flowchart)\b", caption["text"], re.IGNORECASE
        ):
            kind = "diagram"
    asset = _base(page, box, kind, method, caption)
    labels = _text(page.get_textbox(box), limit=10000)
    asset["extracted_text_or_latex"] = labels or None
    asset["structured_data"].update(
        values_status="not_digitized",
        classification_basis="caption" if caption else "unclassified_figure",
    )
    budget.consume(asset)
    return asset


def _equations(page, lines, excluded, budget):
    result = []
    for line in lines:
        text, box = line["text"], line["bbox"]
        if (
            _CAPTION.match(text)
            or len(text) > 600
            or any(_overlap(box, b) > 0.5 for b in excluded)
        ):
            continue
        numbered = _NUMBERED_EQUATION.search(text)
        if not _MATH.search(text) or (not numbered and len(text.split()) > 18):
            continue
        number = (numbered["prefix"] or numbered["suffix"]) if numbered else None
        asset = _base(page, box, "equation", "pdf_text_math_heuristic")
        asset["asset_label"] = f"Eq. ({number})" if number else None
        asset["extracted_text_or_latex"] = text
        context = [
            other["text"]
            for other in lines
            if 0 <= box.y0 - other["bbox"].y1 < 45
            or 0 <= other["bbox"].y0 - box.y1 < 45
        ]
        asset["structured_data"].update(
            equation_format="normalized_source_text",
            equation_verified=False,
            context="\n".join(context)[:2000],
        )
        budget.consume(asset)
        result.append(asset)
    return result


def extract_assets(payload: bytes) -> list[dict]:
    """Extract bounded tables, image/vector figures and source-text equations."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_DOCUMENT_BYTES:
        raise ValueError("Invalid PDF size.")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Invalid PDF signature.")
    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        raise ValueError("The PDF could not be opened.") from None
    try:
        if document.is_encrypted or not 0 < document.page_count <= MAX_DOCUMENT_PAGES:
            raise ValueError("The PDF cannot be extracted.")
        result, budget = [], _Budget()
        deadline = monotonic() + EXTRACTION_TIMEOUT_SECONDS
        for page in document:
            if monotonic() > deadline:
                raise TimeoutError("PDF asset extraction timed out.")
            # PyMuPDF extraction coordinates are unrotated. Render in that same
            # space without changing the persisted input bytes or source PDF.
            if page.rotation:
                page.set_rotation(0)
            lines = _lines(page)
            captions = _captions(lines)
            drawings = page.get_drawings()
            if len(drawings) > MAX_DRAWINGS_PER_PAGE:
                raise ValueError("PDF drawings exceed the extraction limit.")
            assets, table_boxes = _tables(page, captions, drawings, budget)
            image_boxes = []
            images = page.get_image_info()
            if len(images) > MAX_ASSETS:
                raise ValueError("PDF images exceed the extraction limit.")
            for image in images:
                box = _rect(image["bbox"], page.rect)
                if box is None or box.width < 12 or box.height < 12:
                    continue
                if any(
                    _overlap(box, previous) > 0.8
                    for previous in image_boxes + table_boxes
                ):
                    continue
                assets.append(
                    _visual(page, box, captions, "rendered_embedded_image", budget)
                )
                image_boxes.append(box)
            clusters = page.cluster_drawings(
                drawings=drawings, x_tolerance=12, y_tolerance=12
            )
            if len(clusters) > MAX_ASSETS:
                raise ValueError("PDF vector regions exceed the extraction limit.")
            for cluster in clusters:
                box = _rect(cluster, page.rect)
                if box is None or box.width < 24 or box.height < 24:
                    continue
                if any(
                    _overlap(box, previous) > 0.6
                    for previous in table_boxes + image_boxes
                ):
                    continue
                assets.append(
                    _visual(page, box, captions, "rendered_vector_cluster", budget)
                )
                image_boxes.append(box)
            assets.extend(_equations(page, lines, table_boxes + image_boxes, budget))
            result.extend(assets)
        return result
    finally:
        document.close()


def _extract_child(payload, sender):
    try:
        sender.send(extract_assets(payload))
    except Exception:
        sender.send(None)
    finally:
        sender.close()


def extract_assets_bounded(payload: bytes) -> list[dict]:
    """Isolate the native parser in a killable process with a fixed deadline."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_DOCUMENT_BYTES:
        raise ValueError("Invalid PDF size.")
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_extract_child, args=(payload, sender), daemon=True
    )
    try:
        process.start()
        sender.close()
        if not receiver.poll(EXTRACTION_TIMEOUT_SECONDS + 5):
            raise TimeoutError("PDF asset extraction timed out.")
        try:
            result = receiver.recv()
        except (EOFError, OSError):
            raise ValueError("PDF asset extraction failed.") from None
        if result is None:
            raise ValueError("PDF assets could not be extracted within the limits.")
        return result
    finally:
        receiver.close()
        sender.close()
        if process.pid is not None:
            process.join(0.1)
            if process.is_alive():
                process.terminate()
                process.join(2)
