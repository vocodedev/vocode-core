"""Decorator for creating a run tree from functions."""
import contextvars
import functools
import inspect
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional
from uuid import UUID

from langchainplus_sdk.run_trees import RunTree

logger = logging.getLogger(__name__)
_PARENT_RUN_TREE = contextvars.ContextVar[Optional[RunTree]](
    "_PARENT_RUN_TREE", default=None
)
_PROJECT_NAME = contextvars.ContextVar[Optional[str]]("_PROJECT_NAME", default=None)


def get_run_tree_context() -> Optional[RunTree]:
    """Get the current run tree context."""
    return _PARENT_RUN_TREE.get()


@functools.lru_cache(None)
def _warn_once() -> None:
    logger.warning(
        "The @traceable decorator is experimental and will likely see breaking changes."
    )


@functools.lru_cache(None)
def _warn_cm_once() -> None:
    logger.warning(
        "The @trace context manager is experimental and will"
        " likely see breaking changes."
    )


def _get_inputs(
    signature: inspect.Signature, *args: Any, **kwargs: Any
) -> Dict[str, Any]:
    """Return a dictionary of inputs from the function signature."""
    bound = signature.bind_partial(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def traceable(
    run_type: str,
    *,
    name: Optional[str] = None,
    extra: Optional[Dict] = None,
    executor: Optional[ThreadPoolExecutor] = None,
) -> Callable:
    """Decorator for creating or adding a run to a run tree."""
    _warn_once()
    extra_outer = extra or {}

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(
            *args: Any,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            run_tree: Optional[RunTree] = None,
            project_name: Optional[str] = None,
            **kwargs: Any,
        ) -> Any:
            """Async version of wrapper function"""
            if run_tree is None:
                parent_run_ = _PARENT_RUN_TREE.get()
            else:
                parent_run_ = run_tree
            outer_project = _PROJECT_NAME.get() or os.environ.get(
                "LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "default")
            )
            project_name_ = project_name or outer_project
            signature = inspect.signature(func)
            name_ = name or func.__name__
            docstring = func.__doc__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(signature, *args, **kwargs)
            if parent_run_ is not None:
                new_run = parent_run_.create_child(
                    name=name_,
                    run_type=str(run_type),
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    run_type=str(run_type),
                    reference_example_id=reference_example_id,
                    project_name=project_name_,
                    extra=extra_inner,
                    executor=executor,
                )
            new_run.post()
            _PROJECT_NAME.set(project_name_)
            _PARENT_RUN_TREE.set(new_run)
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = await func(*args, run_tree=new_run, **kwargs)
                else:
                    function_result = await func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                _PARENT_RUN_TREE.set(parent_run_)
                _PROJECT_NAME.set(outer_project)
                raise e
            _PARENT_RUN_TREE.set(parent_run_)
            _PROJECT_NAME.set(outer_project)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        @wraps(func)
        def wrapper(
            *args: Any,
            reference_example_id: Optional[UUID] = None,
            run_extra: Optional[Dict] = None,
            run_tree: Optional[RunTree] = None,
            project_name: Optional[str] = None,
            **kwargs: Any,
        ) -> Any:
            """Create a new run or create_child() if run is passed in kwargs."""
            if run_tree is None:
                parent_run_ = _PARENT_RUN_TREE.get()
            else:
                parent_run_ = run_tree
            outer_project = _PROJECT_NAME.get() or os.environ.get(
                "LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "default")
            )
            project_name_ = project_name or outer_project
            signature = inspect.signature(func)
            name_ = name or func.__name__
            docstring = func.__doc__
            if run_extra:
                extra_inner = {**extra_outer, **run_extra}
            else:
                extra_inner = extra_outer
            inputs = _get_inputs(signature, *args, **kwargs)
            if parent_run_ is not None:
                new_run = parent_run_.create_child(
                    name=name_,
                    run_type=run_type,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    extra=extra_inner,
                )
            else:
                new_run = RunTree(
                    name=name_,
                    serialized={
                        "name": name,
                        "signature": str(signature),
                        "doc": docstring,
                    },
                    inputs=inputs,
                    run_type=run_type,
                    reference_example_id=reference_example_id,
                    project_name=project_name_,
                    extra=extra_inner,
                    executor=executor,
                )
            new_run.post()
            _PARENT_RUN_TREE.set(new_run)
            _PROJECT_NAME.set(project_name_)
            func_accepts_parent_run = (
                inspect.signature(func).parameters.get("run_tree", None) is not None
            )
            try:
                if func_accepts_parent_run:
                    function_result = func(*args, run_tree=new_run, **kwargs)
                else:
                    function_result = func(*args, **kwargs)
            except Exception as e:
                new_run.end(error=str(e))
                new_run.patch()
                _PARENT_RUN_TREE.set(parent_run_)
                _PROJECT_NAME.set(outer_project)
                raise e
            _PARENT_RUN_TREE.set(parent_run_)
            _PROJECT_NAME.set(outer_project)
            new_run.end(outputs={"output": function_result})
            new_run.patch()
            return function_result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


@contextmanager
def trace(
    name: str,
    run_type: str,
    *,
    inputs: Optional[Dict] = None,
    extra: Optional[Dict] = None,
    executor: Optional[ThreadPoolExecutor] = None,
    project_name: Optional[str] = None,
    run_tree: Optional[RunTree] = None,
) -> Generator[RunTree, None, None]:
    """Context manager for creating a run tree."""
    _warn_cm_once()
    extra_outer = extra or {}
    parent_run_ = _PARENT_RUN_TREE.get() if run_tree is None else run_tree
    outer_project = _PROJECT_NAME.get()
    project_name_ = project_name or outer_project
    if parent_run_ is not None:
        new_run = parent_run_.create_child(
            name=name,
            run_type=str(run_type),
            extra=extra_outer,
            inputs=inputs,
        )
    else:
        new_run = RunTree(
            name=name,
            run_type=str(run_type),
            extra=extra_outer,
            executor=executor,
            project_name=project_name_,
            inputs=inputs or {},
        )
    new_run.post()
    _PARENT_RUN_TREE.set(new_run)
    _PROJECT_NAME.set(project_name_)
    try:
        yield new_run
    except Exception as e:
        new_run.end(error=str(e))
        new_run.patch()
        _PARENT_RUN_TREE.set(parent_run_)
        _PROJECT_NAME.set(outer_project)
        raise e
    _PARENT_RUN_TREE.set(parent_run_)
    _PROJECT_NAME.set(outer_project)
    if new_run.end_time is None:
        # User didn't call end() on the run, so we'll do it for them
        new_run.end()
    new_run.patch()
