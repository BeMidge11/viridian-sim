# engine/battle.py
# 1v1 turn-based battle loop implementing Gen 3 speed-priority turn order.

from __future__ import annotations
import math
import random
from dataclasses import dataclass

from engine.ai import best_action
from engine.damage import calc_damage, _stat_multiplier
from engine.pokemon_instance import PokemonInstance, PHYS_TYPES, SPEC_TYPES
from data.moves import Move
from data.xp import calc_trainer_xp


# Struggle: used when all PP is exhausted. Typeless, 50 power, 25% recoil.
_STRUGGLE = Move(
    name="struggle", type="normal", power=50, accuracy=100, priority=0,
    never_miss=True, variable_power=False, ailment="none", ailment_chance=0,
    flinch_chance=0, target="selected-pokemon", stat_changes=[], drain=-25,
    pp_max=999,
)


def _pick_action(attacker: PokemonInstance, defender: PokemonInstance, weather: WeatherState) -> tuple[str, Move | str]:
    """Pick best action (MOVE or ITEM). Falls back to Struggle if all exhausted."""
    available = [
        m for i, m in enumerate(attacker.moveset)
        if attacker.move_pp[i] > 0
    ]
    if not available:
        return ("MOVE", _STRUGGLE)
    return best_action(attacker, defender, available_moves=available, weather_condition=weather.condition)


@dataclass
class BattleResult:
    player_won: bool
    turns: int
    leveled_up: bool


@dataclass
class WeatherState:
    condition: str = "none" # "none", "rain", "sun", "sandstorm", "hail"
    turns_remaining: int = 0
    
    def apply_weather(self, move_name: str, ability_name: str) -> None:
        """Apply weather from a move or ability."""
        if ability_name == "drizzle":
            self.condition = "rain"
            self.turns_remaining = 999
        elif ability_name == "drought":
            self.condition = "sun"
            self.turns_remaining = 999
        elif ability_name == "sand-stream":
            self.condition = "sandstorm"
            self.turns_remaining = 999
        elif move_name == "rain-dance":
            self.condition = "rain"
            self.turns_remaining = 5
        elif move_name == "sunny-day":
            self.condition = "sun"
            self.turns_remaining = 5
        elif move_name == "sandstorm":
            self.condition = "sandstorm"
            self.turns_remaining = 5
        elif move_name == "hail":
            self.condition = "hail"
            self.turns_remaining = 5

    def decrement(self, log_messages: list[str]) -> None:
        if self.condition != "none":
            self.turns_remaining -= 1
            if self.turns_remaining <= 0:
                self.condition = "none"


def _can_attack(pokemon: PokemonInstance, rng: random.Random) -> bool:
    """Check if pokemon can attack this turn. Handles Sleep, Freeze, Paralysis, Confusion, Truant."""
    if pokemon.ability == "truant":
        if pokemon.truant_turn:
            print(f"{pokemon.name} is loafing around!")
            pokemon.truant_turn = False
            return False
        else:
            pokemon.truant_turn = True

    if pokemon.status == "sleep":
        pokemon.sleep_turns -= 1
        if pokemon.ability == "early-bird":
            pokemon.sleep_turns -= 1
            
        if pokemon.sleep_turns <= 0:
            pokemon.status = "none"
            return True # Woke up and attacks (Gen 3 mechanics: wake up takes a turn, but we'll simplify to just attacking for now)
        return False
        
    if pokemon.status == "freeze":
        if rng.random() < 0.20: # 20% chance to thaw
            pokemon.status = "none"
            return True
        return False
        
    if pokemon.status == "paralysis":
        if rng.random() < 0.25: # 25% chance of full paralysis
            return False
            
    if pokemon.confused_turns > 0:
        pokemon.confused_turns -= 1
        if pokemon.confused_turns == 0:
            return True # Snapped out of confusion
        if rng.random() < 0.50: # 50% chance to hurt itself
            # Confusion damage: 40 power typeless physical attack against self
            damage = math.floor(math.floor((math.floor(2 * pokemon.level / 5 + 2) * 40 * pokemon.atk / pokemon.def_) / 50) + 2)
            # Apply random roll (0.85-1.0)
            damage = max(1, math.floor(damage * rng.uniform(0.85, 1.0)))
            pokemon.take_damage(damage)
            return False
            
    return True

