import sys
import random
import math
from data.moves import load_move_pool
from data.pokemon import load_species_pool
from data.trainers import TrainerSlot
from engine.pokemon_instance import make_player_instance, PokemonInstance, SPEC_TYPES, PHYS_TYPES
from engine.ai import best_move, score_move
from engine.damage import calc_damage, _stat_multiplier
from sim.randomizer import build_opponent

def run():
    move_pool = load_move_pool()
    species_pool = load_species_pool()
    moves_dict = {m.name: m for m in move_pool}

    def get_moves(names):
        return [moves_dict[n] for n in names if n in moves_dict]

    def print_ai_eval(attacker, defender):
        print(f"  [AI Eval for {attacker.name} vs {defender.name} (is_player={attacker.is_player})]")
        for m in attacker.moveset:
            score = score_move(m, attacker, defender)
            print(f"    - {m.name} (power={m.power}, acc={m.accuracy}): score = {score:.1f}")

    def run_audit(p_inst, opp_inst, seed=42):
        rng = random.Random(seed)
        
        print(f"=== BATTLE START: Lv {p_inst.level} {p_inst.name} vs Lv {opp_inst.level} {opp_inst.name} ===")
        print(f"Player:   HP {p_inst.hp}/{p_inst.hp_max} | Spe {p_inst.spe} | Ability: {p_inst.ability}")
        print(f"Opponent: HP {opp_inst.hp}/{opp_inst.hp_max} | Spe {opp_inst.spe} | Ability: {opp_inst.ability}")
        print(f"Opponent Moves: {', '.join(m.name for m in opp_inst.moveset)}")
        print()

        for turn in range(1, 11):
            p_inst.last_damage_taken = 0
            p_inst.last_damage_category = "none"
            opp_inst.last_damage_taken = 0
            opp_inst.last_damage_category = "none"

            print(f"--- Turn {turn} ---")
            print_ai_eval(p_inst, opp_inst)
            p_move = best_move(p_inst, opp_inst)
            
            print_ai_eval(opp_inst, p_inst)
            o_move = best_move(opp_inst, p_inst)
            
            print(f"\nPlayer chose: {p_move.name} (Priority {p_move.priority})")
            print(f"Opponent chose: {o_move.name} (Priority {o_move.priority})")
            
            p_spe = math.floor(p_inst.spe * _stat_multiplier(p_inst.stat_stages["speed"]))
            o_spe = math.floor(opp_inst.spe * _stat_multiplier(opp_inst.stat_stages["speed"]))
            
            if p_move.priority > o_move.priority: player_first = True
            elif p_move.priority < o_move.priority: player_first = False
            else: player_first = p_spe >= o_spe
            
            print(f"Speeds (after stages) -> Player: {p_spe}, Opp: {o_spe}. Player goes first: {player_first}")

            def execute_attack(attacker: PokemonInstance, defender: PokemonInstance, move) -> bool:
                if move.name == "mirror-coat" or move.name == "counter":
                    is_special = (move.name == "mirror-coat")
                    target_cat = "special" if is_special else "physical"
                    
                    if attacker.last_damage_category == target_cat and attacker.last_damage_taken > 0:
                        dmg = attacker.last_damage_taken * 2
                        print(f"\n> {attacker.name} used {move.name}! Deals 2x {target_cat.title()} Damage ({dmg})")
                    else:
                        dmg = 0
                        print(f"\n> {attacker.name} used {move.name}! But it failed (No {target_cat} damage taken).")
                else:
                    dmg = calc_damage(move, attacker, defender, rng)
                    print(f"\n> {attacker.name} used {move.name}! Deals {dmg} damage.")
                
                defender.take_damage(dmg)
                
                if dmg > 0:
                    defender.last_damage_taken = dmg
                    defender.last_damage_category = "special" if move.type in SPEC_TYPES else "physical"
                
                if move.power == 0 or dmg > 0:
                    for stat_name, change in move.stat_changes:
                        target_mon = attacker if move.target == "user" else defender
                        old = target_mon.stat_stages.get(stat_name, 0)
                        target_mon.apply_stat_change(stat_name, change)
                        new = target_mon.stat_stages.get(stat_name, 0)
                        if old != new:
                            print(f"  {target_mon.name}'s {stat_name} changed from {old} to {new}.")
                
                print(f"  {defender.name} HP: {defender.hp}/{defender.hp_max}")
                if defender.is_fainted:
                    print(f"  {defender.name} fainted!")
                    return True
                return False

            if player_first:
                if execute_attack(p_inst, opp_inst, p_move): break
                if execute_attack(opp_inst, p_inst, o_move): break
            else:
                if execute_attack(opp_inst, p_inst, o_move): break
                if execute_attack(p_inst, opp_inst, p_move): break
                
            print("\n" + "="*50 + "\n")

    seed = random.randint(1, 10000)
    if len(sys.argv) > 1:
        seed = int(sys.argv[1])
    rng = random.Random(seed)
    print(f"--- Randomized Audit (Seed {seed}) ---")

    p = make_player_instance(
        "Kingler", ("water",), 9, 44, 10, 16, 29, 26, 9, 
        get_moves(["screech", "flame-wheel", "fire-blast", "mirror-coat"])
    )
    p.ability = "pressure"
    
    # Corrected Slot initialization
    slot = TrainerSlot("Wild", 0, 9)
    o = build_opponent(slot, rng, species_pool, move_pool)
    o.is_player = False
    
    run_audit(p, o, seed=seed)

if __name__ == "__main__":
    run()
