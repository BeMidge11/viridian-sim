# data/type_chart.py
# Gen 3 type effectiveness table (17 types)
# CHART[attacking][defending] -> multiplier

TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice",
    "fighting", "poison", "ground", "flying", "psychic", "bug",
    "rock", "ghost", "dragon", "dark", "steel",
]
VALID_TYPES = frozenset(TYPES)

# Build flat 1.0 table then patch
CHART: dict[str, dict[str, float]] = {a: {d: 1.0 for d in TYPES} for a in TYPES}

def _s(att: str, defs: list[str], mult: float) -> None:
    for d in defs:
        CHART[att][d] = mult

# Normal
_s("normal",   ["rock", "steel"], 0.5)
_s("normal",   ["ghost"], 0.0)
# Fire
_s("fire",     ["grass", "ice", "bug", "steel"], 2.0)
_s("fire",     ["fire", "water", "rock", "dragon"], 0.5)
# Water
_s("water",    ["fire", "ground", "rock"], 2.0)
_s("water",    ["water", "grass", "dragon"], 0.5)
# Electric
_s("electric", ["water", "flying"], 2.0)
_s("electric", ["electric", "grass", "dragon"], 0.5)
_s("electric", ["ground"], 0.0)
# Grass
_s("grass",    ["water", "ground", "rock"], 2.0)
_s("grass",    ["fire", "grass", "poison", "flying", "bug", "dragon", "steel"], 0.5)
# Ice
_s("ice",      ["grass", "ground", "flying", "dragon"], 2.0)
_s("ice",      ["fire", "water", "ice", "steel"], 0.5)
# Fighting
_s("fighting", ["normal", "ice", "rock", "dark", "steel"], 2.0)
_s("fighting", ["poison", "flying", "psychic", "bug"], 0.5)
_s("fighting", ["ghost"], 0.0)
# Poison
_s("poison",   ["grass"], 2.0)
_s("poison",   ["poison", "ground", "rock", "ghost"], 0.5)
_s("poison",   ["steel"], 0.0)
# Ground
_s("ground",   ["fire", "electric", "poison", "rock", "steel"], 2.0)
_s("ground",   ["grass", "bug"], 0.5)
_s("ground",   ["flying"], 0.0)
# Flying
_s("flying",   ["grass", "fighting", "bug"], 2.0)
_s("flying",   ["electric", "rock", "steel"], 0.5)
# Psychic
_s("psychic",  ["fighting", "poison"], 2.0)
_s("psychic",  ["psychic", "steel"], 0.5)
_s("psychic",  ["dark"], 0.0)
# Bug
_s("bug",      ["grass", "psychic", "dark"], 2.0)
_s("bug",      ["fire", "fighting", "poison", "flying", "ghost", "steel"], 0.5)
# Rock
_s("rock",     ["fire", "ice", "flying", "bug"], 2.0)
_s("rock",     ["fighting", "ground", "steel"], 0.5)
# Ghost
_s("ghost",    ["psychic", "ghost"], 2.0)
_s("ghost",    ["dark"], 0.5)
_s("ghost",    ["normal"], 0.0)
# Dragon
_s("dragon",   ["dragon"], 2.0)
_s("dragon",   ["steel"], 0.5)
# Dark
_s("dark",     ["psychic", "ghost"], 2.0)
_s("dark",     ["fighting", "dark", "steel"], 0.5)
# Steel
_s("steel",    ["ice", "rock"], 2.0)
_s("steel",    ["fire", "water", "electric", "steel"], 0.5)


def type_effectiveness(att_type: str, def_types: list[str]) -> float:
    """Return combined multiplier for att_type attacking def_types (1 or 2 types)."""
    mult = 1.0
    for d in def_types:
        mult *= CHART.get(att_type, {}).get(d, 1.0)
    return mult
