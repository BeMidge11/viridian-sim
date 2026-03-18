# data/pokemon.py
# Loads Gen 1-3 species from PokeAPI pkmn_*.json cache.
# Stores: dex number, name, types, and BST.
# Individual stats are randomized per battle instance, not stored here.

from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from functools import lru_cache

GEN_NAME_MAP = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3,
}

VALID_TYPES = {
    "normal","fire","water","electric","grass","ice","fighting","poison",
    "ground","flying","psychic","bug","rock","ghost","dragon","dark","steel",
}

@dataclass(frozen=True)
class Species:
    dex: int
    name: str
    types: tuple[str, ...]  # 1 or 2 types
    bst: int                # Base Stat Total
    base_xp: int            # Base experience yield (for gaining XP on KO)
    level_up_moves: tuple[tuple[int, str], ...] = () # (level, move_slug)


def _parse_species(j: dict, dex: int) -> Species | None:
    """Parse a PokeAPI pokemon JSON. Return None if not Gen 1-3 or invalid."""
    # Check generation via species sub-object if present
    # pkmn_*.json is a pokemon object (not species); generation is in the species URL name
    # We filter by dex number: Gen 1 = 1-151, Gen 2 = 152-251, Gen 3 = 252-386
    if not (1 <= dex <= 386):
        return None

    name = j.get("name", f"pokemon-{dex}")

    # Extract types
    raw_types = []
    for slot in (j.get("types") or []):
        t = (slot.get("type") or {}).get("name", "")
        if t in VALID_TYPES:
            raw_types.append(t)
    if not raw_types:
        return None

    # Extract base stats
    stats: dict[str, int] = {}
    for entry in (j.get("stats") or []):
        sname = (entry.get("stat") or {}).get("name", "")
        base = entry.get("base_stat", 0)
        stats[sname] = int(base)

    bst = sum(stats.values())
    if bst <= 0:
        return None

    # Base experience for KO XP calculations
    base_xp = j.get("base_experience")
    if base_xp is None:
        base_xp = 120 # Fallback median value

    # Parse Gen 3 level-up moves
    level_up_moves_list = []
    for m in (j.get("moves") or []):
        move_name = (m.get("move") or {}).get("name")
        if not move_name: continue
        for v in (m.get("version_group_details") or []):
            vg_name = (v.get("version_group") or {}).get("name")
            if vg_name in {"ruby-sapphire", "emerald", "firered-leafgreen"}:
                method = (v.get("move_learn_method") or {}).get("name")
                if method == "level-up":
                    lvl = int(v.get("level_learned_at", 1))
                    level_up_moves_list.append((lvl, move_name))
                    break # Only need it once per Gen 3
    level_up_moves_list.sort()

    return Species(
        dex=dex,
        name=name,
        types=tuple(raw_types),
        bst=bst,
        base_xp=int(base_xp),
        level_up_moves=tuple(level_up_moves_list),
    )


@lru_cache(maxsize=4)
def load_species_pool(cache_dir: str = "") -> list[Species]:
    """Load all Gen 1-3 species from pkmn_*.json PokeAPI cache."""
    if not cache_dir:
        # pkmn_*.json live in the project root's cache folders
        base = pathlib.Path(__file__).parent.parent
        cache_path = base / "cache_pokemon"
        # Fallback to data/pokeapi_cache if needed
        if not cache_path.exists():
            cache_path = base / "data" / "pokeapi_cache"
    else:
        cache_path = pathlib.Path(cache_dir)

    if not cache_path.exists():
        raise FileNotFoundError(f"Pokémon cache not found at {cache_path}")

    species_list: list[Species] = []
    for dex in range(1, 387):
        fp = cache_path / f"pkmn_{dex}.json"
        if not fp.exists():
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                j = json.load(f)
            sp = _parse_species(j, dex)
            if sp:
                species_list.append(sp)
        except Exception:
            continue

    if not species_list:
        raise ValueError(
            f"No species found in {cache_path}. "
            "Ensure pkmn_1.json ... pkmn_386.json are present."
        )

    return species_list
