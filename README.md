# VideoAPI

A lightweight, configurable video streaming and recording library with real-time processing capabilities.

## Features

- **NVR-like recording** with automatic file rotation and frame deduplication
- **Multi-threaded architecture** for high-performance video processing
- **Configurable via YAML** with separate credentials management
- **Real-time visualization** with customizable overlays
- **Playback mode** for processing existing video files
- **Extensible algorithm system** for custom frame processing
- **Cross-platform codec support** with automatic fallbacks

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd videoapi

# Install in development mode
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### 1. Setup Credentials (Optional)

Create `configs/creds.yaml` for camera authentication:

```yaml
cameras:
  camera1:
    username: "admin"
    password: "your_password"
    description: "Main security camera"

default:
  username: "admin"
  password: "default_password"

url_templates:
  dahua: "rtsp://{username}:{password}@{ip}:{port}/cam/realmonitor?channel={channel}&subtype={subtype}"
  hikvision: "rtsp://{username}:{password}@{ip}:{port}/Streaming/Channels/{channel}01"
```

### 2. Configure Video Source

Edit `configs/default.yaml`:

```yaml
video:
  width: 640
  height: 360
  fps: 30.0
  source:
    type: "rtsp_simple"
    ip: "192.168.1.100"
    port: 554
    path: "cam/realmonitor?channel=1&subtype=0"
    camera_id: "camera1" # References creds.yaml

recording:
  output_folder: "./recordings/%Y-%m-%d"
  duration_seconds: 120 # 2-minute segments
  fourcc_codec: "mp4v" # Works well on Mac M1
  video_format: "mp4"
  enable_deduplication: true
```

### 3. Run the Application

```bash
# Live recording with default settings
python videoapi/main.py

# With custom config and credentials
python videoapi/main.py -c configs/default.yaml --creds configs/creds.yaml

# Playback mode
python videoapi/main.py -p ./recordings/2025-06-22/12-46-23_c.mp4 -c configs/playback_config.yaml

# Headless mode (no display)
python videoapi/main.py --no-display
```

## Configuration Options

### Video Source Types

**Direct URL:**

```yaml
video:
  source:
    type: "direct"
    address: "http://192.168.1.100/mjpeg/1"
```

**RTSP with credentials:**

```yaml
video:
  source:
    type: "rtsp_simple"
    ip: "192.168.1.100"
    port: 554
    path: "cam/realmonitor?channel=1&subtype=0"
    camera_id: "camera1"
```

**Template-based URLs:**

```yaml
video:
  source:
    type: "rtsp_template"
    template: "dahua"
    camera_id: "camera1"
    ip: "192.168.1.100"
    channel: 1
    subtype: 0
```

### Recording Settings

```yaml
recording:
  output_folder: "./recordings/%Y-%m-%d"
  duration_seconds: 300 # 5-minute segments (null for no rotation)
  fourcc_codec: "mp4v" # Video codec
  video_format: "mp4" # File format
  enable_deduplication: true
  dedup_threshold: 0.95 # Similarity threshold for duplicate detection
```

### Visualization Options

```yaml
visualization:
  show_stream: true
  window_title: "VideoAPI Stream"
  show_fps: true
  show_info: true
  show_recording_status: true
  show_frame_counter: false
  show_resolution: false
```

## Codec Compatibility

**Recommended codecs by platform:**

- **Mac M1/M2:** `mp4v` + `mp4` (H.264)
- **Linux:** `XVID` + `avi` or `mp4v` + `mp4`
- **Windows:** `XVID` + `avi` or `mp4v` + `mp4`

Test codec compatibility:

```python
# Run codec test script
python test_codecs.py
```

## Command Line Usage

```bash
# Basic commands
videoapi                                    # Live mode with defaults
videoapi -c my_config.yaml                 # Custom config
videoapi --creds /secure/creds.yaml        # Specify credentials
videoapi -p video.mp4                      # Playback mode
videoapi -p video.mp4 --loop               # Loop playback
videoapi --no-display                      # Headless mode
videoapi --log-level DEBUG                 # Verbose logging

# Environment variables
export VIDEOAPI_CREDS_PATH="/secure/creds.yaml"
videoapi -c my_config.yaml
```

## Keyboard Controls

**Live Mode:**

- `q` - Quit application
- `r` - Toggle recording
- `s` - Take screenshot
- `ESC` - Exit

**Playback Mode:**

- `q` - Quit playback
- `Space` - Pause/Resume
- `s` - Take screenshot
- `ESC` - Exit

## Programmatic Usage

```python
from videoapi import VideoAPIApp

# Live recording
app = VideoAPIApp("my_config.yaml", "creds.yaml")
app.setup_live_mode()
app.start()
app.run()

# Video playback
app = VideoAPIApp()
app.setup_playback_mode("video.mp4", loop=True)
app.start()
app.run()

# Custom frame processing
from videoapi.algorithms import BaseAlgorithm

class MyAlgorithm(BaseAlgorithm):
    def process(self, frame, frame_info):
        # Your processing logic
        return {"result": "processed"}

# Add to frame processor
app.frame_processor.add_algorithm(MyAlgorithm("my_algo"))
```

## Project Structure

```
videoapi/
├── core/                    # Core components
│   ├── video_stream.py          # Video capture with threading
│   ├── video_recorder.py        # Recording with deduplication
│   ├── frame_processor.py       # Algorithm coordination
│   ├── playback_manager.py      # File playback
│   └── config_manager.py        # Configuration & credentials
├── algorithms/              # Processing algorithms
│   ├── base_algorithm.py        # Algorithm interface
│   └── frame_deduplicator.py    # Duplicate frame detection
├── utils/                   # Shared utilities
│   ├── logging_config.py        # Logging setup
│   ├── time_utils.py            # Time formatting
│   └── frame_utils.py           # Frame operations
└── visualization/           # Display components
    └── stream_viewer.py         # Real-time visualization
```

## Security Notes

- Keep `creds.yaml` secure and add to `.gitignore`
- Use environment variables for production deployments
- Consider encrypted credential storage for sensitive environments

## Batch Processing

Process multiple recordings:

```bash
# Create batch processing script
python batch_playback.py ./recordings configs/playback_config.yaml
```

## Development

```bash
# Run tests
pytest

# Install development dependencies
pip install -e ".[dev]"

# Code formatting
black videoapi/
flake8 videoapi/
```

## Troubleshooting

**Video won't record:**

- Check codec compatibility with `test_codecs.py`
- Try `mp4v` + `mp4` or `MJPG` + `avi`
- Verify disk space and permissions

**Stream connection fails:**

- Test RTSP URL with VLC or ffplay
- Check network connectivity and credentials
- Verify camera supports the stream format

**Performance issues:**

- Reduce video resolution
- Increase buffer size
- Disable frame deduplication
- Use faster codec (MJPG)

## License

See LICENSE file for details.

# Some Info

Currently using `example.py` for nuc recordings. Symbolic link in `cont_record` folder maps to this script. Used with `parameters.yaml`.

## New API

python videoapi/main.py -c ./videoapi/configs/default.yaml --creds ./videoapi/configs/creds.yaml
python videoapi/main.py -p ./recordings/2025-06-22/13-32-17_c.mp4 -c ./videoapi/configs/playback_config.yaml
