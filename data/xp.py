# data/xp.py
# Gen 3 Experience mechanics.
# Simplified to assume Medium Fast growth rate for all Pokémon since IronMon randomized
# run sets base stats randomly, we standardize growth to Med Fast for simplicity.

import math

def get_xp_for_level(level: int) -> int:
    """Medium Fast experience curve (n^3)."""
    return level ** 3

def get_level_for_xp(xp: int) -> int:
    """Medium Fast inverse: level = floor(cbrt(xp)). Limit to 100 max."""
    return min(100, max(1, math.floor(math.pow(xp, 1/3))))

def calc_trainer_xp(base_xp: int, level: int) -> int:
    """
    Gen 3 Trainer Battle Experience Formula:
    XP = (a * t * b * e * L * p * f * v) / (7 * s)
    Simplified for IronMon (1v1, no lucky egg, traded=1, etc):
    a = 1.5 (trainer battle)
    b = base_experience of defeated pokemon
    L = level of defeated pokemon
    s = 1 (number of pokemon participating)
    e = 1 (no lucky egg)
    
    Formula used: floor((1.5 * b * L) / 7)
    """
    return math.floor((1.5 * base_xp * level) / 7)
