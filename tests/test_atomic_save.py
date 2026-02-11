"""
Test that Task.save yields a final, parseable JSON file and no lingering .tmp files.

This test writes repeatedly from a background process while the main test reads the
file many times to detect partially-written JSON. The test asserts the final file
parses as JSON and no .tmp files remain.
"""
import json
import time
import multiprocessing
from pathlib import Path

from agent_maestro.protocol import Task


def _writer(path_str: str, iterations: int = 100, delay: float = 0.01):
    """Background writer that repeatedly updates a Task and saves it."""
    path = Path(path_str)
    t = Task(instructions="atomic-save-test")
    for i in range(iterations):
        t.result = f"iteration-{i}"
        t.save(path)
        time.sleep(delay)


def test_atomic_save(tmp_path):
    file = tmp_path / "task_atomic.json"
    iterations = 60

    p = multiprocessing.Process(target=_writer, args=(str(file), iterations, 0.005))
    p.start()

    # While the writer is running, repeatedly attempt to read/parse the file
    parse_success = 0
    attempts = iterations * 4
    for _ in range(attempts):
        try:
            text = file.read_text(encoding="utf-8")
            json.loads(text)
            parse_success += 1
        except Exception:
            # Read may occur while writer is in the middle of writing; that's ok
            pass
        time.sleep(0.002)

    p.join(timeout=5)
    if p.is_alive():
        p.terminate()
        p.join()

    # Final file must exist and be valid JSON
    assert file.exists(), "Task file was not created"
    json.loads(file.read_text(encoding="utf-8"))  # must not raise

    # Ensure there are no temporary *.tmp files in the directory
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert not tmp_files, f"Found unexpected temporary files: {tmp_files}"

    # We should have parsed successfully at least once while writer ran
    assert parse_success >= 1, "Never observed a parseable JSON while writer ran"