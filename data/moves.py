# data/moves.py
# Builds the full Gen 1-3 damaging move pool from PokeAPI move JSON cache.
# Filters: HMs excluded, must have power > 0, must exist in Gen 1-3.

from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache

# HMs to exclude (by slug)
HM_SLUGS = {
    "cut", "fly", "surf", "strength", "flash",
    "rock-smash", "waterfall", "dive",
}

# Generation name -> index
GEN_NAME_MAP = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3,
}

@dataclass(frozen=True)
class Move:
    name: str
    type: str
    power: int
    accuracy: int   # 0-100; 101 = never-miss (stored as 100 with never_miss=True)
    priority: int   # Gen 3 priorities: quick attack=1, mach punch=1, protect=3, roar=-6, etc.
    never_miss: bool
    variable_power: bool # True for Eruption, Water Spout, Flail, Reversal
    
    # Status / Secondary effects
    ailment: str          # e.g., "paralysis", "burn", "poison", "confusion", "none"
    ailment_chance: int   # 0-100% (0 usually means 100% if the move purely inflicts status)
    flinch_chance: int    # 0-100%
    
    # Stat changes (e.g. Swords Dance, Growl)
    target: str           # "user", "selected-pokemon", "all-opponents", etc.
    stat_changes: list[tuple[str, int]] # e.g. [("attack", -1)]
    
    # Recoil/Drain/Hits
    drain: int            # % of damage. Positive=Heal (Giga Drain), Negative=Recoil (Double-Edge)
    pp_max: int           # Max PP in Gen 3 (e.g. Flamethrower=15, Splash=40)
    min_hits: int = 1
    max_hits: int = 1


