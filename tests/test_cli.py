#!/usr/bin/env python3
"""
Test suite for PolyLlama CLI functionality
"""

import pytest
import threading
import time
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock
import sys
import io

# Add parent directory to path to import builder modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from builder.cli import PolyLlamaCLI


class TestLogTailing:
    """Test the log tailing functionality"""

    def test_tail_log_file_basic(self, tmp_path):
        """Test basic log tailing with 3 lines"""
        # Create a temporary log file
        log_file = tmp_path / "test.log"

        # Create CLI instance and override log file path
        cli = PolyLlamaCLI()
        cli.log_file = log_file

        # Write initial content
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        # Capture output
        captured_output = io.StringIO()
        stop_event = threading.Event()

        # Mock print to capture output
        with mock.patch("builtins.print") as mock_print:
            # Start tailing in a thread
            tail_thread = threading.Thread(target=cli.tail_log_file, args=(stop_event,))
            tail_thread.daemon = True
            tail_thread.start()

            # Let it run briefly
            time.sleep(0.3)

            # Stop tailing
            stop_event.set()
            tail_thread.join(timeout=1)

            # Check that print was called with expected content
            print_calls = mock_print.call_args_list
            assert any("Line 1" in str(call) for call in print_calls)
            assert any("Line 2" in str(call) for call in print_calls)
            assert any("Line 3" in str(call) for call in print_calls)

    def test_tail_log_file_dynamic_updates(self, tmp_path):
        """Test log tailing with dynamic updates"""
        # Create a temporary log file
        log_file = tmp_path / "test.log"
        log_file.write_text("")

        # Create CLI instance and override log file path
        cli = PolyLlamaCLI()
        cli.log_file = log_file

        stop_event = threading.Event()
        lines_seen = []

        # Mock print to capture output
        def mock_print_fn(*args, **kwargs):
            # Extract lines that contain our test content
            content = " ".join(str(arg) for arg in args)
            if "Test line" in content and "│" in content:
                lines_seen.append(content)

        with mock.patch("builtins.print", side_effect=mock_print_fn):
            # Start tailing in a thread
            tail_thread = threading.Thread(target=cli.tail_log_file, args=(stop_event,))
            tail_thread.daemon = True
            tail_thread.start()

            # Write lines dynamically
            time.sleep(0.2)
            with open(log_file, "a") as f:
                f.write("Test line 1\n")
                f.flush()

            time.sleep(0.2)
            with open(log_file, "a") as f:
                f.write("Test line 2\n")
                f.flush()

            time.sleep(0.2)
            with open(log_file, "a") as f:
                f.write("Test line 3\n")
                f.write("Test line 4\n")
                f.flush()

            time.sleep(0.3)

            # Stop tailing
            stop_event.set()
            tail_thread.join(timeout=1)

            # Verify we saw the lines
            assert any("Test line 1" in line for line in lines_seen)
            assert any("Test line 2" in line for line in lines_seen)
            assert any("Test line 3" in line for line in lines_seen)
            assert any("Test line 4" in line for line in lines_seen)

    def test_tail_log_file_only_shows_last_3_lines(self, tmp_path):
        """Test that only the last 3 lines are displayed"""
        # Create a temporary log file
        log_file = tmp_path / "test.log"

        # Create CLI instance and override log file path
        cli = PolyLlamaCLI()
        cli.log_file = log_file

        # Write many lines
        with open(log_file, "w") as f:
            for i in range(10):
                f.write(f"Line {i+1}\n")

        stop_event = threading.Event()
        final_lines = []

        # Mock print to capture output
        def mock_print_fn(*args, **kwargs):
            content = " ".join(str(arg) for arg in args)
            if "Line" in content and "│" in content:
                final_lines.append(content)

        with mock.patch("builtins.print", side_effect=mock_print_fn):
            # Start tailing
            tail_thread = threading.Thread(target=cli.tail_log_file, args=(stop_event,))
            tail_thread.daemon = True
            tail_thread.start()

            # Let it process
            time.sleep(0.3)

            # Stop tailing
            stop_event.set()
            tail_thread.join(timeout=1)

            # Get the last 3 unique lines we saw
            seen_lines = []
            for line in final_lines:
                if line not in seen_lines:
                    seen_lines.append(line)
            last_three = seen_lines[-3:]

            # Should only see lines 8, 9, 10
            assert any("Line 8" in line for line in last_three)
            assert any("Line 9" in line for line in last_three)
            assert any("Line 10" in line for line in last_three)
            assert not any("Line 7" in line for line in last_three)

    def test_tail_log_file_truncates_long_lines(self, tmp_path):
        """Test that long lines are truncated"""
        # Create a temporary log file
        log_file = tmp_path / "test.log"

        # Create CLI instance and override log file path
        cli = PolyLlamaCLI()
        cli.log_file = log_file

        # Write a very long line
        long_line = "A" * 150
        log_file.write_text(f"{long_line}\n")

        stop_event = threading.Event()
        truncated_seen = False

        # Mock print to capture output
        def mock_print_fn(*args, **kwargs):
            content = " ".join(str(arg) for arg in args)
            if "..." in content and "AAA" in content:
                nonlocal truncated_seen
                truncated_seen = True

        with mock.patch("builtins.print", side_effect=mock_print_fn):
            # Start tailing
            tail_thread = threading.Thread(target=cli.tail_log_file, args=(stop_event,))
            tail_thread.daemon = True
            tail_thread.start()

            # Let it process
            time.sleep(0.3)

            # Stop tailing
            stop_event.set()
            tail_thread.join(timeout=1)

            # Verify truncation happened
            assert truncated_seen

    def test_tail_log_file_handles_missing_file(self):
        """Test that tailing handles missing log file gracefully"""
        # Create CLI instance with non-existent log file
        cli = PolyLlamaCLI()
        cli.log_file = Path("/tmp/non_existent_file_12345.log")

        stop_event = threading.Event()

        # This should not raise an exception
        tail_thread = threading.Thread(target=cli.tail_log_file, args=(stop_event,))
        tail_thread.daemon = True
        tail_thread.start()

        # Let it run briefly
        time.sleep(0.2)

        # Stop without error
        stop_event.set()
        tail_thread.join(timeout=1)

        # If we get here without exception, test passes
        assert True


