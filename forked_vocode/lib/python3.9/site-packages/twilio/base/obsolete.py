import warnings
import functools


class ObsoleteException(Exception):
    """Base class for warnings about obsolete features."""


def obsolete_client(func):
    """This is a decorator which can be used to mark Client classes as
    obsolete. It will result in an error being emitted when the class is
    instantiated."""

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        raise ObsoleteException(
            "{} has been removed from this version of the library. "
            "Please refer to current documentation for guidance.".format(func.__name__)
        )

    return new_func


def deprecated_method(new_func=None):
    """
    This is a decorator which can be used to mark deprecated methods.
    It will report in a DeprecationWarning being emitted to stderr when the deprecated method is used.
    """

    def deprecated_method_wrapper(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = "Function method .{}() is deprecated".format(func.__name__)
            msg += (
                " in favor of .{}()".format(new_func)
                if isinstance(new_func, str)
                else ""
            )
            warnings.warn(msg, DeprecationWarning)
            return func(*args, **kwargs)

        return wrapper

    if callable(new_func):
        return deprecated_method_wrapper(new_func)

    return deprecated_method_wrapper
