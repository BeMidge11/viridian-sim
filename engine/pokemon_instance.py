# engine/pokemon_instance.py
# A live Pokémon in battle: computed stats, current HP, moveset.

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from data.moves import Move
from data.type_chart import VALID_TYPES
from data.xp import get_xp_for_level, get_level_for_xp


@dataclass
class PokemonInstance:
    name: str
    types: tuple[str, ...]      # 1 or 2 types (lowercase)
    level: int
    base_stats: dict[str, int]  # Keys: hp, atk, def, spatk, spdef, spe
    # Actual stat values (already computed, not base stats)
    hp_max: int
    atk: int
    def_: int
    spatk: int
    spdef: int
    spe: int
    moveset: list[Move]
    base_xp_yield: int = 120    # Base XP given when defeated
    level_up_moves: tuple[tuple[int, str], ...] = () # (level, move_slug)
    ability: str = "none"
    revealed_ability: str = "none" # Known to the AI? "none" means unknown/unrevealed.
    revealed_moves: list[Move] = field(default_factory=list) # Moves the opponent has seen this Mon use
    truant_turn: bool = False      # Tracks Truant flip-flop
    is_player: bool = False
    
    held_item: str = "none"
    inventory: dict[str, int] = field(default_factory=dict)

    # Damage Tracking for Counter/Mirror Coat
    last_damage_taken: int = 0
    last_damage_category: str = "none" # "physical", "special", or "none"

    # Mutable battle state
    hp: int = field(init=False)
    xp: int = field(init=False)
    
    # Status conditions
    status: str = "none"        # "burn", "poison", "paralysis", "freeze", "sleep", "none"
    sleep_turns: int = 0
    confused_turns: int = 0
    flinched: bool = False
    
    # Stat Stages (-6 to +6)
    stat_stages: dict[str, int] = field(init=False)
    # PP tracking: slot index -> current PP
    move_pp: list[int] = field(init=False)

    def __post_init__(self):
        self.hp = self.hp_max
        self.xp = get_xp_for_level(self.level)
        self.clear_stat_stages()
        self.move_pp = [m.pp_max for m in self.moveset]

    @property
    def is_fainted(self) -> bool:
        return self.hp <= 0
    
    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - amount)
        self._check_berry()

    def inflict_status(self, ailment: str, rng: random.Random) -> bool:
        """Attempt to inflict a status. Returns True if applied."""
        if ailment in ("none", ""): return False
        
        # --- Ability Immunity Checks ---
        if ailment == "poison" and self.ability == "immunity":
            self.revealed_ability = "immunity"
            return False
        if ailment == "paralysis" and self.ability == "limber":
            self.revealed_ability = "limber"
            return False
        if ailment == "burn" and self.ability == "water-veil":
            self.revealed_ability = "water-veil"
            return False
        if ailment == "sleep" and self.ability in ("insomnia", "vital-spirit"):
            self.revealed_ability = self.ability
            return False
        if ailment == "confusion" and self.ability == "own-tempo":
            self.revealed_ability = "own-tempo"
            return False
        if ailment == "infatuation" and self.ability == "oblivious":
            self.revealed_ability = "oblivious"
            return False
        
        # Volatile statuses
        if ailment == "confusion":
            if self.confused_turns == 0:
                # Gen 3 confusion lasts 2-5 turns
                self.confused_turns = rng.randint(2, 5)
                self._check_berry()
                return True
            return False
            
        # Non-volatile statuses (can only have one)
        if self.status != "none":
            return False
            
        if ailment in ("burn", "poison", "paralysis", "freeze", "sleep"):
            self.status = ailment
            if ailment == "sleep":
                # Gen 3 sleep lasts 2-5 turns (represented as 1-4 remaining after wake check)
                self.sleep_turns = rng.randint(2, 5)
            self._check_berry()
            return True
        return False

    def clear_volatile_status(self):
        """Clears statuses that go away when switching out (or end of battle)"""
        self.confused_turns = 0
        self.flinched = False

    def _check_berry(self):
        """Checks if the held berry's condition is met, and consumes it if so."""
        if self.held_item == "none": return
        if self.hp <= 0: return

        # Health Berries (<= 50% HP)
        if self.hp <= self.hp_max / 2.0:
            if self.held_item == "sitrus-berry":
                self.hp = min(self.hp_max, self.hp + 30)
                self.held_item = "none"
                return
            if self.held_item == "oran-berry":
                self.hp = min(self.hp_max, self.hp + 10)
                self.held_item = "none"
                return

        # Stat Berries (<= 25% HP)
        if self.hp <= self.hp_max / 4.0:
            if self.held_item == "liechi-berry" and self.apply_stat_change("attack", 1):
                self.held_item = "none"
                return
            if self.held_item == "ganlon-berry" and self.apply_stat_change("defense", 1):
                self.held_item = "none"
                return
            if self.held_item == "salac-berry" and self.apply_stat_change("speed", 1):
                self.held_item = "none"
                return
            if self.held_item == "petaya-berry" and self.apply_stat_change("special-attack", 1):
                self.held_item = "none"
                return
            if self.held_item == "apicot-berry" and self.apply_stat_change("special-defense", 1):
                self.held_item = "none"
                return

        # Status Berries
        if self.status != "none" or self.confused_turns > 0:
            if self.held_item == "lum-berry":
                self.status = "none"
                self.confused_turns = 0
                self.held_item = "none"
                return
            if self.held_item == "chesto-berry" and self.status == "sleep":
                self.status = "none"
                self.sleep_turns = 0
                self.held_item = "none"
                return
            if self.held_item == "pecha-berry" and self.status in ("poison", "bad-poison"):
                self.status = "none"
                self.held_item = "none"
                return
            if self.held_item == "rawst-berry" and self.status == "burn":
                self.status = "none"
                self.held_item = "none"
                return
            if self.held_item == "aspear-berry" and self.status == "freeze":
                self.status = "none"
                self.held_item = "none"
                return
            if self.held_item == "cheri-berry" and self.status == "paralysis":
                self.status = "none"
                self.held_item = "none"
                return
            if self.held_item == "persim-berry" and self.confused_turns > 0:
                self.confused_turns = 0
                self.held_item = "none"
                return

    def clear_stat_stages(self):
        self.stat_stages = {
            "attack": 0, "defense": 0, "special-attack": 0,
            "special-defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
        }

    def apply_stat_change(self, stat_name: str, amount: int) -> bool:
        """Apply a stat stage change, bounding between -6 and +6. Returns True if changed."""
        if stat_name not in self.stat_stages:
            return False
            
        # --- Ability checks for stat drops ---
        if amount < 0:
            if self.ability in ("clear-body", "white-smoke"):
                self.revealed_ability = self.ability
                return False
            if stat_name == "attack" and self.ability == "hyper-cutter":
                self.revealed_ability = "hyper-cutter"
                return False
            if stat_name == "accuracy" and self.ability == "keen-eye":
                self.revealed_ability = "keen-eye"
                return False
            
        current = self.stat_stages[stat_name]
        new_val = max(-6, min(6, current + amount))
        if new_val != current:
            self.stat_stages[stat_name] = new_val
            return True
        return False

    def full_heal(self) -> None:
        self.hp = self.hp_max
        self.status = "none"
        self.sleep_turns = 0
        self.clear_volatile_status()
        self.clear_stat_stages()
        # Restore PP to max
        self.move_pp = [m.pp_max for m in self.moveset]

    def gain_xp(self, amount: int, move_pool: list[Move] | None = None, rng: random.Random | None = None) -> bool:
        """Add XP and recompute stats if we level up. Returns True if leveled up."""
        old_level = self.level
        self.xp += amount
        new_level = get_level_for_xp(self.xp)
        if new_level > old_level:
            self.level = new_level
            # Recompute stats
            old_hp_max = self.hp_max
            self.hp_max = _gen3_hp(self.base_stats["hp"], self.level)
            self.atk = _gen3_stat(self.base_stats["atk"], self.level)
            self.def_ = _gen3_stat(self.base_stats["def"], self.level)
            self.spatk = _gen3_stat(self.base_stats["spatk"], self.level)
            self.spdef = _gen3_stat(self.base_stats["spdef"], self.level)
            self.spe = _gen3_stat(self.base_stats["spe"], self.level)
            # Heal by the amount of max HP gained
            self.hp += (self.hp_max - old_hp_max)
            
            if move_pool is not None:
                if self.is_player:
                    # Smart player replacement: roll a random move from the pool,
                    # replace weakest current move if the new one scores better.
                    _rng = rng if rng is not None else random
                    candidate = _rng.choice(move_pool)
                    
                    # Avoid duplicates
                    if not any(m.name == candidate.name for m in self.moveset):
                        from engine.ai import score_move_general
                        scores = [(score_move_general(m, self), i, m) for i, m in enumerate(self.moveset)]
                        worst_score, worst_idx, worst_move = min(scores, key=lambda x: x[0])
                        new_score = score_move_general(candidate, self)
                        
                        if new_score > worst_score:
                            self.moveset[worst_idx] = candidate
                            self.move_pp[worst_idx] = candidate.pp_max
                            print(f"  [player] Lv{self.level}: Replaced {worst_move.name} "
                                  f"({worst_score:.1f}) with {candidate.name} ({new_score:.1f})")
                else:
                    # AI opponents: learn level-up moves from their learnset
                    move_dict = {m.name: m for m in move_pool}
                    for lvl, slug in self.level_up_moves:
                        if old_level < lvl <= self.level:
                            if slug in move_dict:
                                new_move = move_dict[slug]
                                if any(m.name == new_move.name for m in self.moveset):
                                    continue
                                if len(self.moveset) < 4:
                                    self.moveset.append(new_move)
                                else:
                                    idx = random.randint(0, 3)
                                    self.moveset[idx] = new_move
            return True
        return False