class TestCLIIntegration:
    """Test CLI integration with mocked subprocess calls"""

    def test_launch_with_log_tailing(self, tmp_path):
        """Test that launch uses log tailing for non-debug mode"""
        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("builder.detector.GPUDetector.detect_gpu_groups") as mock_detect:
                # Mock GPU detection
                mock_detect.return_value = [{"name": "RTX 3090", "indices": [0]}]

                # Mock subprocess calls to succeed
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                # Create CLI instance with temp paths
                cli = PolyLlamaCLI()
                cli.built_dir = tmp_path / "built"
                cli.built_dir.mkdir()
                cli.compose_file = cli.built_dir / "docker-compose.yml"
                cli.log_file = cli.built_dir / "test.log"

                # Create a mock compose file
                cli.compose_file.write_text("version: '3.8'\nservices:\n  test: {}")

                # Mock threading to verify tail thread is created
                original_thread = threading.Thread
                tail_thread_created = False

                def mock_thread(*args, **kwargs):
                    nonlocal tail_thread_created
                    if "target" in kwargs and kwargs["target"].__name__ == "tail_log_file":
                        tail_thread_created = True
                    return original_thread(*args, **kwargs)

                with mock.patch("threading.Thread", side_effect=mock_thread):
                    with mock.patch("builtins.print"):  # Suppress output
                        # Run launch in non-debug mode
                        cli.launch(debug=False, build=False, dev_mode=False)

                # Verify tail thread was created
                assert (
                    tail_thread_created
                ), "Log tailing thread should be created in non-debug mode"

    def test_launch_debug_no_tailing(self, tmp_path):
        """Test that debug mode doesn't use log tailing"""
        with mock.patch("subprocess.run") as mock_run:
            with mock.patch("builder.detector.GPUDetector.detect_gpu_groups") as mock_detect:
                # Mock GPU detection
                mock_detect.return_value = [{"name": "RTX 3090", "indices": [0]}]

                # Mock subprocess calls to succeed
                mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

                # Create CLI instance with temp paths
                cli = PolyLlamaCLI()
                cli.built_dir = tmp_path / "built"
                cli.built_dir.mkdir()
                cli.compose_file = cli.built_dir / "docker-compose.yml"
                cli.log_file = cli.built_dir / "test.log"

                # Create a mock compose file
                cli.compose_file.write_text("version: '3.8'\nservices:\n  test: {}")

                # Mock threading to verify tail thread is NOT created
                original_thread = threading.Thread
                tail_thread_created = False

                def mock_thread(*args, **kwargs):
                    nonlocal tail_thread_created
                    if "target" in kwargs and kwargs["target"].__name__ == "tail_log_file":
                        tail_thread_created = True
                    return original_thread(*args, **kwargs)

                with mock.patch("threading.Thread", side_effect=mock_thread):
                    with mock.patch("builtins.print"):  # Suppress output
                        # Run launch in debug mode
                        cli.launch(debug=True, build=False, dev_mode=False)

                # Verify tail thread was NOT created
                assert (
                    not tail_thread_created
                ), "Log tailing thread should not be created in debug mode"
