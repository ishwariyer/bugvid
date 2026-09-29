# bugvid

An MCP server that lets a coding agent read a screen recording of a bug.

Instead of sampling frames at fixed intervals, bugvid uses ffmpeg scene
detection to split a recording into segments where nothing visibly changes.
Every segment is represented by one frame, and the segments cover the whole
video with no gaps — so the agent can honestly say what it has and hasn't seen.

## Status

Early development.

- [x] `probe_video` — metadata + scene-segmented timeline (text only)
- [ ] Frame extraction with timestamps burned in
- [ ] Bug analysis with observed / inferred / unknown claims
- [ ] User confirmation step
- [ ] Handoff prompt for a coding agent

## Requirements

- Python 3.12
- `mcp` 2.0.0
- A static build of ffmpeg + ffprobe (Linux amd64)

## Setup

```bash
git clone https://github.com/ishwariyer/bugvid.git
cd bugvid
python3 -m venv .venv
.venv/bin/pip install "mcp==2.0.0"
```

### ffmpeg

The binaries are not committed. Download a static amd64 build from
https://johnvansickle.com/ffmpeg/ and extract it into `vendor/`:

```bash
mkdir -p vendor
tar -xf ffmpeg-*-amd64-static.tar.xz -C vendor
```

By default bugvid looks in `vendor/ffmpeg-7.0.2-amd64-static/`. To use a
different folder, set:

```bash
export BUGVID_FFMPEG_DIR=/path/to/folder/containing/ffmpeg
```

## Running

```bash
.venv/bin/python server.py
```

Register it with an MCP client over stdio, e.g.:

```json
{
  "mcpServers": {
    "bugvid": {
      "command": "/path/to/bugvid/.venv/bin/python",
      "args": ["/path/to/bugvid/server.py"]
    }
  }
}
```

## Tools

### `probe_video(path, threshold=0.02)`

Returns the video's size, frame rate, codec and duration, followed by a
timeline table:

```
  #   start     end     dur   change
  1    0.00    3.40    3.40   -
  2    3.40    7.12    3.72   0.043
```

`threshold` is scene-change sensitivity (0–1). Keep it low for screen
recordings: a small UI change such as a button changing colour can score
under 0.05, well below the 0.3–0.4 usually used for film.

## Project layout

| File | Purpose |
|---|---|
| `server.py` | MCP layer — registers tools, no video logic |
| `video.py` | ffprobe/ffmpeg calls and timeline building, no MCP imports |
| `probe_image_support.py` | Diagnostic server: checks a client passes tool-result images to the model |
