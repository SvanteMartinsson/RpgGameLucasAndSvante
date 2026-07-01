"""B11 fog-of-war: a compact bitset over the overworld tiles (row-major, one bit
per tile). Pure Python (no pygame) so the reveal/query rules are unit-testable.

The bitset lives on the player as an opaque `bytearray` (persisted as base64); the
presentation owns the tile semantics via these helpers. Reveal is O(revealed
tiles), membership O(1).
"""

from __future__ import annotations


def _byte_len(n_tiles: int) -> int:
    return (n_tiles + 7) // 8


def ensure_capacity(bits: bytearray, n_tiles: int) -> bytearray:
    """Grow the bitset in place so it can hold n_tiles bits (older/empty saves
    start short)."""
    need = _byte_len(n_tiles)
    if len(bits) < need:
        bits.extend(b"\x00" * (need - len(bits)))
    return bits


def reveal_rect(bits: bytearray, width: int, height: int,
                left: int, right: int, top: int, bottom: int) -> None:
    """Set every tile in the half-open [left,right) x [top,bottom) rectangle,
    clamped to the map. O(rectangle area)."""
    ensure_capacity(bits, width * height)
    y0, y1 = max(0, top), min(height, bottom)
    x0, x1 = max(0, left), min(width, right)
    for y in range(y0, y1):
        base = y * width
        for x in range(x0, x1):
            i = base + x
            bits[i >> 3] |= 1 << (i & 7)


def is_revealed(bits: bytearray, width: int, x: int, y: int) -> bool:
    i = y * width + x
    byte = i >> 3
    return byte < len(bits) and bool((bits[byte] >> (i & 7)) & 1)


def count_revealed(bits: bytearray) -> int:
    return sum(bin(byte).count("1") for byte in bits)
