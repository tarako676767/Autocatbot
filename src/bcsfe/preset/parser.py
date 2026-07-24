from collections.abc import Callable
from typing import Any

from bcsfe.preset import (
    LOG_FN,
    Preset,
    PresetAction,
    error,
    get_field,
    get_field_default,
    warn,
)

from bcsfe import core, __version__

import json

from bcsfe.preset.cat import CatAction


def parse_json_file(path: core.Path, log_fn: LOG_FN) -> Preset | None:
    data = path.read().to_str()

    return parse_json_str(data, log_fn)


def parse_json_str(data: str, log_fn: LOG_FN) -> Preset | None:
    try:
        obj = json.loads(data)
    except json.JSONDecodeError as e:
        error(log_fn, f"{e}")
        return None

    schema = get_field(obj, "schema", str, log_fn)
    if schema is None:
        return None

    if schema != "1":
        error(log_fn, f"unsupported schema: {schema}")
        return None

    editor_version = get_field(obj, "editor_version", str, log_fn)
    if editor_version is None:
        return None

    if core.Updater.beta_version_check(editor_version, __version__):
        error(
            log_fn,
            f"unsupported editor version: preset version ({editor_version}) > current version ({__version__})",
        )
        return None

    actions_ls = get_field_default(obj, "actions", [], log_fn)
    if actions_ls is None:
        return None

    actions: list[PresetAction] = []

    mapping: dict[str, Callable[[Any, LOG_FN], Any]] = {"cat": CatAction.parse}

    for action_obj in actions_ls:
        action_typ = get_field(action_obj, "type", str, log_fn)
        if action_typ is None:
            return None

        action = None
        fn = mapping.get(action_typ)
        if fn is None:
            error(
                log_fn,
                f"unrecognised action type: {action_typ}. Expected values: {list(mapping.keys())}",
            )
            return None

        action = fn(action_obj, log_fn)

        if action is None:
            return None

        actions.append(PresetAction(action, action.apply))

    if not actions:
        warn(log_fn, "no actions specified")

    return Preset(schema, editor_version, actions)
