import asyncio
import functools

from loguru import logger

tasks_registry = []


def log_if_exception(reraise_cancelled: bool, future: asyncio.Future) -> None:
    try:
        if exc := future.exception():
            logger.exception(
                f"Vocode wrapped logger; exception raised by task {future}: {exc}",
                exc_info=exc,
            )
    except asyncio.CancelledError:
        if reraise_cancelled:
            raise


def asyncio_create_task_with_done_error_log(
    *args,
    reraise_cancelled: bool = False,
    **kwargs,
) -> asyncio.Task:
    task = asyncio.create_task(*args, **kwargs)
    tasks_registry.append(task)
    task.add_done_callback(functools.partial(log_if_exception, reraise_cancelled))
    task.add_done_callback(lambda t: tasks_registry.remove(t))
    return task
