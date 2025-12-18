"""
Operation method registry and resolution.

Operations are the building blocks of crawler pipelines. Each operation
is a function that takes a Context and data dict, performs some action,
and optionally emits data to subsequent stages.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from memorious.logic.context import Context

# Type for operation functions
OperationFunc = Callable[["Context", dict[str, Any]], Any]

# Registry for operations
_REGISTRY: dict[str, OperationFunc] = {}


def register(name: str):
    """Decorator to register an operation.

    Example:
        @register("my_operation")
        def my_operation(context: Context, data: dict) -> None:
            ...
    """

    def decorator(func: OperationFunc) -> OperationFunc:
        _REGISTRY[name] = func
        return func

    return decorator


def resolve_operation(method_name: str) -> OperationFunc:
    """
    Resolve an operation method by name.

    Resolution order:
    1. Local registry (built-in and decorated operations)
    2. Direct module import (module:function syntax)

    Args:
        method_name: Either a registered name (e.g., "fetch") or
                     a module path (e.g., "mypackage.ops:my_func")

    Returns:
        The operation function.

    Raises:
        ValueError: If the operation cannot be resolved.
    """
    # Check local registry first
    if method_name in _REGISTRY:
        return _REGISTRY[method_name]

    # Direct import with module:function syntax
    if ":" in method_name:
        package, function = method_name.rsplit(":", 1)
        module = import_module(package)
        return getattr(module, function)

    raise ValueError(f"Unknown operation: {method_name}")


def list_operations() -> list[str]:
    """Return a list of all registered operation names."""
    return sorted(_REGISTRY.keys())


# Import operations to trigger registration
# This must be at the bottom to avoid circular imports
from memorious.operations import (  # noqa: E402, F401
    aleph,
    clean,
    debug,
    documentcloud,
    extract,
    fetch,
    ftm,
    ftp,
    initializers,
    parse,
    regex,
    store,
    webdav,
)
