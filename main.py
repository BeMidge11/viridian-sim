# main.py  — Viridian Forest IronMon Simulator CLI
#
# Usage examples:
#
#   # Using explicit stats and move list
#   python main.py \
#       --name Arcanine --types fire --level 10 \
#       --hp 45 --atk 70 --def 55 --spatk 60 --spdef 50 --spe 80 \
#       --moves flamethrower bite quick-attack extremespeed \
#       --seeds 10000
#
#   # Using a JSON input file
#   python main.py --input player.json --seeds 5000
#
# player.json format:
# {
#   "name": "Arcanine", "types": ["fire"], "level": 10,
#   "hp": 45, "atk": 70, "def": 55, "spatk": 60, "spdef": 50, "spe": 80,
#   "moves": ["flamethrower", "bite", "quick-attack", "extremespeed"]
# }

from __future__ import annotations
import argparse
import json
import random
import sys
import time

from data.moves import load_move_pool, Move
from data.pokemon import load_species_pool
from data.trainers import TRAINER_NAMES
from engine.pokemon_instance import make_player_instance, _gen3_hp, _gen3_stat
from sim.monte_carlo import run_simulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_moves(move_names: list[str], pool: list[Move]) -> list[Move]:
    """Look up move objects by name slug; error on unknown moves."""
    pool_by_name = {m.name: m for m in pool}
    resolved: list[Move] = []
    for nm in move_names:
        slug = nm.lower().strip().replace(" ", "-").replace("_", "-")
        if slug not in pool_by_name:
            # Try partial match
            matches = [k for k in pool_by_name if slug in k]
            if len(matches) == 1:
                slug = matches[0]
                print(f"  [move] '{nm}' resolved to '{slug}'")
            else:
                print(f"  [warning] Move '{nm}' not found in pool. Skipping.")
                continue
        resolved.append(pool_by_name[slug])
    return resolved


