"""traditional.py - Tier 1 readers: Tesseract and RapidOCR.

Both return the same shape so the rules extractor and the two-reader
agreement check do not care which engine produced the text:

    {
      "engine": "tesseract" | "rapidocr",
      "lines": [str, ...],              # top-to-bottom text lines
      "tokens": [{"text": str, "conf": float}, ...],   # conf in [0, 1]
                                         # rapidocr tokens also carry "box" (four [x, y]
                                         # corners, original-image pixels), "id" (index)
                                         # and "line" (index into lines); added
                                         # 2026-10-31, caches written before lack them
      "mean_conf": float,                # mean token confidence
      "low_conf_share": float,           # share of tokens below 0.5
      "latency_ms": int,
    }

SROIE scans are huge (about 5000 x 7000 px). RapidOCR's detector is quadratic
in image area, so it works on a copy downscaled to RAPID_MAX_SIDE; Tesseract
prefers high resolution and gets the original.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
]
RAPID_MAX_SIDE = 2000


def _summarize(engine: str, lines: list[str], tokens: list[dict], t0: float) -> dict:
    confs = [t["conf"] for t in tokens if t["conf"] is not None]
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    low = sum(1 for c in confs if c < 0.5) / len(confs) if confs else 1.0
    return {
        "engine": engine,
        "lines": lines,
        "tokens": tokens,
        "mean_conf": round(mean_conf, 4),
        "low_conf_share": round(low, 4),
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


def run_tesseract(image_path: str | Path, lang: str = "eng") -> dict:
    import pytesseract
    from PIL import Image

    for cand in _TESSERACT_CANDIDATES:
        if os.path.exists(cand):
            pytesseract.pytesseract.tesseract_cmd = cand
            break
    t0 = time.perf_counter()
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, lang=lang, config="--psm 6",
                                     output_type=pytesseract.Output.DICT)
    tokens: list[dict] = []
    lines_map: dict[tuple, list[str]] = {}
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        conf = None if conf < 0 else conf / 100.0
        tokens.append({"text": text, "conf": conf})
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines_map.setdefault(key, []).append(text)
    lines = [" ".join(words) for _, words in sorted(lines_map.items())]
    return _summarize("tesseract", lines, tokens, t0)


_rapid_engine = None


def run_rapidocr(image_path: str | Path, max_side: int = RAPID_MAX_SIDE) -> dict:
    global _rapid_engine
    import numpy as np
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    if _rapid_engine is None:
        _rapid_engine = RapidOCR()
    t0 = time.perf_counter()
    img = Image.open(image_path).convert("RGB")
    orig_w, orig_h = img.size
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side))
    sx, sy = orig_w / img.size[0], orig_h / img.size[1]   # detector pixels -> original pixels
    arr = np.asarray(img)[:, :, ::-1].copy()          # RGB -> BGR as OpenCV expects
    result, _elapse = _rapid_engine(arr)
    tokens: list[dict] = []
    rows: list[tuple[float, float, str]] = []
    heights: list[float] = []
    for box, text, score in (result or []):
        text = (text or "").strip()
        if not text:
            continue
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        rows.append((sum(ys) / 4.0, min(xs), text))
        heights.append(max(ys) - min(ys))
        tokens.append({"text": text, "conf": float(score),
                       "box": [[round(p[0] * sx), round(p[1] * sy)] for p in box]})
    lines, line_of = group_lines(rows, heights)
    for i, tok in enumerate(tokens):
        tok["id"] = i
        tok["line"] = line_of[i]
    return _summarize("rapidocr", lines, tokens, t0)


def group_lines(rows: list[tuple[float, float, str]], heights: list[float]) -> tuple[list[str], list[int]]:
    """Group detections into lines by vertical proximity, then order left to right.

    rows: (centre_y, min_x, text) per detection, detector pixels, in detection order.
    Returns the line strings top to bottom and, per detection, the index of its line.
    Tolerance scales with the text height: a right-aligned amount sits in the
    same row as its label when their centres differ by less than ~60% of a
    text line. (A fixed pixel tolerance split "Total ... :" from its amount.)
    """
    med_h = sorted(heights)[len(heights) // 2] if heights else 20.0
    line_tol = max(6.0, 0.6 * med_h)
    lines: list[str] = []
    line_of = [0] * len(rows)
    current: list[tuple[float, str, int]] = []
    anchor_y: float | None = None
    for i in sorted(range(len(rows)), key=lambda j: rows[j]):
        y, x, text = rows[i]
        if anchor_y is not None and abs(y - anchor_y) > line_tol:
            lines.append(" ".join(t for _, t, _ in sorted(current)))
            current = []
            anchor_y = None
        current.append((x, text, i))
        line_of[i] = len(lines)
        anchor_y = y if anchor_y is None else (anchor_y + y) / 2.0
    if current:
        lines.append(" ".join(t for _, t, _ in sorted(current)))
    return lines, line_of


ENGINES = {"tesseract": run_tesseract, "rapidocr": run_rapidocr}
