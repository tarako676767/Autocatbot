from __future__ import annotations
import enum
from typing import Any

from bcsfe import core, preset


class Rarity(enum.Enum):
    NORMAL = 0
    SPECIAL = 1
    RARE = 2
    SUPER_RARE = 3
    UBER_RARE = 4
    LEGEND_RARE = 5

    @staticmethod
    def parse(obj: str, log_fn: preset.LOG_FN) -> Rarity | None:
        obj = obj.lower()
        mp = {
            "normal": Rarity.NORMAL,
            "special": Rarity.SPECIAL,
            "rare": Rarity.RARE,
            "super_rare": Rarity.SUPER_RARE,
            "uber_rare": Rarity.UBER_RARE,
            "legend_rare": Rarity.LEGEND_RARE,
        }

        v = mp.get(obj)
        if v is None:
            preset.error(log_fn, f"no rarity with name: {obj}")
            return None

        return v


class CatSelector:
    def __init__(self, ids: list[int], rarities: list[Rarity], combine: preset.Combine):
        self.ids = ids
        self.rarities = rarities
        self.combine = combine

    def resolve(self, total_cats: int, unitbuy: core.UnitBuy) -> list[int] | None:
        ids: set[int] = set()

        ids.update(range(0, total_cats + 1))

        if self.ids:
            ids.intersection_update(self.ids)

        for rarity in self.rarities:
            cats = unitbuy.filter_rarity(rarity.value)
            if cats is None:
                return None

            ids.intersection_update(cats)

        return list(ids)

    @staticmethod
    def parse(obj: Any, log_fn: preset.LOG_FN) -> CatSelector | None:
        ids = preset.parse_field_default(
            obj, "ids", [], lambda v, l: preset.validate_ls(v, int, l), log_fn
        )
        if ids is None:
            return None

        combine = preset.parse_field_default(
            obj, "combine", "or", preset.Combine.parse, log_fn
        )

        if combine is None:
            return None

        rarities = preset.parse_field_default(
            obj,
            "rarities",
            [],
            lambda v, l: preset.parse_ls(v, Rarity.parse, l),
            log_fn,
        )
        if rarities is None:
            return None

        return CatSelector(ids, rarities, combine)


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

    def apply(self, save_file: core.SaveFile, cat: core.Cat, log_fn: preset.LOG_FN):
        if (
            not self.max_base
            and not self.max_plus
            and self.base is None
            and self.plus is None
        ):
            return
        upgrade = core.Upgrade(-1, -1)

        upgrade.base = (self.base or 0) - 1
        if self.plus is None:
            upgrade.plus = -1
        else:
            upgrade.plus = self.plus

        pw = core.PowerUpHelper(cat, save_file)
        if self.max_base:
            upgrade.base = pw.get_max_possible_base() - 1
        if self.max_plus:
            upgrade.plus = pw.get_max_possible_plus()

        if upgrade.base != -1:
            pw.reset_upgrade()
            preset.info(
                log_fn, f"upgrading base level to {upgrade.base+1}. Cat: {cat.id}"
            )
            pw.upgrade_by(upgrade.base)

        if upgrade.plus != -1:
            preset.info(
                log_fn, f"upgrading plus level to {upgrade.plus}. Cat: {cat.id}"
            )

        cat.set_upgrade(save_file, upgrade, only_plus=True)

    @staticmethod
    def parse(obj: Any, log_fn: preset.LOG_FN) -> CatUpgrade | None:
        max_base = preset.get_field_default(obj, "max_base", False, log_fn)
        if max_base is None:
            return None
        max_plus = preset.get_field_default(obj, "max_plus", False, log_fn)
        if max_plus is None:
            return None
        max = preset.get_field_default(obj, "max", False, log_fn)
        if max is None:
            return None
        base = preset.get_field_default(obj, "base", -1, log_fn)
        if base is None:
            return None
        plus = preset.get_field_default(obj, "plus", -1, log_fn)
        if plus is None:
            return None

        if max:
            max_base = max_plus = True

        if base == -1:
            base = None
        if plus == -1:
            plus = None

        return CatUpgrade(max_base, max_plus, base, plus)


class CatEdit:
    def __init__(self, unlock: bool, remove: bool, upgrade: CatUpgrade):
        self.unlock = unlock
        self.remove = remove
        self.upgrade = upgrade

    def apply(self, save_file: core.SaveFile, cat: core.Cat, log_fn: preset.LOG_FN):
        if self.unlock:
            preset.info(log_fn, f"unlocking cat: {cat.id}")
            cat.unlock(save_file)
        if self.remove:
            preset.info(log_fn, f"removing cat: {cat.id}")
            cat.remove(save_file=save_file)

        self.upgrade.apply(save_file, cat, log_fn)

    @staticmethod
    def parse(obj: Any, log_fn: preset.LOG_FN) -> CatEdit | None:
        unlock = preset.get_field_default(obj, "unlock", False, log_fn)
        if unlock is None:
            return None
        remove = preset.get_field_default(obj, "remove", False, log_fn)
        if remove is None:
            return None

        upgrade = preset.parse_field_default(
            obj, "upgrade", {}, CatUpgrade.parse, log_fn
        )
        if upgrade is None:
            return None
        return CatEdit(unlock, remove, upgrade)


class CatAction:
    def __init__(self, selectors: list[CatSelector], edit: CatEdit):
        self.selectors = selectors
        self.edit = edit

    def resolve_ids(
        self, total_cats: int, unitbuy: core.UnitBuy, log_fn: preset.LOG_FN
    ) -> list[int] | None:
        if not self.selectors:
            preset.warn(log_fn, "No selectors specified, no cats selected")
            return []

        first = self.selectors[0].resolve(total_cats, unitbuy)
        if first is None:
            return None

        first = set(first)

        for other in self.selectors[1:]:
            ids = other.resolve(total_cats, unitbuy)
            if ids is None:
                return None
            if other.combine == preset.Combine.OR:
                first.update(ids)
            elif other.combine == preset.Combine.AND:
                first.intersection_update(ids)

        if not first:
            preset.warn(log_fn, "No cats selected")

        return list(first)

    @staticmethod
    def parse(obj: dict[str, Any], log_fn: preset.LOG_FN) -> CatAction | None:
        selectors = preset.parse_field_default(
            obj,
            "selectors",
            [],
            lambda v, l: preset.parse_ls(v, CatSelector.parse, l),
            log_fn,
        )

        if selectors is None:
            return None

        edit = preset.parse_field(obj, "edit", CatEdit.parse, log_fn)

        if edit is None:
            return None

        return CatAction(selectors, edit)

    def apply(self, save_file: core.SaveFile, log_fn: preset.LOG_FN):
        ub = core.UnitBuy(save_file)
        ids = self.resolve_ids(len(save_file.cats.cats), ub, log_fn)
        if ids is None:
            return

        for id in ids:
            cat = save_file.cats.get_cat_by_id(id)
            if cat is None:
                preset.warn(log_fn, f"No cat with id: {id}. Skipping...")
                continue

            self.edit.apply(save_file, cat, log_fn)
