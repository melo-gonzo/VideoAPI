# Video Recording System Thread Architecture

## Overview of Threads
The system uses three main threads to handle different aspects of video processing:

1. **Capture Thread** (VideoStream._read_frames)
2. **Read Thread** (read_video_stream)
3. **Write Thread** (VideoRecorder._write_thread)

## Thread Details

### 1. Capture Thread (VideoStream._read_frames)
```python
self.thread = threading.Thread(target=self._read_frames)
```

**Purpose:**
- Continuously captures frames from the video source
- Maintains the frame buffer
- Handles stream disconnections and reconnections

**Key Operations:**
- Initializes video capture
- Reads frames as quickly as possible from the source
- Stores frames in a thread-safe deque (frame_buffer)
- Manages frame counters and timestamps
- Handles stream failures and reconnection logic

**Benefits:**
- Dedicated thread ensures no frames are missed due to processing delays
- Can run at maximum capture speed independent of processing
- Quick recovery from stream interruptions

### 2. Read Thread (read_video_stream)
```python
read_thread = threading.Thread(target=read_video_stream, args=(vs, video_recorder, recording_duration))
```

**Purpose:**
- Acts as an intermediary between capture and write operations
- Manages recording sessions and timing
- Coordinates frame transfer from buffer to writer

**Key Operations:**
- Monitors recording status
- Retrieves batches of frames from VideoStream
- Queues frames for writing
- Handles recording duration and file rotation
- Manages recording start/stop operations

**Benefits:**
- Decouples capture from writing operations
- Handles recording logic without affecting capture speed
- Enables batch processing of frames for efficiency

### 3. Write Thread (VideoRecorder._write_thread)
```python
self.write_thread = threading.Thread(target=self._write_thread)
```

**Purpose:**
- Handles all disk I/O operations
- Manages the writing queue
- Ensures frames are written in order

**Key Operations:**
- Processes frames from the write queue
- Performs frame resizing
- Writes frames to disk
- Maintains write counter for duplicate prevention
- Handles file operations (creation, closing)

**Benefits:**
- Isolates slow disk operations from capture
- Prevents frame drops during disk writes
- Enables buffering during high load

## Thread Synchronization

### Critical Sections and Locks
1. **Frame Buffer Lock**
```python
self.frame_lock = threading.Lock()
self.frame_available = threading.Condition(self.frame_lock)
```
- Protects the frame buffer during read/write operations
- Enables thread signaling for new frames
- Prevents race conditions in frame access

2. **Write Lock**
```python
self.write_lock = threading.Lock()
```
- Protects video writer operations
- Ensures atomic file operations
- Prevents concurrent access to disk resources

### Data Flow and Queues
```
[Camera Source] → Capture Thread → Frame Buffer → Read Thread → Write Queue → Write Thread → [Disk]
```

Each stage uses thread-safe containers:
- `frame_buffer`: thread-safe deque for captured frames
- `frame_queue`: thread-safe deque for frames pending write

## Benefits of This Architecture

1. **Maximum Frame Capture**
- Capture thread runs independently at maximum speed
- No blocking from processing or disk operations
- Large buffer handles burst situations

2. **Reliable Recording**
- Separate write thread handles slow disk operations
- Frame ordering maintained through counters
- Automatic recovery from failures

3. **Resource Management**
- CPU utilization spread across threads
- Memory usage controlled through buffer sizes
- I/O operations isolated from critical timing

4. **Scalability**
- Easy to add processing steps between capture and write
- Can adjust buffer sizes based on system capabilities
- Modular design allows for feature additions

## Example Flow

1. **Frame Capture:**
```python
with self.frame_lock:
    self.frame_buffer.append((self.frame_counter, frame.copy(), current_time))
    self.frame_available.notify()
```

2. **Frame Processing:**
```python
new_frames = vs.get_latest_frames(video_recorder.last_written_frame_counter)
if new_frames:
    video_recorder.write_frames(new_frames)
```

3. **Frame Writing:**
```python
frame_counter, frame, _ = self.frame_queue.popleft()
with self.write_lock:
    self.video_writer.write(frame)
```

This architecture ensures maximum frame capture while maintaining system stability and preventing frame drops. Each thread has a specific responsibility and is optimized for its task, while the synchronization mechanisms ensure safe data transfer between threads.
