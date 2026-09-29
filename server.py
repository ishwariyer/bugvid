"""bugvid MCP server: tools a coding agent can call to read a bug recording."""

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import video

server = MCPServer("bugvid")


@server.tool(structured_output=False)
def probe_video(path: str, threshold: float = 0.02) -> str:
    """Summarise a screen recording as a scene-segmented timeline.

        Returns the video's dimensions and duration, then a table of segments.
        Each segment is a span with no detected visual change, and the segments
        tile the entire recording, so nothing is unaccounted for. Call this
        first, before requesting any frames.

        threshold is the scene-change sensitivity, 0-1. Screen recordings need
        a low value; localized UI changes score below 0.05.
    """
    target = Path(path).expanduser()
    if not target.is_file():
        raise ValueError(f"no such file: {target}")

    meta = video.probe_metadata(str(target))
    changes = video.detect_changes(str(target), threshold)
    segments = video.build_timeline(meta["duration"], changes)
    return video.format_timeline(meta, segments, threshold)

if __name__ == "__main__":
    print("bugvid server is ready", file=sys.stderr)
    server.run()
