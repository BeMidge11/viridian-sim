from engine.pokemon_instance import make_instance
from engine.damage import calc_damage
from data.moves import load_move_pool
import random

pool = {m.name: m for m in load_move_pool()}
def get_move(name): return pool[name]

rng = random.Random(42)
bases = {"hp":100, "atk":100, "def":100, "spatk":100, "spdef":100, "spe":100}

# Create a generic defender (100 Defense stat)
defender = make_instance(
    name="Defender", types=("normal",), level=50, bst=600,
    bases=bases, moveset=[get_move("tackle")], rng=rng
)

# Attacker with NO ability
attacker_normal = make_instance(
    name="AttackerNormal", types=("normal",), level=50, bst=600,
    bases=bases, moveset=[get_move("tackle")], rng=rng, ability="none"
)

# Attacker with HUGE POWER
attacker_huge = make_instance(
    name="AttackerHuge", types=("normal",), level=50, bst=600,
    bases=bases, moveset=[get_move("tackle")], rng=rng, ability="huge-power"
)

# Test physical damage (Tackle is 35 power physical)
dmg_normal = calc_damage(get_move("tackle"), attacker_normal, defender, rng)
rng.seed(42) # Reset seed for fair comparison
dmg_huge = calc_damage(get_move("tackle"), attacker_huge, defender, rng)

print(f"Normal Tackle Damage: {dmg_normal}")
print(f"Huge Power Tackle Damage: {dmg_huge}")
