from engine.pokemon_instance import make_player_instance, make_instance
from engine.damage import calc_damage, expected_damage
from data.moves import load_move_pool
import random

pool = {m.name: m for m in load_move_pool()}
def resolve(s): return pool.get(s)
rng = random.Random(42)

p_bases = {"hp":45, "atk":70, "def":55, "spatk":60, "spdef":50, "spe":80}

p = make_player_instance(
    name="Paras", types=("bug","grass"), level=10,
    hp_max=45, atk=70, def_=55, spatk=60, spdef=50, spe=80,
    moveset=[resolve("scratch")], rng=rng, ability="flash-fire", ai_knowledge="unknown"
)
e = make_instance(
    name="Charmander", types=("fire",), level=10, bst=300,
    bases=p_bases, moveset=[resolve("ember"), resolve("scratch")], rng=rng
)

print("Player Abil:", p.ability, "Rev Abil:", p.revealed_ability)

damage = calc_damage(resolve("ember"), e, p, rng)
print("Ember Damage (Actual):", damage)
print("Player Rev Abil after:", p.revealed_ability)
