"""
Operation method registry and resolution.

Operations are the building blocks of crawler pipelines. Each operation
is a function that takes a Context and data dict, performs some action,
and optionally emits data to subsequent stages.
"""

import re
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from anystore.functools import weakref_cache as cache

if TYPE_CHECKING:
    from memorious.logic.context import Context

# Type for operation functions
OperationFunc = Callable[["Context", dict[str, Any]], Any]

# Registry for operations
_REGISTRY: dict[str, OperationFunc] = {}

# Pattern to detect module:function syntax (vs file path)
_MODULE_RE = re.compile(r"^[\w\.]+:\w+$")


def register(name: str):
    """Decorator to register an operation.

    Raises ValueError if an operation with the same name already exists.

    Example:
        @register("my_operation")
        def my_operation(context: Context, data: dict) -> None:
            ...
    """

    def decorator(func: OperationFunc) -> OperationFunc:
        if name in _REGISTRY:
            raise ValueError(
                f"Operation '{name}' is already registered. "
                f"Use a different name or the module:function syntax."
            )
        _REGISTRY[name] = func
        return func

    return decorator


def _load_func(path: str, base_path: Path | None = None) -> OperationFunc:
    """Load a function from module:function or file:function syntax."""
    module_path, func_name = path.rsplit(":", 1)

    if _MODULE_RE.match(path):
        # Module syntax: mypackage.ops:my_func
        module = import_module(module_path)
    else:
        # File path syntax: ./src/ops.py:my_func
        file_path = Path(module_path)
        if base_path and not file_path.is_absolute():
            file_path = base_path / file_path
        file_path = file_path.resolve()
        spec = spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot load module from `{file_path}`")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

    return getattr(module, func_name)


@cache
def resolve_operation(
    method_name: str, base_path: Path | str | None = None
) -> OperationFunc:
    """
    Resolve an operation method by name.

    Resolution order:
    1. Local registry (built-in and decorated operations)
    2. Module import (module:function syntax, e.g., "mypackage.ops:my_func")
    3. File import (file:function syntax, e.g., "./src/ops.py:my_func")

    Args:
        method_name: Either a registered name (e.g., "fetch"),
                     a module path (e.g., "mypackage.ops:my_func"),
                     or a file path (e.g., "./src/ops.py:my_func")
        base_path: Base directory for resolving relative file paths.
                   Typically the directory containing the crawler config.

    Returns:
        The operation function.

    Raises:
        ValueError: If the operation cannot be resolved.
    """
    # Check local registry first
    if method_name in _REGISTRY:
        return _REGISTRY[method_name]

    # Import from module or file path
    if ":" in method_name:
        bp = Path(base_path) if base_path else None
        return _load_func(method_name, bp)

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