# ---------------------------------------------------------------------------
# Stat computation helpers
# ---------------------------------------------------------------------------

PHYS_TYPES = frozenset({
    "normal","fighting","flying","poison","ground","rock","bug","ghost","steel"
})
SPEC_TYPES = frozenset({
    "fire","water","grass","electric","psychic","ice","dragon","dark"
})


def _gen3_stat(base: int, level: int, iv: int = 15, ev: int = 0,
               nature: float = 1.0) -> int:
    """Gen 3 non-HP stat formula."""
    inner = math.floor((2 * base + iv + ev // 4) * level / 100) + 5
    return math.floor(inner * nature)


def _gen3_hp(base: int, level: int, iv: int = 15, ev: int = 0) -> int:
    """Gen 3 HP stat formula."""
    return math.floor((2 * base + iv + ev // 4) * level / 100) + level + 10


def _distribute_bst(bst: int, rng: random.Random) -> dict[str, int]:
    """
    Randomly distribute a BST into 6 stats (hp, atk, def, spatk, spdef, spe).
    Each base stat is at least 1 and at most 255, summing to bst.
    Uses a random Dirichlet-like split: draw 6 random weights, scale to bst.
    """
    # Draw 6 uniform weights; ensure each stat gets at least 1
    weights = [rng.random() for _ in range(6)]
    total_w = sum(weights)
    # Scale to bst - 6 (reserve 1 per stat), then add 1 to each
    remainder = bst - 6
    raw = [max(0, min(249, int(w / total_w * remainder))) for w in weights]
    # Fix rounding so sum == bst - 6
    diff = (bst - 6) - sum(raw)
    for i in range(abs(diff)):
        raw[i % 6] += 1 if diff > 0 else -1
    bases = [v + 1 for v in raw]
    keys = ["hp", "atk", "def", "spatk", "spdef", "spe"]
    return dict(zip(keys, bases))


def estimate_base_stats(level: int, hp: int, atk: int, def_: int, spatk: int, spdef: int, spe: int, iv: int = 15) -> dict[str, int]:
    """
    Back-calculate base stats from observed actual stats at a given level.
    Assumes EVs=0 and Neutral Nature. Limits to [1, 255].
    """
    def _inv_hp(actual, lvl):
        # actual = floor((2*base + iv)*lvl/100) + lvl + 10
        # ((actual - lvl - 10) * 100 / lvl - iv) / 2 = base
        try:
            val = ((actual - lvl - 10) * 100 / lvl - iv) / 2
            return max(1, min(255, round(val)))
        except ZeroDivisionError:
            return 50

    def _inv_stat(actual, lvl):
        # actual = floor((2*base + iv)*lvl/100) + 5
        # ((actual - 5) * 100 / lvl - iv) / 2 = base
        try:
            val = ((actual - 5) * 100 / lvl - iv) / 2
            return max(1, min(255, round(val)))
        except ZeroDivisionError:
            return 50

    return {
        "hp": _inv_hp(hp, level),
        "atk": _inv_stat(atk, level),
        "def": _inv_stat(def_, level),
        "spatk": _inv_stat(spatk, level),
        "spdef": _inv_stat(spdef, level),
        "spe": _inv_stat(spe, level),
    }

def make_instance(
    name: str,
    types: tuple[str, ...],
    bst: int,
    level: int,
    moveset: list[Move],
    rng: random.Random,
    base_xp_yield: int = 120,
    bases: dict[str, int] | None = None,
    level_up_moves: tuple[tuple[int, str], ...] = (),
    ability: str = "none",
    held_item: str = "none",
    ai_knowledge: str = "unknown",
    is_player: bool = False,
) -> PokemonInstance:
    """Create a randomised PokemonInstance at the given level.
    Base stats are randomly distributed from bst; IVs=15, EVs=0, neutral nature.
    """
    if bases is None:
        bases = _distribute_bst(bst, rng)
        
    rev_kb = ai_knowledge
    if rev_kb == "unknown":
        rev_kb = "1-ability" if rng.random() < 0.5 else "2-abilities"
    revealed = ability if rev_kb == "1-ability" else "none"

    return PokemonInstance(
        name=name,
        types=types,
        level=level,
        base_stats=bases,
        hp_max=_gen3_hp(bases["hp"], level),
        atk=_gen3_stat(bases["atk"], level),
        def_=_gen3_stat(bases["def"], level),
        spatk=_gen3_stat(bases["spatk"], level),
        spdef=_gen3_stat(bases["spdef"], level),
        spe=_gen3_stat(bases["spe"], level),
        moveset=moveset,
        base_xp_yield=base_xp_yield,
        level_up_moves=level_up_moves,
        ability=ability,
        revealed_ability=revealed,
        is_player=is_player,
        held_item=held_item,
    )



def make_player_instance(
    name: str,
    types: tuple[str, ...],
    level: int,
    hp_max: int,
    atk: int,
    def_: int,
    spatk: int,
    spdef: int,
    spe: int,
    moveset: list[Move],
    rng: random.Random,
    level_up_moves: tuple[tuple[int, str], ...] = (),
    ability: str = "none",
    held_item: str = "none",
    inventory: dict[str, int] | None = None,
    ai_knowledge: str = "unknown",
    is_player: bool = True,
) -> PokemonInstance:
    """Create a player PokemonInstance with explicit stats (no randomization)."""
    bases = estimate_base_stats(level, hp_max, atk, def_, spatk, spdef, spe)
    
    rev_kb = ai_knowledge
    if rev_kb == "unknown":
        rev_kb = "1-ability" if rng.random() < 0.5 else "2-abilities"
    revealed = ability if rev_kb == "1-ability" else "none"

    return PokemonInstance(
        name=name,
        types=types,
        level=level,
        base_stats=bases,
        hp_max=hp_max,
        atk=atk,
        def_=def_,
        spatk=spatk,
        spdef=spdef,
        spe=spe,
        moveset=moveset,
        base_xp_yield=120,
        level_up_moves=level_up_moves,
        ability=ability,
        revealed_ability=revealed,
        is_player=is_player,
        held_item=held_item,
    )
    if inventory:
        p.inventory = inventory
    return p
