"""Pure geometry helpers. Top-left origin throughout (l < r, t < b)."""

from __future__ import annotations


def normalize_tl(box: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Return (l, t, r, b) with l<=r and t<=b regardless of input order."""
    l, t, r, b = box
    return (min(l, r), min(t, b), max(l, r), max(t, b))


def area(box: tuple[float, float, float, float]) -> float:
    l, t, r, b = box
    return max(0.0, r - l) * max(0.0, b - t)


def centroid(box: tuple[float, float, float, float]) -> tuple[float, float]:
    l, t, r, b = box
    return ((l + r) / 2.0, (t + b) / 2.0)


def contains_point(box: tuple[float, float, float, float], x: float, y: float) -> bool:
    l, t, r, b = box
    return l <= x <= r and t <= y <= b


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    la, ta, ra, ba = a
    lb, tb, rb, bb = b
    iw = max(0.0, min(ra, rb) - max(la, lb))
    ih = max(0.0, min(ba, bb) - max(ta, tb))
    inter = iw * ih
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def contains_box(
    outer: tuple[float, float, float, float],
    inner: tuple[float, float, float, float],
    tol: float = 0.5,
) -> bool:
    """True if `inner` lies inside `outer` (with a small tolerance)."""
    ol, ot, or_, ob = outer
    il, it, ir_, ib = inner
    return il >= ol - tol and it >= ot - tol and ir_ <= or_ + tol and ib <= ob + tol
