"""
AI Solution Builder — Parallel Workstream Scheduler with Conflict Prevention

Orchestrates independent workstreams (Modernization Workstream vs Feature Extension Workstream)
in parallel while automatically serializing tasks that modify intersecting critical files
(such as package.json, requirements.txt, or root routers).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskWorkstream:
    """Represents a discrete modernization or feature extension work unit."""

    task_id: str
    name: str
    workstream: str  # "modernization" | "feature_extension" | "validation" | "infra"
    description: str
    files_to_modify: list[str]
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "serialized_wait"
    execute_fn: Optional[Callable[[], Awaitable[Any]]] = None
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "workstream": self.workstream,
            "description": self.description,
            "files_to_modify": self.files_to_modify,
            "dependencies": self.dependencies,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class ConflictGraphScheduler:
    """Dependency-aware concurrent task scheduler with file-level conflict serialization."""

    def __init__(self, max_concurrency: int = 4):
        self.tasks: dict[str, TaskWorkstream] = {}
        self.active_files: set[str] = set()
        self.lock = asyncio.Lock()
        self.max_concurrency = max_concurrency
        self.execution_timeline: list[dict[str, Any]] = []

    def add_task(self, task: TaskWorkstream) -> None:
        """Register a workstream task."""
        self.tasks[task.task_id] = task

    def check_file_conflict(self, files: list[str]) -> bool:
        """Check if any of the target files are currently locked by an active task."""
        norm_files = {f.replace("\\", "/").lower() for f in files}
        return bool(norm_files & self.active_files)

    def _acquire_files(self, files: list[str]) -> None:
        norm_files = {f.replace("\\", "/").lower() for f in files}
        self.active_files.update(norm_files)

    def _release_files(self, files: list[str]) -> None:
        norm_files = {f.replace("\\", "/").lower() for f in files}
        self.active_files.difference_update(norm_files)

    def _record_event(self, event_type: str, task: TaskWorkstream, details: Optional[str] = None) -> None:
        self.execution_timeline.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_type,
            "task_id": task.task_id,
            "task_name": task.name,
            "workstream": task.workstream,
            "files": task.files_to_modify,
            "details": details,
        })

    async def execute_all(
        self, progress_callback: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None
    ) -> dict[str, Any]:
        """Execute all tasks using safe parallel dispatch with conflict serialization."""
        completed_tasks: set[str] = set()
        running_tasks: set[asyncio.Task] = set()
        task_id_to_async_task: dict[str, asyncio.Task] = {}
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _run_single(task: TaskWorkstream) -> None:
            async with semaphore:
                # Wait for file conflict to clear if another task is modifying the same file
                while True:
                    async with self.lock:
                        if not self.check_file_conflict(task.files_to_modify):
                            self._acquire_files(task.files_to_modify)
                            task.status = "running"
                            task.started_at = datetime.now(UTC).isoformat()
                            self._record_event("task_started", task)
                            break
                        else:
                            if task.status != "serialized_wait":
                                task.status = "serialized_wait"
                                self._record_event(
                                    "conflict_detected_serializing",
                                    task,
                                    f"Serialized execution: waiting for file conflict on {task.files_to_modify}",
                                )
                    await asyncio.sleep(0.05)

                if progress_callback:
                    await progress_callback(task.to_dict())

                try:
                    if task.execute_fn:
                        task.result = await task.execute_fn()
                    task.status = "completed"
                    task.completed_at = datetime.now(UTC).isoformat()
                    self._record_event("task_completed", task)
                except Exception as exc:
                    task.status = "failed"
                    task.error = str(exc)
                    task.completed_at = datetime.now(UTC).isoformat()
                    self._record_event("task_failed", task, str(exc))
                    logger.error("Task %s failed: %s", task.task_id, exc)
                finally:
                    async with self.lock:
                        self._release_files(task.files_to_modify)
                        completed_tasks.add(task.task_id)

                if progress_callback:
                    await progress_callback(task.to_dict())

        # Main orchestration loop
        while len(completed_tasks) < len(self.tasks):
            # Find tasks ready to run (dependencies satisfied and not already started)
            ready_tasks = [
                t for t in self.tasks.values()
                if t.status in ("pending", "serialized_wait")
                and t.task_id not in task_id_to_async_task
                and all(dep in completed_tasks for dep in t.dependencies)
            ]

            if not ready_tasks and not running_tasks:
                # Deadlock detection or unfulfilled dependencies
                unresolved = [
                    t.task_id for t in self.tasks.values() if t.task_id not in completed_tasks
                ]
                logger.warning("Unresolved tasks (cycle or missing dependency): %s", unresolved)
                for tid in unresolved:
                    self.tasks[tid].status = "skipped"
                    completed_tasks.add(tid)
                break

            for t in ready_tasks:
                fut = asyncio.create_task(_run_single(t))
                running_tasks.add(fut)
                task_id_to_async_task[t.task_id] = fut
                fut.add_done_callback(running_tasks.discard)

            await asyncio.sleep(0.05)

        # Ensure all running tasks finish
        if running_tasks:
            await asyncio.gather(*running_tasks, return_exceptions=True)

        return {
            "total_tasks": len(self.tasks),
            "completed": sum(1 for t in self.tasks.values() if t.status == "completed"),
            "failed": sum(1 for t in self.tasks.values() if t.status == "failed"),
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "timeline": self.execution_timeline,
        }
