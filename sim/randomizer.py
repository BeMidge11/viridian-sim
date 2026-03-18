# sim/randomizer.py
# Per-seed random assignment of species and moves to trainer slots.

from __future__ import annotations
import random

from data.moves import Move, load_move_pool
from data.pokemon import Species, load_species_pool
from data.trainers import TrainerSlot
from engine.pokemon_instance import PokemonInstance, make_instance

# Number of moves per opponent Pokémon
MOVES_PER_MON = 4

VALID_ABILITIES = [
    "air-lock", "battle-armor", "blaze", "chlorophyll", "clear-body", "cloud-nine",
    "color-change", "compound-eyes", "cute-charm", "damp", "drizzle", "d drought",
    "early-bird", "effect-spore", "flame-body", "flash-fire", "forecast", "guts",
    "huge-power", "hustle", "hyper-cutter", "illuminate", "immunity", "inner-focus",
    "insomnia", "intimidate", "keen-eye", "levitate", "lightning-rod", "limber",
    "liquid-ooze", "magma-armor", "marvel-scale", "minus", "natural-cure", "oblivious",
    "overgrow", "own-tempo", "pickup", "plus", "poison-point", "pressure",
    "pure-power", "rain-dish", "rock-head", "rough-skin", "run-away", "sand-stream",
    "sand-veil", "serene-grace", "shed-skin", "shell-armor", "shield-dust", "soundproof",
    "speed-boost", "static", "stench", "sticky-hold", "sturdy", "suction-cups",
    "swarm", "swift-swim", "synchronize", "thick-fat", "torrent", "trace", "truant",
    "vital-spirit", "volt-absorb", "water-absorb", "water-veil", "white-smoke", "drought"
]

VALID_BERRIES = [
    "sitrus-berry", "oran-berry", "lum-berry", "chesto-berry", 
    "pecha-berry", "rawst-berry", "aspear-berry", "persim-berry", 
    "cheri-berry", "liechi-berry", "ganlon-berry", "salac-berry", 
    "petaya-berry", "apicot-berry"
]


def build_opponent(
    slot: TrainerSlot,
    rng: random.Random,
    species_pool: list[Species],
    move_pool: list[Move],
    identity_cache: dict[int, tuple[dict[str, int], list[Move], str, str, dict[int, Move]]] | None = None
) -> PokemonInstance:
    """
    For one trainer slot, randomly assign:
    - A species (from full Gen 1-3 pool)
    - 4 random damaging moves (without replacement)
    - Random BST stat distribution
    - Random Ability
    """
    sp: Species = rng.choice(species_pool)
    
    if identity_cache is not None and sp.dex in identity_cache:
        bases, base_moves, ability, held_item, level_up_rng_cache = identity_cache[sp.dex]
    else:
        # We must import _distribute_bst here to generate the base stats manually
        from engine.pokemon_instance import _distribute_bst
        bases = _distribute_bst(sp.bst, rng)
        base_moves = rng.sample(move_pool, k=min(MOVES_PER_MON, len(move_pool)))
        if len(base_moves) < MOVES_PER_MON:
            # This should only happen if move_pool is extremely small
            raise ValueError(f"Move pool too small to draw {MOVES_PER_MON} moves!")
        ability = rng.choice(VALID_ABILITIES)
        held_item = rng.choice(VALID_BERRIES)
        level_up_rng_cache = {}
        if identity_cache is not None:
            identity_cache[sp.dex] = (bases, base_moves, ability, held_item, level_up_rng_cache)

    moves = list(base_moves)
    for lvl, _slug in sp.level_up_moves:
        if lvl <= slot.level:
            if lvl not in level_up_rng_cache:
                level_up_rng_cache[lvl] = rng.choice(move_pool)
            new_move = level_up_rng_cache[lvl]
            if any(m.name == new_move.name for m in moves):
                continue
            if len(moves) >= 4:
                moves.pop(0)
            moves.append(new_move)

    instance = make_instance(
        name=sp.name,
        types=sp.types,
        bst=sp.bst,
        level=slot.level,
        moveset=list(moves),
        rng=rng,
        base_xp_yield=sp.base_xp,
        bases=bases,
        level_up_moves=sp.level_up_moves,
        ability=ability,
        held_item=held_item,
    )

    return instance


def build_all_opponents(
    slots: list[TrainerSlot],
    rng: random.Random,
    species_pool: list[Species],
    move_pool: list[Move],
) -> list[PokemonInstance]:
    """Build one randomised opponent for every trainer slot."""
    # Shedinja (#292) cannot appear in Viridian Forest
    EXCLUDED_DEX = {292}
    eligible = [s for s in species_pool if s.dex not in EXCLUDED_DEX]
    identity_cache: dict[int, tuple[dict[str, int], list[Move], str, str, dict[int, Move]]] = {}
    return [build_opponent(s, rng, eligible, move_pool, identity_cache) for s in slots]
