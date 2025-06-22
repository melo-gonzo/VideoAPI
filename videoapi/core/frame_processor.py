"""Frame processing coordinator."""

import threading
import time
from typing import List, Dict, Any, Optional, Callable
from collections import deque
import numpy as np

from videoapi.algorithms.base_algorithm import BaseAlgorithm
from videoapi.utils.logging_config import get_logger

logger = get_logger("frame_processor")


class FrameProcessor:
    """Coordinates frame processing through multiple algorithms."""

    def __init__(self, max_queue_size: int = 100):
        """Initialize frame processor.

        Args:
            max_queue_size: Maximum number of frames to queue for processing
        """
        self.max_queue_size = max_queue_size
        self.algorithms: List[BaseAlgorithm] = []
        self.frame_queue = deque(maxlen=max_queue_size)
        self.results_queue = deque(maxlen=max_queue_size)

        # Threading
        self.queue_lock = threading.Lock()
        self.frame_available = threading.Condition(self.queue_lock)
        self.running = False
        self.thread = None

        # Statistics
        self.processed_frames = 0
        self.dropped_frames = 0
        self.processing_times = deque(maxlen=100)  # Keep last 100 processing times

        # Callbacks
        self.result_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        logger.info("FrameProcessor initialized")

    def add_algorithm(self, algorithm: BaseAlgorithm) -> None:
        """Add an algorithm to the processing pipeline.

        Args:
            algorithm: Algorithm to add
        """
        self.algorithms.append(algorithm)
        logger.info(f"Added algorithm: {algorithm.name}")

    def remove_algorithm(self, algorithm_name: str) -> bool:
        """Remove an algorithm from the processing pipeline.

        Args:
            algorithm_name: Name of algorithm to remove

        Returns:
            True if algorithm was removed, False if not found
        """
        for i, algo in enumerate(self.algorithms):
            if algo.name == algorithm_name:
                removed_algo = self.algorithms.pop(i)
                removed_algo.cleanup()
                logger.info(f"Removed algorithm: {algorithm_name}")
                return True

        logger.warning(f"Algorithm not found: {algorithm_name}")
        return False

    def get_algorithm(self, algorithm_name: str) -> Optional[BaseAlgorithm]:
        """Get algorithm by name.

        Args:
            algorithm_name: Name of algorithm to get

        Returns:
            Algorithm instance or None if not found
        """
        for algo in self.algorithms:
            if algo.name == algorithm_name:
                return algo
        return None

    def set_result_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set callback function for processing results.

        Args:
            callback: Function to call with processing results
        """
        self.result_callback = callback

    def start(self) -> None:
        """Start frame processing."""
        if self.running:
            logger.warning("Frame processor is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.thread.start()

        logger.info("Frame processor started")

    def stop(self) -> None:
        """Stop frame processing."""
        if not self.running:
            return

        logger.info("Stopping frame processor...")
        self.running = False

        # Notify processing thread
        with self.queue_lock:
            self.frame_available.notify_all()

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        # Cleanup algorithms
        for algo in self.algorithms:
            algo.cleanup()

        logger.info("Frame processor stopped")

    def submit_frame(self, frame: np.ndarray, frame_info: Dict[str, Any]) -> bool:
        """Submit frame for processing.

        Args:
            frame: Frame to process
            frame_info: Frame metadata

        Returns:
            True if frame was queued, False if queue is full
        """
        with self.queue_lock:
            if len(self.frame_queue) >= self.max_queue_size:
                self.dropped_frames += 1
                logger.debug("Frame queue full, dropping frame")
                return False

            self.frame_queue.append((frame.copy(), frame_info.copy()))
            self.frame_available.notify()

        return True

    def _processing_loop(self) -> None:
        """Main processing loop running in separate thread."""
        while self.running:
            frame_data = None

            with self.queue_lock:
                while len(self.frame_queue) == 0 and self.running:
                    if not self.frame_available.wait(timeout=1.0):
                        continue

                if len(self.frame_queue) > 0:
                    frame_data = self.frame_queue.popleft()

            if frame_data is None:
                continue

            frame, frame_info = frame_data

            try:
                start_time = time.time()
                results = self._process_frame(frame, frame_info)
                processing_time = time.time() - start_time

                self.processing_times.append(processing_time)
                self.processed_frames += 1

                # Store results
                result_data = {
                    "frame_info": frame_info,
                    "processing_time": processing_time,
                    "algorithm_results": results,
                    "timestamp": time.time(),
                }

                with self.queue_lock:
                    self.results_queue.append(result_data)

                # Call result callback if provided
                if self.result_callback:
                    try:
                        self.result_callback(result_data)
                    except Exception as e:
                        logger.error(f"Error in result callback: {e}")

            except Exception as e:
                logger.error(f"Error processing frame: {e}")

    def _process_frame(
        self, frame: np.ndarray, frame_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process frame through all algorithms.

        Args:
            frame: Frame to process
            frame_info: Frame metadata

        Returns:
            Dictionary of algorithm results
        """
        results = {}

        for algo in self.algorithms:
            if not algo.enabled:
                continue

            try:
                algo_start = time.time()
                result = algo.process(frame, frame_info)
                algo_time = time.time() - algo_start

                results[algo.name] = {"result": result, "processing_time": algo_time}

            except Exception as e:
                logger.error(f"Error in algorithm {algo.name}: {e}")
                results[algo.name] = {
                    "result": None,
                    "error": str(e),
                    "processing_time": 0.0,
                }

        return results

    def get_latest_results(self, count: int = 1) -> List[Dict[str, Any]]:
        """Get latest processing results.

        Args:
            count: Number of results to retrieve

        Returns:
            List of result dictionaries
        """
        with self.queue_lock:
            if count == 1:
                return [self.results_queue[-1]] if self.results_queue else []
            else:
                return list(self.results_queue)[-count:]

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with self.queue_lock:
            queue_size = len(self.frame_queue)
            results_size = len(self.results_queue)

        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times
            else 0.0
        )

        return {
            "processed_frames": self.processed_frames,
            "dropped_frames": self.dropped_frames,
            "queue_size": queue_size,
            "max_queue_size": self.max_queue_size,
            "results_size": results_size,
            "avg_processing_time": avg_processing_time,
            "algorithms_count": len(self.algorithms),
            "enabled_algorithms": [
                algo.name for algo in self.algorithms if algo.enabled
            ],
            "is_running": self.running,
        }

    def clear_queues(self) -> None:
        """Clear frame and results queues."""
        with self.queue_lock:
            self.frame_queue.clear()
            self.results_queue.clear()

        logger.info("Frame and results queues cleared")
