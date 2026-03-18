from engine.pokemon_instance import make_player_instance, make_instance
from engine.damage import calc_damage
from data.moves import load_move_pool
import random

pool = {m.name: m for m in load_move_pool()}
def get_move(name): return pool[name]

rng = random.Random(42)
bases = {"hp":100, "atk":100, "def":100, "spatk":100, "spdef":100, "spe":100}

tests = [
    ("flash-fire", "fire", get_move("ember")),
    ("levitate", "ground", get_move("earthquake")),
    ("volt-absorb", "electric", get_move("thunderbolt")),
    ("lightning-rod", "electric", get_move("thunderbolt")),
    ("water-absorb", "water", get_move("water-gun")),
    ("dry-skin", "water", get_move("water-gun")),
    ("soundproof", "normal", get_move("hyper-voice")),
    ("damp", "normal", get_move("self-destruct")),
]

print(f"{'Ability':<15} | {'Move':<15} | {'Damage':<8} | {'Revealed':<10}")
print("-" * 55)

for ability, def_type, move in tests:
    defender = make_player_instance(
        name="TestDummy", types=(def_type,), level=50,
        hp_max=150, atk=100, def_=100, spatk=100, spdef=100, spe=100,
        moveset=[get_move("tackle")], rng=rng, ability=ability, ai_knowledge="unknown"
    )
    
    attacker = make_instance(
        name="Attacker", types=(move.type,), level=50, bst=300,
        bases=bases, moveset=[move], rng=rng
    )
    
    dmg = calc_damage(move, attacker, defender, rng)
    print(f"{ability:<15} | {move.name:<15} | {dmg:<8} | {defender.revealed_ability:<10}")

# Test Wonder Guard separately
wg_def = make_player_instance(
    name="Shedinja", types=("bug", "ghost"), level=50,
    hp_max=1, atk=100, def_=100, spatk=100, spdef=100, spe=100,
    moveset=[get_move("tackle")], rng=rng, ability="wonder-guard", ai_knowledge="unknown"
)

attacker = make_instance("Attacker", ("fire",), 50, 300, bases=bases, moveset=[get_move("ember"), get_move("water-gun")], rng=rng)

# Ember is Super Effective
dmg1 = calc_damage(get_move("ember"), attacker, wg_def, rng)
# Water Gun is normal effective
dmg2 = calc_damage(get_move("water-gun"), attacker, wg_def, rng)

print(f"\nwonder-guard    | SE ember       | {dmg1:<8} | {wg_def.revealed_ability:<10}")
print(f"wonder-guard    | Neutral surf | {dmg2:<8} | {wg_def.revealed_ability:<10}")
