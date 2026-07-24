from collections.abc import Callable
import enum
from typing import Any, TypeVar


from bcsfe import core


class Combine(enum.Enum):
    OR = 0
    AND = 1

    @staticmethod
    def parse(obj: str, log_fn: LOG_FN) -> Combine | None:
        obj = obj.lower()
        if obj == "or":
            return Combine.OR
        if obj == "and":
            return Combine.AND

        error(log_fn, f"expected `or` or `and`, not `{obj}`")
        return None


LOG_FN = Callable[[str, str], None]
APPLY_FN = Callable[[core.SaveFile, LOG_FN], None]

info: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("INFO", msg)
error: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("ERROR", msg)
warn: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("WARN", msg)


class PresetAction:
    def __init__(self, data: Any, apply_fn: APPLY_FN):
        self.data = data
        self.apply_fn = apply_fn

    def apply(self, save_file: core.SaveFile, log_fn: LOG_FN):
        self.apply_fn(save_file, log_fn)


class Preset:
    def __init__(self, schema: str, editor_version: str, actions: list[PresetAction]):
        self.schema = schema
        self.editor_version = editor_version
        self.actions = actions

    def apply(self, save_file: core.SaveFile, log_fn: LOG_FN):
        for action in self.actions:
            action.apply(save_file, log_fn)

    def __repr__(self) -> str:
        return repr(self)


def repr(obj: Any, depth: int = 0) -> str:
    tabs = "  " * (depth + 1)
    if obj is None:
        return str(obj)
    if isinstance(obj, str):
        return f'"{obj}"'
    if isinstance(obj, Callable):
        return "fn(...) -> ..."
    if isinstance(obj, bool):
        return str(obj)
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, enum.Enum):
        return f"{type(obj).__name__}.{obj.name}"
    if isinstance(obj, list):
        lines: list[str] = []
        for val in obj:  # type: ignore
            lines.append(tabs + repr(val, depth + 1))
        if not lines:
            return "[]"
        out = ",\n".join(lines)
        return "[\n" + out + f"\n{tabs}]"
    lines: list[str] = []

    for key, value in obj.__dict__.items():
        lines.append(f'{tabs}"{key}": {repr(value, depth+1)}')

    if not lines:
        return "{}"

    out = ",\n".join(lines)

    return "{\n" + out + "\n" + tabs + "}"


T = TypeVar("T")


def check_typ(val: Any, typ: type[T], log_fn: LOG_FN) -> T | None:
    if isinstance(val, typ):
        return val
    error(log_fn, f"expected type: `{typ}`, got {type(val)}")
    return None


def get_field(obj: Any, name: str, typ: type[T], log_fn: LOG_FN) -> T | None:
    obj = check_typ(obj, dict, log_fn)
    if obj is None:
        return None

    val = obj.get(name)
    if val is None:
        error(log_fn, f"expected field: `{name}`")
        return None

    return check_typ(val, typ, log_fn)


def get_field_default(obj: Any, name: str, default: T, log_fn: LOG_FN) -> T | None:
    obj = check_typ(obj, dict, log_fn)
    if obj is None:
        return None

    val = obj.get(name, default)
    if val is None:
        error(log_fn, f"expected field: `{name}`")
        return None

    return check_typ(val, type(default), log_fn)


def validate_ls(obj: Any, typ: type[T], log_fn: LOG_FN) -> list[T] | None:
    obj = check_typ(obj, list, log_fn)
    if obj is None:
        return None
    new: list[T] = []

    for item in obj:
        item = check_typ(item, typ, log_fn)
        if item is None:
            return None
        new.append(item)

    return new


def parse_field(
    obj: Any, name: str, parse_fn: Callable[[Any, LOG_FN], T | None], log_fn: LOG_FN
):
    obj = check_typ(obj, dict, log_fn)
    if obj is None:
        return None
    val = obj.get(name)
    if val is None:
        error(log_fn, f"expected field: `{name}`")
        return None

    return parse_fn(val, log_fn)


def parse_field_default(
    obj: Any,
    name: str,
    default: Any,
    parse_fn: Callable[[Any, LOG_FN], T | None],
    log_fn: LOG_FN,
):
    obj = check_typ(obj, dict, log_fn)
    if obj is None:
        return None
    val = obj.get(name, default)
    if val is None:
        error(log_fn, f"expected field: `{name}`")
        return None

    return parse_fn(val, log_fn)


def parse_ls(
    obj: Any, parse_fn: Callable[[Any, LOG_FN], T | None], log_fn: LOG_FN
) -> list[T] | None:
    obj = check_typ(obj, list, log_fn)
    if obj is None:
        return None
    new: list[T] = []

    for item in obj:
        item = parse_fn(item, log_fn)
        if item is None:
            return None
        new.append(item)

    return new


from bcsfe.preset import parser, presets, cat

__all__ = ["parser", "presets", "cat"]
