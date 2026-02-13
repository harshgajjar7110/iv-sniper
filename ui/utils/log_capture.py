"""
Log Capture Utilities for Live Scanner Updates

Provides thread-safe log capturing and progress tracking for the scanner UI.
"""

import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from collections import deque


@dataclass
class ScanProgress:
    """Progress update from the scanner."""
    current: int          # Number of stocks processed
    total: int            # Total stocks to process
    qualified: int        # Number of stocks that qualified
    message: str          # Current status message
    
    @property
    def percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total == 0:
            return 0.0
        return (self.current / self.total) * 100


@dataclass
class LogMessage:
    """A single log message captured from the scanner."""
    timestamp: str
    level: str
    logger_name: str
    message: str
    
    def format(self) -> str:
        """Format the log message for display."""
        return f"[{self.timestamp}] [{self.level}] {self.message}"


class QueueHandler(logging.Handler):
    """
    A logging handler that sends log records to a queue.
    
    Used to capture scanner logs and display them in real-time in the UI.
    """
    
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record: logging.LogRecord) -> None:
        """Put the log record into the queue."""
        try:
            log_msg = LogMessage(
                timestamp=datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record)
            )
            self.log_queue.put_nowait(log_msg)
        except Exception:
            self.handleError(record)


class LogCapture:
    """
    Context manager for capturing scanner logs.
    
    Usage:
        with LogCapture() as capture:
            run_scan(progress_callback=capture.progress_callback)
            logs = capture.get_logs()
            progress = capture.get_progress()
    """
    
    # Loggers to capture (scanner and related modules)
    CAPTURED_LOGGERS = [
        "scanner.scanner",
        "scanner.iv_scorer",
        "core.trend_detector",
        "core.iv_calculator",
        "core.instrument_master",
    ]
    
    def __init__(self, max_logs: int = 500):
        self.log_queue: queue.Queue[LogMessage] = queue.Queue()
        self.progress_lock = threading.Lock()
        self._progress = ScanProgress(current=0, total=0, qualified=0, message="Initializing...")
        self._handlers: list[tuple[logging.Logger, logging.Handler]] = []
        self._max_logs = max_logs
        self._logs: deque[LogMessage] = deque(maxlen=max_logs)
    
    def __enter__(self) -> "LogCapture":
        """Set up log capturing."""
        # Create queue handler
        self.queue_handler = QueueHandler(self.log_queue)
        self.queue_handler.setLevel(logging.INFO)
        self.queue_handler.setFormatter(logging.Formatter("%(message)s"))
        
        # Attach to all relevant loggers
        for logger_name in self.CAPTURED_LOGGERS:
            logger = logging.getLogger(logger_name)
            logger.addHandler(self.queue_handler)
            self._handlers.append((logger, self.queue_handler))
        
        # Also capture root scanner logger
        root_scanner = logging.getLogger("scanner")
        if self.queue_handler not in root_scanner.handlers:
            root_scanner.addHandler(self.queue_handler)
            self._handlers.append((root_scanner, self.queue_handler))
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up log capturing."""
        for logger, handler in self._handlers:
            logger.removeHandler(handler)
    
    def progress_callback(self, current: int, total: int, message: str, qualified: int = 0) -> None:
        """
        Callback for scanner progress updates.
        
        Args:
            current: Number of stocks processed so far
            total: Total number of stocks to process
            message: Status message
            qualified: Number of stocks that qualified
        """
        with self.progress_lock:
            self._progress = ScanProgress(
                current=current,
                total=total,
                qualified=qualified,
                message=message
            )
    
    def get_progress(self) -> ScanProgress:
        """Get the current progress state."""
        with self.progress_lock:
            return self._progress
    
    def get_new_logs(self) -> list[LogMessage]:
        """
        Get all new log messages since last call.
        
        Returns:
            List of LogMessage objects that haven't been retrieved yet.
        """
        new_logs = []
        try:
            while True:
                log_msg = self.log_queue.get_nowait()
                self._logs.append(log_msg)
                new_logs.append(log_msg)
        except queue.Empty:
            pass
        return new_logs
    
    def get_all_logs(self) -> list[LogMessage]:
        """Get all captured logs."""
        # First, drain any remaining logs from queue
        self.get_new_logs()
        return list(self._logs)
    
    def format_logs(self, logs: list[LogMessage] | None = None) -> str:
        """
        Format logs for display.
        
        Args:
            logs: List of logs to format, or None to use all captured logs.
        
        Returns:
            Formatted string of log messages.
        """
        if logs is None:
            logs = self.get_all_logs()
        return "\n".join(log.format() for log in logs)


def create_progress_callback(
    progress_queue: queue.Queue,
    lock: threading.Lock,
    progress_state: dict
) -> Callable[[int, int, str, int], None]:
    """
    Create a thread-safe progress callback function.
    
    This is an alternative to using LogCapture class directly,
    useful when you need more control over the callback.
    
    Args:
        progress_queue: Queue to put progress updates into
        lock: Thread lock for state updates
        progress_state: Dictionary to store current progress state
    
    Returns:
        A callback function that can be passed to run_scan()
    """
    def callback(current: int, total: int, message: str, qualified: int = 0) -> None:
        with lock:
            progress_state["current"] = current
            progress_state["total"] = total
            progress_state["qualified"] = qualified
            progress_state["message"] = message
        
        progress_queue.put(ScanProgress(
            current=current,
            total=total,
            qualified=qualified,
            message=message
        ))
    
    return callback