def print_results(result, player_name: str) -> None:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"
    CYAN = "\033[96m"

    print()
    print(f"{BOLD}{'='*55}{RESET}")
    print(f"{BOLD}  Viridian Forest — {player_name}{RESET}")
    print(f"{'='*55}")
    pct = result.win_rate * 100
    color = GREEN if pct >= 60 else (CYAN if pct >= 35 else RED)
    print(f"\n  Overall win rate:  {color}{BOLD}{pct:.1f}%{RESET}")
    print(f"  95% CI:            [{result.ci_low*100:.1f}% – {result.ci_high*100:.1f}%]")
    print(f"  Seeds simulated:   {result.n_seeds:,}")
    print()
    print(f"  {'Trainer':<12} {'Survival':>10}  {'Loss rate (if reached)':>24}")
    print(f"  {'-'*50}")
    for t in TRAINER_NAMES:
        surv = result.trainer_survival[t] * 100
        loss = result.trainer_loss_rate[t] * 100
        bar_len = int(surv / 5)
        bar = "#" * bar_len + "." * (20 - bar_len)
        print(f"  {t:<12} {surv:>8.1f}%  {bar}  {loss:>6.1f}% loss")
    print(f"\n{'='*55}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Viridian Forest IronMon Simulator"
    )
    parser.add_argument("--input", "-i", help="Path to player JSON file")
    parser.add_argument("--name", default="Player", help="Pokémon name")
    parser.add_argument("--types", nargs="+", default=["normal"],
                        help="1 or 2 types (e.g. --types fire flying)")
    parser.add_argument("--level", type=int, default=10)
    parser.add_argument("--hp",    type=int, help="HP stat value")
    parser.add_argument("--atk",   type=int, help="Attack stat value")
    parser.add_argument("--def",   type=int, dest="def_", help="Defense stat value")
    parser.add_argument("--spatk", type=int, help="Sp. Atk stat value")
    parser.add_argument("--spdef", type=int, help="Sp. Def stat value")
    parser.add_argument("--spe",   type=int, help="Speed stat value")
    parser.add_argument("--moves", nargs="+", default=[],
                        help="Move slugs (e.g. flamethrower bite)")
    parser.add_argument("--seeds", type=int, default=10_000,
                        help="Number of Monte Carlo seeds (default 10000)")
    parser.add_argument("--ability", default="none",
                        help="Player Pokémon's ability (e.g. intimidate, static)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel worker count (default 1)")
    parser.add_argument("--cache-dir", default=None,
                        help="Override path to PokeAPI cache directory")
    args = parser.parse_args()

    # Load pools (shared)
    print("Loading move pool and species pool...")
    t0 = time.time()
    if args.cache_dir:
        move_pool = load_move_pool(args.cache_dir)
        species_pool = load_species_pool(args.cache_dir)
    else:
        move_pool = load_move_pool()
        species_pool = load_species_pool()
    print(f"  {len(move_pool)} moves, {len(species_pool)} species loaded ({time.time()-t0:.1f}s)")

    # Build player from JSON or CLI args
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            cfg = json.load(f)
        name = cfg.get("name", "Player")
        types = tuple(t.lower() for t in cfg.get("types", ["normal"]))
        level = int(cfg.get("level", 10))
        hp    = int(cfg["hp"])
        atk   = int(cfg["atk"])
        def_  = int(cfg["def"])
        spatk = int(cfg["spatk"])
        spdef = int(cfg["spdef"])
        spe   = int(cfg["spe"])
        ability = str(cfg.get("ability", "none")).lower()
        move_names = cfg.get("moves", [])
    else:
        name  = args.name
        types = tuple(t.lower() for t in args.types)
        level = args.level
        # Stats: if not provided, use level-scaled defaults (base 50 each)
        hp    = args.hp    or _gen3_hp(50, level)
        atk   = args.atk   or _gen3_stat(50, level)
        def_  = args.def_  or _gen3_stat(50, level)
        spatk = args.spatk or _gen3_stat(50, level)
        spdef = args.spdef or _gen3_stat(50, level)
        spe   = args.spe   or _gen3_stat(50, level)
        ability = args.ability.lower()
        move_names = args.moves

    if not move_names:
        print("[error] You must provide at least one move.")
        sys.exit(1)

    moves = resolve_moves(move_names, move_pool)
    if not moves:
        print("[error] No valid moves resolved. Check move names against the Gen 1-3 pool.")
        sys.exit(1)

    # Pad with random moves to reach EXACTLY 4 moves (as per Phase 10)
    if len(moves) < 4:
        needed = 4 - len(moves)
        if needed > 0:
            other_moves = [m for m in move_pool if m not in moves]
            padded = random.sample(other_moves, k=min(needed, len(other_moves)))
            for m in padded:
                print(f"  [player] Padded with random move: {m.name}")
            moves.extend(padded)

    player = make_player_instance(
        name=name, types=types, level=level,
        hp_max=args.hp, atk=args.atk, def_=args.def_,
        spatk=args.spatk, spdef=args.spdef, spe=args.spe,
        moveset=moves,
        rng=random.Random(),
        ability=ability,
    )

    print(f"\n--- Player Setup ({player.name}) ---")
    print(f"Types: {' / '.join(player.types)}")
    print(f"Moves: {', '.join(m.name for m in moves)}")
    bs = player.base_stats
    print(f"Estimated Base Stats: HP={bs['hp']} Atk={bs['atk']} Def={bs['def']} SpAtk={bs['spatk']} SpDef={bs['spdef']} Spe={bs['spe']}\n")

    def progress(done, total):
        pct = done / total * 100
        bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
        print(f"\r  [{bar}] {pct:.0f}%  ({done:,}/{total:,})", end="", flush=True)

    t1 = time.time()
    result = run_simulation(
        player=player,
        n_seeds=args.seeds,
        n_workers=args.workers,
        progress_callback=progress,
    )
    print(f"\n  Done in {time.time()-t1:.1f}s")

    print_results(result, name)


if __name__ == "__main__":
    main()
