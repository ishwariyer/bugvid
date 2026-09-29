"""Phase 0 gate: does this MCP client actually deliver tool-result images to the
model, or silently drop them?

Three tools (probe_text / probe_image / probe_image_via_path) let us triangulate.
The PNG is built from scratch with only zlib + struct so there is zero chance an
imaging library is the thing that's broken.
"""

import os
import random
import struct
import sys
import tempfile
import zlib
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer

_FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
}

_ALPHABET = "AEFGIR"  # every letter _FONT knows how to draw


def _marker() -> str:
    """Five random letters, drawn only from glyphs the font actually has."""
    return "".join(random.choices(_ALPHABET, k=5))


def _marker_from_env() -> str | None:
    """Let the operator pin the image marker so nobody else can learn it."""
    word = (os.environ.get("BUGVID_PROBE_WORD") or "").upper()
    if not word:
        return None
    missing = sorted(set(word) - set(_ALPHABET))
    if missing:
        print(
            f"[bugvid-probe] ignoring BUGVID_PROBE_WORD: no glyph for {missing}",
            file=sys.stderr,
        )
        return None
    return word


# The word only the pixels carry. Never appears in a tool name or description.
IMAGE_MARKER = _marker_from_env() or _marker()

# A separate word for the text control, so it can never leak the answer above.
TEXT_MARKER = _marker()
while TEXT_MARKER == IMAGE_MARKER:
    TEXT_MARKER = _marker()


SCALE = 12
PAD = 16
FG = (10, 10, 10)
BG = (255, 255, 255)

def _chunk(kind: bytes, data: bytes) -> bytes:
    """One Png chunk: length, type, payload, CRC over type+payload"""
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )

def _render(word: str) -> bytes:
    glyphs = [_FONT[ch] for ch in word]
    cols = len(glyphs) * 6 - 1 #5px per glyph, 1px gap between
    rows = 7

    width = cols * SCALE + 2 * PAD
    height = rows * SCALE + 2 * PAD

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        gy = (y - PAD) // SCALE
        for x in range(width):
            gx = (x - PAD) // SCALE
            on = False
            if 0 <= gy < rows and 0 <= gx < cols:
                glyph, col = divmod(gx, 6)
                on = col < 5 and glyphs[glyph][gy][col] == "1"
            raw.extend(FG if on else BG)

    return (
    b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b"")
    )

server = MCPServer("bugvid-probe")


@server.tool()
def probe_text() -> str:
    """Return a short diagnostic status string."""
    return f"probe_text ok, marker={TEXT_MARKER}"

@server.tool()
def probe_image() -> Image:
    """Return a small PNG generated in memory."""
    return Image(data=_render(IMAGE_MARKER), format="png")

@server.tool()
def probe_image_via_path() -> Image:
    """Return a small PNG that was written to a file on disk."""
    path = Path(tempfile.gettempdir()) / "bugvid_probe.png"
    path.write_bytes(_render(IMAGE_MARKER))
    return Image(path=path)

if __name__ == "__main__":
    # stderr only: stdout belongs to the JSON-RPC stream on stdio transport.
    print(f"[bugvid-probe] image marker: {IMAGE_MARKER}", file=sys.stderr)
    print(f"[bugvid-probe] text  marker: {TEXT_MARKER}", file=sys.stderr)
    server.run()


