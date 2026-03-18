# sim/monte_carlo.py
# Runs N seeds and aggregates: overall win rate, per-trainer survival,
# 95% confidence interval via Wilson score interval.

from __future__ import annotations
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

from data.moves import load_move_pool
from data.pokemon import load_species_pool
from data.trainers import TRAINER_NAMES
from engine.pokemon_instance import PokemonInstance
from sim.run import run_seed, SeedResult


@dataclass
class SimResult:
    n_seeds: int
    win_rate: float           # 0.0 - 1.0
    ci_low: float             # Wilson 95% CI lower bound
    ci_high: float            # Wilson 95% CI upper bound
    # Fraction of seeds that reached AND cleared each trainer
    trainer_survival: dict[str, float]
    # Fraction of seeds lost at each trainer (given they were reached)
    trainer_loss_rate: dict[str, float]


def _wilson_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% confidence interval for a proportion."""
    if n == 0:
        return 0.0, 1.0
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _run_seed_worker(args):
    """Top-level function for multiprocessing (must be picklable)."""
    player_template, seed = args
    # Reload pools inside worker (cached per-process after first load)
    species_pool = load_species_pool()
    move_pool = load_move_pool()
    return run_seed(player_template, seed, species_pool=species_pool, move_pool=move_pool)


def run_simulation(
    player: PokemonInstance,
    n_seeds: int = 10_000,
    n_workers: int = 1,
    seed_offset: int = 0,
    progress_callback=None,
) -> SimResult:
    """
    Run Monte Carlo simulation over n_seeds.

    n_workers > 1 uses multiprocessing (faster for large n_seeds).
    seed_offset shifts the seed range (for reproducibility).
    progress_callback(completed, total) called every 500 seeds if provided.
    """
    results: list[SeedResult] = []

    args_iter = [(player, seed_offset + i) for i in range(n_seeds)]

    if n_workers > 1:
        with ProcessPoolExecutor(max_workers=n_workers) as exe:
            futures = {exe.submit(_run_seed_worker, a): a for a in args_iter}
            for i, fut in enumerate(as_completed(futures)):
                results.append(fut.result())
                if progress_callback and i % 500 == 0:
                    progress_callback(i + 1, n_seeds)
    else:
        # Single-process (avoids pickling overhead for small runs)
        species_pool = load_species_pool()
        move_pool = load_move_pool()
        for i, (player_t, seed) in enumerate(args_iter):
            results.append(run_seed(player_t, seed, species_pool=species_pool, move_pool=move_pool))
            if progress_callback and i % 500 == 0:
                progress_callback(i + 1, n_seeds)

    # Aggregate
    wins = sum(1 for r in results if r.won)
    win_rate = wins / n_seeds
    ci_low, ci_high = _wilson_ci(win_rate, n_seeds)

    # Per-trainer stats: cleared = won the trainer fight
    trainer_cleared: dict[str, int] = {t: 0 for t in TRAINER_NAMES}
    trainer_reached: dict[str, int] = {t: 0 for t in TRAINER_NAMES}

    for r in results:
        for i, tname in enumerate(TRAINER_NAMES):
            outcome = r.trainer_outcomes.get(tname)
            if outcome is not None:   # None = not reached
                trainer_reached[tname] += 1
            if outcome is True:
                trainer_cleared[tname] += 1

    trainer_survival = {
        t: (trainer_cleared[t] / n_seeds) for t in TRAINER_NAMES
    }
    trainer_loss_rate = {
        t: (
            (trainer_reached[t] - trainer_cleared[t]) / trainer_reached[t]
            if trainer_reached[t] > 0
            else 0.0
        )
        for t in TRAINER_NAMES
    }

    return SimResult(
        n_seeds=n_seeds,
        win_rate=win_rate,
        ci_low=ci_low,
        ci_high=ci_high,
        trainer_survival=trainer_survival,
        trainer_loss_rate=trainer_loss_rate,
    )