def _apply_end_of_turn(pokemon: PokemonInstance, weather: WeatherState) -> None:
    """Apply burn/poison damage. Apply speed boost. Apply Weather chip damage."""
    if pokemon.status in ("burn", "poison", "bad-poison"): # bad-poison simplified to normal poison for now
        damage = max(1, pokemon.hp_max // 8)
        pokemon.take_damage(damage)
        
    if pokemon.ability == "speed-boost":
        pokemon.apply_stat_change("speed", 1)
        
    # Weather Chip Damage (1/16 Max HP)
    if weather.condition == "sandstorm" and not any(t in ("rock", "ground", "steel") for t in pokemon.types):
        if pokemon.ability not in ("sand-veil",):
            pokemon.take_damage(max(1, pokemon.hp_max // 16))
            
    if weather.condition == "hail" and not any(t in ("ice",) for t in pokemon.types):
        pokemon.take_damage(max(1, pokemon.hp_max // 16))
        
    # Rain Dish
    if weather.condition == "rain" and pokemon.ability == "rain-dish":
        pokemon.hp = min(pokemon.hp_max, pokemon.hp + max(1, pokemon.hp_max // 16))

def _apply_status_effect(attacker: PokemonInstance, defender: PokemonInstance, move: Move, rng: random.Random):
    """Apply move secondary ailments."""
    if move.ailment != "none" and move.ailment_chance > 0:
        if rng.random() < (move.ailment_chance / 100.0):
            if defender.inflict_status(move.ailment, rng):
                if defender.ability == "synchronize" and move.ailment in ("burn", "poison", "paralysis"):
                    attacker.inflict_status(move.ailment, rng)


def run_battle(
    player: PokemonInstance,
    opponent: PokemonInstance,
    rng: random.Random,
    max_turns: int = 200,
    move_pool: list[Move] | None = None
) -> BattleResult:
    """
    Simulate a single 1v1 battle between player and opponent.
    Both pick their best move each turn (greedy / optimal play).
    Faster Pokémon attacks first; ties go to player.

    Returns BattleResult(player_won, turns_taken).
    """
    leveled_up = False
    
    weather = WeatherState()

    # Intimidate
    if player.ability == "intimidate":
        opponent.apply_stat_change("attack", -1)
    if opponent.ability == "intimidate":
        player.apply_stat_change("attack", -1)
        
    # Passive Weather Setup
    weather.apply_weather("none", player.ability)
    weather.apply_weather("none", opponent.ability)

    for turn in range(1, max_turns + 1):
        # Reset turn-based tracking
        player.last_damage_taken = 0
        player.last_damage_category = "none"
        opponent.last_damage_taken = 0
        opponent.last_damage_category = "none"
        # Determine moves
        p_act = _pick_action(player, opponent, weather)
        o_act = _pick_action(opponent, player, weather)
        
        p_pri = 6 if p_act[0] == "ITEM" else p_act[1].priority
        o_pri = 6 if o_act[0] == "ITEM" else o_act[1].priority

        # Effective Speed (Paralysis quarters speed, apply stat stages)
        p_spe = math.floor(player.spe * _stat_multiplier(player.stat_stages["speed"]))
        p_spe = p_spe // 4 if player.status == "paralysis" else p_spe
        
        o_spe = math.floor(opponent.spe * _stat_multiplier(opponent.stat_stages["speed"]))
        o_spe = o_spe // 4 if opponent.status == "paralysis" else o_spe

        # Speed / Priority order
        if p_pri > o_pri:
            player_first = True
        elif p_pri < o_pri:
            player_first = False
        else:
            player_first = p_spe >= o_spe

        def execute_action(attacker: PokemonInstance, defender: PokemonInstance, action: tuple[str, Move | str]) -> bool:
            """Execute an action, return True if battle should end (someone fainted)."""
            if action[0] == "ITEM":
                item_name = action[1]
                attacker.inventory[item_name] -= 1
                if item_name == "potion": attacker.hp = min(attacker.hp_max, attacker.hp + 20)
                elif item_name == "super-potion": attacker.hp = min(attacker.hp_max, attacker.hp + 50)
                elif item_name == "hyper-potion": attacker.hp = min(attacker.hp_max, attacker.hp + 200)
                elif item_name == "max-potion": attacker.hp = attacker.hp_max
                elif item_name == "full-restore":
                    attacker.hp = attacker.hp_max
                    attacker.status = "none"
                    attacker.confused_turns = 0
                elif item_name == "full-heal":
                    attacker.status = "none"
                    attacker.confused_turns = 0
                elif item_name == "antidote" and attacker.status in ("poison", "bad-poison"):
                    attacker.status = "none"
                elif item_name == "paralyze-heal" and attacker.status == "paralysis":
                    attacker.status = "none"
                elif item_name == "awakening" and attacker.status == "sleep":
                    attacker.status = "none"
                    attacker.sleep_turns = 0
                elif item_name == "burn-heal" and attacker.status == "burn":
                    attacker.status = "none"
                elif item_name == "ice-heal" and attacker.status == "freeze":
                    attacker.status = "none"
                return False

            move = action[1]
            if _can_attack(attacker, rng):
                # Decrement PP for the move used (not Struggle)
                if move is not _STRUGGLE:
                    for i, m in enumerate(attacker.moveset):
                        if m.name == move.name:
                            attacker.move_pp[i] = max(0, attacker.move_pp[i] - 1)
                            break
                if move not in attacker.revealed_moves:
                    attacker.revealed_moves.append(move)
                
                # Roll number of hits
                num_hits = 1
                if move.max_hits > 1:
                    if move.min_hits == move.max_hits:
                        num_hits = move.max_hits
                    else:
                        # 2-5 hits (37.5%, 37.5%, 12.5%, 12.5%)
                        roll_hit = rng.random()
                        if roll_hit < 0.375:
                            num_hits = 2
                        elif roll_hit < 0.75:
                            num_hits = 3
                        elif roll_hit < 0.875:
                            num_hits = 4
                        else:
                            num_hits = 5
                            
                hits_landed = 0
                for _hit_idx in range(num_hits):
                    # If target is dead, stop hitting
                    if defender.hp <= 0 or attacker.hp <= 0:
                        break
                        
                    hits_landed += 1
                    
                    if move.name == "mirror-coat":
                        if attacker.last_damage_category == "special" and attacker.last_damage_taken > 0:
                            dmg = attacker.last_damage_taken * 2
                        else:
                            dmg = 0
                    else:
                        dmg = calc_damage(move, attacker, defender, rng, weather.condition)
                    
                    defender.take_damage(dmg)
                    
                    # Store damage for Counter/Mirror Coat
                    if dmg > 0:
                        defender.last_damage_taken = dmg
                        defender.last_damage_category = "special" if move.type in SPEC_TYPES else "physical"
                    
                    # (Miss check heuristic: if base power > 0 and dmg == 0 and type effectiveness > 0, we can assume it missed/failed.
                    #  For simplicity, we'll apply stat changes if the move is 0 power, or if dmg > 0)
                    hit_target = (move.power == 0) or (dmg > 0)
                    
                    if hit_target:
                        # 0. Weather Triggers
                        weather.apply_weather(move.name, "none")
                        
                        # 2. Stat Changes Phase
                        for stat_name, change in move.stat_changes:
                            target_mon = attacker if move.target == "user" else defender
                            target_mon.apply_stat_change(stat_name, change)

                        # 3. Secondary Effects Phase (Only procs on last hit generally, but Gen 3 is messy. 
                        # We will proc per hit for things like Secret Power, consistent with modern mechanics)
                        if defender.ability != "shield-dust":
                            if move.flinch_chance > 0 and rng.random() < (move.flinch_chance / 100.0):
                                defender.flinched = True
                            _apply_status_effect(attacker, defender, move, rng)
                            
                        # 4. Contact Abilities
                        if move.power > 0 and move.type in PHYS_TYPES:
                            if defender.ability == "static" and rng.random() < 0.3:
                                attacker.inflict_status("paralysis", rng)
                            elif defender.ability == "poison-point" and rng.random() < 0.3:
                                attacker.inflict_status("poison", rng)
                            elif defender.ability == "flame-body" and rng.random() < 0.3:
                                attacker.inflict_status("burn", rng)
                            elif defender.ability == "effect-spore" and rng.random() < 0.3:
                                rng_val = rng.random()
                                if rng_val < 0.33: attacker.inflict_status("poison", rng)
                                elif rng_val < 0.66: attacker.inflict_status("paralysis", rng)
                                else: attacker.inflict_status("sleep", rng)
                            elif defender.ability == "cute-charm" and rng.random() < 0.3:
                                attacker.inflict_status("infatuation", rng)
                            elif defender.ability == "rough-skin":
                                attacker.take_damage(max(1, attacker.hp_max // 16))
                                
                        # Gen 3 Castform interaction handled by 'forecast' in stat calcs. We ignore forms for now.
                        
                        # 5. Drain & Recoil Phase
                        if move.name == "struggle":
                            attacker.take_damage(max(1, attacker.hp_max // 4))
                        elif move.drain != 0 and dmg > 0:
                            drain_amount = math.floor(dmg * (move.drain / 100.0))
                            if drain_amount > 0:
                                if defender.ability == "liquid-ooze":
                                    attacker.take_damage(drain_amount)
                                else:
                                    # Heal (e.g. Giga Drain)
                                    attacker.hp = min(attacker.hp_max, attacker.hp + drain_amount)
                            elif drain_amount < 0:
                                # Recoil (e.g. Double-Edge)
                                attacker.take_damage(abs(drain_amount))
                            
            return attacker.is_fainted or defender.is_fainted

        if player_first:
            if execute_action(player, opponent, p_act): break
            if not opponent.flinched:
                if execute_action(opponent, player, o_act): break
        else:
            if execute_action(opponent, player, o_act): break
            if not player.flinched:
                if execute_action(player, opponent, p_act): break
                
        # Reset flinch
        player.flinched = False
        opponent.flinched = False
        
        # End of turn effects
        _apply_end_of_turn(player, weather)
        _apply_end_of_turn(opponent, weather)
        weather.decrement([])
        if player.is_fainted or opponent.is_fainted:
            break

    # Battle over — check who won
    if opponent.is_fainted:
        xp = calc_trainer_xp(opponent.base_xp_yield, opponent.level)
        if player.gain_xp(xp, move_pool, rng=rng):
            leveled_up = True
        return BattleResult(player_won=True, turns=turn, leveled_up=leveled_up)
    
    return BattleResult(player_won=False, turns=turn, leveled_up=leveled_up)
