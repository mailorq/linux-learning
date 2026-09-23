from pathlib import Path

from linux_learning.progress import ProgressStore


def test_progress_store_saves_session_and_topic_errors() -> None:
    store = ProgressStore(Path(":memory:"))
    try:
        store.save_session(
            attempts=3,
            solved=1,
            solved_without_hints=0,
            hints_used=1,
            progress_penalty=5,
            topic_errors={"network": 2},
        )

        summary = store.load_summary()
    finally:
        store.close()

    assert summary.sessions == 1
    assert summary.attempts == 3
    assert summary.solved == 1
    assert summary.solved_without_hints == 0
    assert summary.hints_used == 1
    assert summary.progress_penalty == 5
    assert summary.topic_errors == (("network", 2),)


def test_progress_store_starts_with_empty_summary() -> None:
    store = ProgressStore(Path(":memory:"))
    try:
        summary = store.load_summary()
    finally:
        store.close()

    assert summary.sessions == 0
    assert summary.topic_errors == ()
