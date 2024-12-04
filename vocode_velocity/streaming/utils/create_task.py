import asyncio
import functools

from loguru import logger

tasks_registry = []


def asyncio_create_task(
    *args,
    **kwargs,
) -> asyncio.Task:
    task = asyncio.create_task(*args, **kwargs)
    tasks_registry.append(task)
    task.add_done_callback(lambda t: tasks_registry.remove(t))
    return task