def _parse_move(j: dict) -> Move | None:
    """Parse a PokeAPI move JSON dict. Return None if the move should be excluded."""
    slug = j.get("name", "")

    # Exclude HMs
    if slug in HM_SLUGS:
        return None

    # Must be Gen 1-3
    gen_name = (j.get("generation") or {}).get("name", "")
    if GEN_NAME_MAP.get(gen_name, 99) > 3:
        return None

    # We must scan `past_values` to revert power/accuracy if they were changed in Gen 4+.
    past_values = j.get("past_values", [])
    past_power = None
    past_acc = None
    for pv in past_values:
        vg = (pv.get("version_group") or {}).get("name", "")
        if vg in {"diamond-pearl", "black-white", "x-y", "sun-moon", "sword-shield", "scarlet-violet"}:
            if pv.get("power") is not None and past_power is None:
                past_power = pv.get("power")
            if pv.get("accuracy") is not None and past_acc is None:
                past_acc = pv.get("accuracy")

    power_raw = past_power if past_power is not None else j.get("power")
    power_int = 0
    if isinstance(power_raw, (int, float)):
        power_int = int(power_raw)
    elif isinstance(power_raw, str) and power_raw.isdigit():
        power_int = int(power_raw)

    accuracy_raw = past_acc if past_acc is not None else j.get("accuracy")
    never_miss = not isinstance(accuracy_raw, (int, float, str))
    if never_miss:
        accuracy = 100
    else:
        try:
            accuracy = max(1, int(float(accuracy_raw)))
        except (ValueError, TypeError):
            accuracy = 100
            never_miss = True

    move_type_data = j.get("type")
    move_type = "normal"
    if isinstance(move_type_data, dict):
        move_type = str(move_type_data.get("name", "normal"))
    
    # Exclude Shadow moves
    if move_type == "shadow":
        return None

    priority = int(j.get("priority", 0))
    variable_power = slug in {"eruption", "water-spout", "flail", "reversal"}
    
    # Parse metadata for ailments
    meta = j.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        
    ailment_data = meta.get("ailment")
    ailment = ailment_data.get("name", "none") if isinstance(ailment_data, dict) else "none"
    
    val = meta.get("ailment_chance", 0)
    ailment_chance = int(val) if isinstance(val, (int, float, str)) and str(val).isdigit() else 0
    
    val2 = meta.get("flinch_chance", 0)
    flinch_chance = int(val2) if isinstance(val2, (int, float, str)) and str(val2).isdigit() else 0

    target_data = j.get("target")
    target = target_data.get("name", "selected-pokemon") if isinstance(target_data, dict) else "selected-pokemon"
    
    stat_changes_raw = j.get("stat_changes")
    if not isinstance(stat_changes_raw, list):
        stat_changes_raw = []
        
    stat_changes = []
    for sc in stat_changes_raw:
        if not isinstance(sc, dict):
            continue
        stat_data = sc.get("stat")
        stat_name = stat_data.get("name") if isinstance(stat_data, dict) else None
        
        c_raw = sc.get("change", 0)
        change = int(c_raw) if isinstance(c_raw, (int, float, str)) and str(c_raw).lstrip('-').isdigit() else 0
        
        if stat_name and change != 0:
            stat_changes.append((str(stat_name), change))

    drain_val = meta.get("drain", 0)
    drain = int(drain_val) if isinstance(drain_val, (int, float, str)) and str(drain_val).lstrip('-').isdigit() else 0

    # Parse PP (use past_values for Gen 3 value if available)
    past_pp = None
    for pv in past_values:
        vg = (pv.get("version_group") or {}).get("name", "")
        if vg in {"diamond-pearl", "black-white", "x-y", "sun-moon", "sword-shield", "scarlet-violet"}:
            if pv.get("pp") is not None and past_pp is None:
                past_pp = pv.get("pp")
    pp_raw = past_pp if past_pp is not None else j.get("pp")
    pp_max = int(pp_raw) if isinstance(pp_raw, (int, float)) and pp_raw > 0 else 5

    # Parse Hits
    min_hits = meta.get("min_hits")
    max_hits = meta.get("max_hits")
    min_hits_val = int(min_hits) if min_hits is not None else 1
    max_hits_val = int(max_hits) if max_hits is not None else 1
    
    # Double Kick / Twineedle are locked at 2
    if slug in ("double-kick", "twineedle", "bonemerang", "gear-grind"):
        min_hits_val = 2
        max_hits_val = 2
    # Triple Kick locked at 3 
    elif slug == "triple-kick":
        min_hits_val = 3
        max_hits_val = 3
    # Standard 2-5 multi-hits
    elif slug in ("bullet-seed", "icicle-spear", "rock-blast", "arm-thrust", "fury-swipes", "pin-missile", "fury-attack", "comet-punch", "spike-cannon", "barrage", "bone-rush", "doubleslap"):
        min_hits_val = 2
        max_hits_val = 5

    return Move(
        name=slug,
        type=move_type,
        power=power_int,
        accuracy=accuracy,
        priority=priority,
        never_miss=never_miss,
        variable_power=variable_power,
        ailment=ailment,
        ailment_chance=ailment_chance,
        flinch_chance=flinch_chance,
        target=target,
        stat_changes=stat_changes,
        drain=drain,
        pp_max=pp_max,
        min_hits=min_hits_val,
        max_hits=max_hits_val,
    )


@lru_cache(maxsize=4)
def load_move_pool(cache_dir: str = "") -> list[Move]:
    """Load all valid Gen 1-3 damaging moves from PokeAPI JSON cache.

    cache_dir: path string to the folder with move_*.json files.
               Pass empty string ("") to use the default (auto-detected).
    """
    if not cache_dir:
        # __file__ is data/moves.py, so .parent is data/, .parent.parent is project root
        base = pathlib.Path(__file__).parent.parent
        cache_path = base / "cache_moves"
    else:
        cache_path = pathlib.Path(cache_dir)

    if not cache_path.exists():
        raise FileNotFoundError(f"Move cache not found at {cache_path}")

    moves: list[Move] = []
    seen: set[str] = set()

    for fp in sorted(cache_path.glob("move_*.json")):
        try:
            with open(fp, encoding="utf-8") as f:
                j = json.load(f)
            if isinstance(j, dict) and "name" not in j:
                continue
            mv = _parse_move(j)
            if mv and mv.name not in seen:
                moves.append(mv)
                seen.add(mv.name)
        except Exception:
            continue

    if not moves:
        raise ValueError(
            f"No valid moves found in {cache_path}. "
            "Make sure the PokeAPI move JSON cache is present."
        )

    return moves
