from __future__ import annotations

from collections.abc import Callable
import enum
from typing import TypeVar, Generic

from bcsfe import core

T = TypeVar("T")


class Combine(enum.Enum):
    OR = 0
    AND = 1


class CatSelector:
    def __init__(self, ids: list[int], combine: Combine):
        self.ids = ids
        self.combine = combine

    def resolve(self, total_cats: int) -> list[int]:
        ids: set[int] = set()

        ids.update(range(0, total_cats + 1))

        ids.intersection_update(self.ids)

        return list(ids)


class CatUpgrade:
    def __init__(
        self,
        max_base: bool,
        max_plus: bool,
        base: int | None,
        plus: int | None,
    ):
        self.max_base = max_base
        self.max_plus = max_plus
        self.base = base
        self.plus = plus

    def apply(self, save_file: core.SaveFile, cat: core.Cat, log_fn: LOG_FN):
        upgrade = core.Upgrade(-1, -1)
        if self.max_base:
            upgrade.base = (
                core.PowerUpHelper(cat, save_file).get_max_possible_base() - 1
            )
        if self.max_plus:
            upgrade.base = (
                core.PowerUpHelper(cat, save_file).get_max_possible_plus() - 1
            )

        upgrade.base = (self.base or 0) - 1
        upgrade.plus = (self.plus or 0) - 1

        cat.set_upgrade(save_file, upgrade)


class CatEdit:
    def __init__(self, unlock: bool, remove: bool, upgrade: CatUpgrade):
        self.unlock = unlock
        self.remove = remove
        self.upgrade = upgrade

    def apply(self, save_file: core.SaveFile, cat: core.Cat, log_fn: LOG_FN):
        if self.unlock:
            cat.unlock(save_file)
        if self.remove:
            cat.remove(save_file=save_file)

        self.upgrade.apply(save_file, cat, log_fn)


LOG_FN = Callable[[str, str], None]

info: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("INFO", msg)
error: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("ERROR", msg)
warn: Callable[[LOG_FN, str], None] = lambda fn, msg: fn("WARN", msg)


class CatAction:
    def __init__(self, selectors: list[CatSelector], edit: CatEdit):
        self.selectors = selectors
        self.edit = edit

    def resolve_ids(self, total_cats: int, log_fn: LOG_FN) -> list[int]:
        if not self.selectors:
            warn(log_fn, "No selectors specified, no cats selected")
            return []

        first = set(self.selectors[0].resolve(total_cats))

        for other in self.selectors[1:]:
            ids = other.resolve(total_cats)
            if other.combine == Combine.OR:
                first.update(ids)
            elif other.combine == Combine.AND:
                first.intersection_update(ids)

        if not first:
            warn(log_fn, "No cats selected")

        return list(first)

    def apply(self, save_file: core.SaveFile, log_fn: LOG_FN):
        ids = self.resolve_ids(len(save_file.cats.cats), log_fn)

        for id in ids:
            cat = save_file.cats.get_cat_by_id(id)
            if cat is None:
                warn(log_fn, f"No cat with id: {id}. Skipping...")
                continue

            self.edit.apply(save_file, log_fn)


class PresetAction(enum.Enum):
    CAT: CatAction


class Preset:
    def __init__(self, schema: str, editor_version: str, actions: list[PresetAction]):
        self.schema = schema
        self.editor_version = editor_version
        self.actions = actions

    def apply(self, save_file: core.SaveFile):
        for action in self.actions:
            action.value.apply(save_file)
