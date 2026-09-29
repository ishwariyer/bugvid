"""Video probing for bugvid: metadata and a scene-segmented timeline."""

import json
import os
import subprocess
from pathlib import Path
import re
from sys import float_repr_style


_VENDOR = Path(__file__).resolve().parent / "vendor" / "ffmpeg-7.0.2-amd64-static"


def _tool(name: str) -> str:
    """Absolute path to a vendored ffmpeg binary. BUGVID_FFMPEG_DIR overrides."""
    root = Path(os.environ.get("BUGVID_FFMPEG_DIR") or _VENDOR)
    path = root / name
    if not path.is_file():
        raise FileNotFoundError(f"{name} not found at {path}")
    return str(path)


def _run(args: list[str]) -> str:
    """Run a tool and return stdout, raising with stderr if it fails."""
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{Path(args[0]).name}: {proc.stderr.strip()[:400]}")
    return proc.stdout


def probe_metadata(path: str) -> dict:
    """Container and video-stream facts, straight from ffprobe."""
    out = _run([
        _tool("ffprobe"),
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ])
    data = json.loads(out)
    if not data.get("streams"):
        raise ValueError(f"no video stream in {path}")
    stream = data["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    return {
        "duration": float(data["format"]["duration"]),
        "width": stream["width"],
        "height": stream["height"],
        "fps": round(int(num) / (int(den) or 1), 3),
        "codec": stream["codec_name"],
    }

_PTS = re.compile(r"pts_time:(\d+\.?\d*)")
_SCORE = re.compile(r"lavfi\.scene_score=(\d+\.?\d*)")


def detect_changes(path: str, threshold: float = 0.02) -> list[tuple[float, float]]:
    """Timestamps where the picture changed, paired with their difference score."""
    out = _run([
        _tool("ffmpeg"),
        "-v", "error",
        "-i", path,
        "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
        "-an",
        "-f", "null",
        "-"
    ])
    times = _PTS.findall(out)
    scores = _SCORE.findall(out)
    return [(float(t), float(s)) for t, s in zip(times, scores)]

def build_timeline(duration: float, changes: list[tuple[float, float]] )-> list[dict]:
    """Split a recording into spans with no detected visual change."""
    boundaries = [0.0] + [t for t, _ in changes]
    scores =  [None] + [s for _, s in changes]

    segments = []
    for i, start in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else duration
        segments.append({
            "index": i + 1,
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "score": scores[i],
        })
    return segments

def format_timeline(meta: dict, segments: list[dict], threshold: float) -> str:
    """Render metadata and segments as the text block the model reads."""
    lines = [
        f"Video: {meta['width']}x{meta['height']}, {meta['fps']} fps, "
        f"{meta['codec']}, {meta['duration']:.2f}s",
        "",
        f"Timeline: {len(segments)} segments, scene threshold {threshold}.",
        "Each segment is a span with no detected visual change, so one frame",
        f"represents it. Segments cover 0.00s-{meta['duration']:.2f}s with no gaps.",
        "",
        "  #   start     end     dur   change",
    ]
    for s in segments:
        score = "-" if s["score"] is None else f"{s['score']:.3f}"
        lines.append(
            f"{s['index']:>3}  {s['start']:>6.2f}  {s['end']:>6.2f}  "
            f"{s['duration']:>6.2f}   {score}"
        )
    return "\n".join(lines)
