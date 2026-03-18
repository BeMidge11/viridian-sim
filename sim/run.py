# sim/run.py
# Runs a single seed: player vs all Viridian Forest trainers in order.
# Player gets a full heal between trainers (IronMon standard).

from __future__ import annotations
import copy
import random
from dataclasses import dataclass

from data.moves import Move, load_move_pool
from data.pokemon import load_species_pool
from data.trainers import VIRIDIAN_FOREST_TRAINERS, TRAINER_NAMES
from engine.battle import run_battle
from engine.pokemon_instance import PokemonInstance
from sim.randomizer import build_all_opponents


@dataclass
class SeedResult:
    won: bool
    # Name of trainer where the run ended (None if full clear)
    lost_to_trainer: str | None
    # Index into TRAINER_NAMES at which the run ended (None if won)
    lost_to_trainer_idx: int | None
    # Per-trainer outcome: True = cleared, False = lost, None = not reached
    trainer_outcomes: dict[str, bool | None]


def run_seed(
    player_template: PokemonInstance,
    seed: int,
    species_pool=None,
    move_pool=None,
) -> SeedResult:
    """
    Run one complete seed through Viridian Forest.

    player_template: A PokemonInstance with the player's stats and moves.
                     Will be deep-copied and healed between each trainer.
    seed: Integer RNG seed for this simulation run.
    """
    rng = random.Random(seed)

    if species_pool is None:
        species_pool = load_species_pool()
    if move_pool is None:
        move_pool = load_move_pool()

    # Randomise all opponents for this seed up-front
    opponents = build_all_opponents(
        VIRIDIAN_FOREST_TRAINERS, rng, species_pool, move_pool
    )

    # Map opponent list index -> trainer name
    slot_trainer = [s.trainer for s in VIRIDIAN_FOREST_TRAINERS]

    # Track per-trainer outcomes
    outcomes: dict[str, bool | None] = {name: None for name in TRAINER_NAMES}

    # One continuous run for this seed: player retains XP/levels, heals between trainers
    player = copy.deepcopy(player_template)

    opp_idx = 0
    for trainer_name in TRAINER_NAMES:
        # Full heal between trainers (IronMon standard)
        player.full_heal()

        # Find all opponent slots for this trainer
        trainer_opps = [
            opponents[i]
            for i, t in enumerate(slot_trainer)
            if t == trainer_name
        ]

        trainer_won = True
        for opp in trainer_opps:
            result = run_battle(player, opp, rng, move_pool=move_pool)
            if not result.player_won:
                trainer_won = False
                break
            # Carry HP through trainer's party (no heal between each mon)
            # player HP is already modified in-place by run_battle
            # but player_template is separate — player here is a copy

        outcomes[trainer_name] = trainer_won

        if not trainer_won:
            return SeedResult(
                won=False,
                lost_to_trainer=trainer_name,
                lost_to_trainer_idx=TRAINER_NAMES.index(trainer_name),
                trainer_outcomes=outcomes,
            )

    return SeedResult(
        won=True,
        lost_to_trainer=None,
        lost_to_trainer_idx=None,
        trainer_outcomes=outcomes,
    )
