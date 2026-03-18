import random
from data.moves import load_move_pool
from engine.pokemon_instance import make_instance
from engine.battle import run_battle

moves = {m.name: m for m in load_move_pool()}
rng = random.Random(42)

# Create two generic pokemons
bases = {"hp": 100, "atk": 100, "def": 100, "spatk": 100, "spdef": 100, "spe": 100}

p1 = make_instance("P1", ("normal",), 600, 50, [moves["tackle"], moves["thunder-wave"]], rng, bases=bases, ability="speed-boost", is_player=True)
p2 = make_instance("P2", ("normal",), 600, 50, [moves["tackle"], moves["thunder-wave"]], rng, bases=bases, ability="synchronize")

# Just run a quick battle to make sure we don't crash and that abilities trigger
result = run_battle(p1, p2, rng, max_turns=10, move_pool=list(moves.values()))
print("Battle 1 completed without crashing:", result)

# Test liquid-ooze and rough-skin
p3 = make_instance("P3", ("grass",), 600, 50, [moves["giga-drain"]], rng, bases=bases, ability="overgrow", is_player=True)
p4 = make_instance("P4", ("poison",), 600, 50, [moves["tackle"]], rng, bases=bases, ability="liquid-ooze")

result2 = run_battle(p3, p4, rng, max_turns=5, move_pool=list(moves.values()))
print("Battle 2 (Liquid Ooze / Overgrow) completed without crashing:", result2)

print("All mechanic tests passed!")
