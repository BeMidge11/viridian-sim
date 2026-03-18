# engine/ai.py
# Greedy move selector: pick the move with highest expected damage vs opponent.
# Both player and enemy use the same logic (symmetric optimal play).

from __future__ import annotations
import math
import random
from data.moves import Move
from engine.damage import expected_damage, _stat_multiplier
from engine.pokemon_instance import SPEC_TYPES


def score_move(move: Move, attacker, defender, weather_condition: str = "none") -> float:
    """
    Gen 3 'Smart AI' scoring heuristic.
    Base score is the expected damage the move will deal.
    Adjustments are made based on Gen 3 logic:
    - Avoid status moves if target already has a non-volatile status.
    - Heavily penalize moves with 0 expected damage (immunities or 0 base power).
    - Favor moves with good secondary effects or priority if they can KO.
    """
    # 1. Base Score = Expected Damage
    score = expected_damage(move, attacker, defender, weather_condition)
    
    # Check if this move can KO the defender this turn
    can_ko = score >= defender.hp
    
    # 2. Status Move Logic (Moves that deal 0 damage but apply a status)
    if move.power == 0:
        if move.name == "splash":
            # Gen 3 AI treats Splash mysteriously like a stat buff.
            if attacker.hp > (attacker.hp_max / 2):
                score += 60.0
            else:
                score += 10.0
        elif move.ailment != "none" and move.ailment_chance > 0:
            # Don't try to status a fainted or already statused opponent
            if defender.is_fainted or defender.status != "none":
                return -1000.0
            
            # Confusion check
            if move.ailment == "confusion" and defender.confused_turns > 0:
                return -1000.0
                
            # If it's a valid status, assign a base value. (Equivalent to a 40-60 base power move)
            score = 50.0 
        elif move.stat_changes:
            # It's a stat-changing move. Let the Expert AI step handle scoring it.
            score = 0.0
            attacker_healthy = attacker.hp >= (attacker.hp_max * 0.8)
            defender_healthy = defender.hp >= (defender.hp_max * 0.8)
            
            # Setup sweep logic: If both are healthy, setting up is extremely valuable.
            # Particularly Evasion (Double Team) or offensive stats (Swords Dance).
            for stat_name, change in move.stat_changes:
                target_mon = attacker if move.target == "user" else defender
                
                # Don't try to boost if already at +6 / -6
                current_stage = target_mon.stat_stages.get(stat_name, 0)
                if (change > 0 and current_stage >= 6) or (change < 0 and current_stage <= -6):
                    continue
                    
                # High HP scenario: value setup strongly
                if attacker_healthy:
                    if stat_name in ("evasion", "accuracy"):
                        score += abs(change) * 45.0  # Double Team / Sand-Attack are menace moves
                    elif stat_name in ("attack", "special-attack", "speed"):
                        score += abs(change) * 40.0  # Dragon Dance / Swords Dance sweep setups
                    elif stat_name in ("defense", "special-defense"):
                        score += abs(change) * 20.0  # Iron Defense / Cosmic Power stall setups
                        
        elif move.name in ("rain-dance", "sunny-day", "sandstorm", "hail"):
            # Weather setting
            is_rain = weather_condition == "rain"
            is_sun = weather_condition == "sun"
            is_sand = weather_condition == "sandstorm"
            is_hail = weather_condition == "hail"
            
            # Don't set weather if already active
            if (move.name == "rain-dance" and is_rain) or \
               (move.name == "sunny-day" and is_sun) or \
               (move.name == "sandstorm" and is_sand) or \
               (move.name == "hail" and is_hail):
                return -1000.0
                
            # If healthy, weather setting can be a strong pivot
            if attacker.hp >= (attacker.hp_max * 0.8):
                score = 55.0
            else:
                score = 10.0
                
        elif move.name == "mirror-coat":
            # Check if opponent is likely to use special attacks
            opp_moves = defender.moveset
            has_special = any(m.power > 0 and m.type in SPEC_TYPES for m in opp_moves)
            score = 15.0 if has_special else -1000.0
        else:
            return -1000.0

    # 3. Penalize immune or totally ineffective attacks
    if score == 0 and move.power > 0:
        return -1000.0

    # 4. KO Handling and Priority
    # 4. priority handling
    if can_ko:
        if move.priority > 0:
            score = score + 1000.0
        else:
            score = score + 500.0
        
    # 5. Secondary Status Effects
    if move.power > 0 and move.ailment != "none" and defender.status == "none":
        score = score + ((move.ailment_chance / 100.0) * 10.0)

    # 6. Stat Stage Modifiers ("Expert AI" handling)
    if move.stat_changes:
        for stat_name, change in move.stat_changes:
            c = int(change)  # Type cast for static analysis
            
            # Self-targeting buffs
            if move.target == "user" and c > 0:
                # Don't use if already maxed
                if attacker.stat_stages.get(stat_name, 0) >= 6:
                    return -1000.0
                # Expert AI ONLY buffs at MAX HP
                if attacker.hp == attacker.hp_max:
                    score = score + (60.0 * float(c))
                else:
                    return -1000.0  # Refuse to buff if damaged
            
            # Opponent-targeting debuffs
            if move.target != "user" and c < 0:
                # --- Hyper Cutter check ---
                if stat_name == "attack" and getattr(defender, "revealed_ability", "") == "hyper-cutter":
                    return -1000.0

                # Don't drop if already min
                if defender.stat_stages.get(stat_name, 0) <= -6:
                    return -1000.0
                
                # Expert AI ONLY debuffs at MAX HP
                if attacker.hp < attacker.hp_max:
                    return -1000.0
                
                # Speed control: heavily favor dropping speed if currently slower
                if stat_name == "speed":
                    eff_atk_spe = attacker.spe * _stat_multiplier(attacker.stat_stages.get("speed", 0))
                    eff_def_spe = defender.spe * _stat_multiplier(defender.stat_stages.get("speed", 0))
                    if eff_atk_spe < eff_def_spe:
                        score = score + 80.0 * abs(float(c))
                    else:
                        score = score + 20.0 * abs(float(c))
                else:
                    score = score + 40.0 * abs(float(c))

    # 8. Player Bias: Human players "almost always" use attacking moves.
    # Penalize status moves heavily for the player instance.
    if attacker.is_player and move.power == 0:
        score = score - 100.0

    return float(score)


def score_move_general(move: Move, attacker) -> float:
    """
    Score a move for the given attacker without a specific defender.
    Used to compare moves in isolation (e.g., during level-up replacement decisions).

    Creates a neutral dummy defender at the same level with balanced stats
    and no type advantages, then delegates to score_move.
    """
    from engine.pokemon_instance import PokemonInstance, _gen3_stat, _gen3_hp

    # Neutral dummy: same level, neutral base stats (~50 across the board),
    # normal typing (no immunities, no weaknesses to trigger easy scores).
    dummy_base = 50
    dummy_level = attacker.level

    class _DummyDefender:
        """Minimal stand-in for a PokemonInstance, no dataclass overhead."""
        def __init__(self):
            self.name = "Dummy"
            self.types = ("normal",)
            self.level = dummy_level
            self.hp_max = _gen3_hp(dummy_base, dummy_level)
            self.hp = self.hp_max
            self.atk = _gen3_stat(dummy_base, dummy_level)
            self.def_ = _gen3_stat(dummy_base, dummy_level)
            self.spatk = _gen3_stat(dummy_base, dummy_level)
            self.spdef = _gen3_stat(dummy_base, dummy_level)
            self.spe = _gen3_stat(dummy_base, dummy_level)
            self.status = "none"
            self.confused_turns = 0
            self.flinched = False
            self.is_fainted = False
            self.is_player = False
            self.ability = "none"
            self.revealed_ability = "none"
            self.stat_stages = {
                "attack": 0, "defense": 0, "special-attack": 0,
                "special-defense": 0, "speed": 0, "accuracy": 0, "evasion": 0
            }
            # Empty moveset — mirror coat etc. won't trigger positively
            self.moveset = []
            self.ability = "none"

    dummy = _DummyDefender()
    return score_move(move, attacker, dummy)


def best_action(attacker, defender, available_moves: list[Move] | None = None, weather_condition: str = "none") -> tuple[str, Move | str]:
    """
    Select the move or item that yields the highest expected value.
    Returns a tuple of ("MOVE", Move) or ("ITEM", str)
    """
    moves = available_moves if available_moves is not None else attacker.moveset
    if not moves:
        raise ValueError("Pokemon has no moves!")

    scored = [(score_move(m, attacker, defender, weather_condition), m) for m in moves]
    
    # Sort by Score (desc), then Accuracy (desc), then Power (desc)
    scored.sort(key=lambda x: (x[0], x[1].accuracy, x[1].power), reverse=True)
    
    # Collect all moves that share the highest score/acc/power
    best_score = scored[0][0]
    best_acc = scored[0][1].accuracy
    best_power = scored[0][1].power
    
    best_m = None
    # After scoring & finding best score, apply Gen 3 random overrides conditionally
    if best_score < 60.0:
        eruption_moves = [m for m in moves if m.name in {"eruption", "water-spout"}]
        if eruption_moves and random.random() < 0.25:
            best_m = random.choice(eruption_moves)

    if not best_m:
        best_options = [
            m for (s, m) in scored 
            if s == best_score and m.accuracy == best_acc and m.power == best_power
        ]
        best_m = random.choice(best_options)

    # --- ITEM LOGIC ---
    if attacker.is_player and attacker.inventory:
        # Estimate enemy's threat level based ONLY on moves it has revealed
        enemy_scores = [score_move(m, defender, attacker, weather_condition) for m in defender.revealed_moves if m.power > 0]
        max_enemy_dmg = max(enemy_scores) if enemy_scores else 0.0

        # Provide a baseline threat if the enemy hasn't revealed their full moveset
        if len(defender.revealed_moves) < max(1, len(defender.moveset)):
            blind_power = min(90, 40 + (defender.level // 2))
            from engine.damage import PHYS_TYPES
            for t in defender.types:
                cat = "physical" if t in PHYS_TYPES else "special"
                blind_move = Move(
                    name=f"blind-threat-{t}",
                    type=t,
                    category=cat,
                    power=blind_power,
                    accuracy=100,
                    pp_max=10
                )
                blind_score = score_move(blind_move, defender, attacker, weather_condition)
                if blind_score > max_enemy_dmg:
                    max_enemy_dmg = blind_score

        # Heuristic 1: Status curing is paramount if we have Full Heal/Restore or specific heals
        if attacker.status != "none" or attacker.confused_turns > 0:
            if attacker.inventory.get("full-restore", 0) > 0:
                return ("ITEM", "full-restore")
            if attacker.inventory.get("full-heal", 0) > 0:
                return ("ITEM", "full-heal")
            
            if attacker.status in ("poison", "bad-poison") and attacker.inventory.get("antidote", 0) > 0:
                return ("ITEM", "antidote")
            if attacker.status == "paralysis" and attacker.inventory.get("paralyze-heal", 0) > 0:
                return ("ITEM", "paralyze-heal")
            if attacker.status == "sleep" and attacker.inventory.get("awakening", 0) > 0:
                return ("ITEM", "awakening")
            if attacker.status == "burn" and attacker.inventory.get("burn-heal", 0) > 0:
                return ("ITEM", "burn-heal")
            if attacker.status == "freeze" and attacker.inventory.get("ice-heal", 0) > 0:
                return ("ITEM", "ice-heal")

        # Heuristic 2: Survival Potion popping
        if max_enemy_dmg >= attacker.hp:
            # We are in KO range. Are we faster and can we KO them first?
            # Require 90% expected-to-hp confidence to guarantee the oneshot
            if best_score >= (defender.hp * 0.9) and best_m.priority >= 0:
                eff_atk_spe = attacker.spe * _stat_multiplier(attacker.stat_stages.get("speed", 0))
                
                # Estimate opponent's speed range based on randomized BST distribution
                bst = sum(defender.base_stats.values())
                min_base_spe = 1
                max_base_spe = min(255, bst - 5)
                
                def estimate_spe(base_val: int) -> int:
                    # IronMon standard: IV=15, EV=0
                    return math.floor((2 * base_val + 15) * defender.level / 100) + 5
                
                min_spe = estimate_spe(min_base_spe) * _stat_multiplier(defender.stat_stages.get("speed", 0))
                max_spe = estimate_spe(max_base_spe) * _stat_multiplier(defender.stat_stages.get("speed", 0))
                
                if eff_atk_spe >= max_spe:
                    outspeed_chance = 1.0
                elif eff_atk_spe <= min_spe:
                    outspeed_chance = 0.0
                else:
                    outspeed_chance = (eff_atk_spe - min_spe) / max(1, max_spe - min_spe)
                
                if outspeed_chance >= 0.85 or best_m.priority > 0:
                    # We are highly confident we outspeed and kill. Don't waste a potion.
                    return ("MOVE", best_m)

            # We need to heal to survive
            potions = [
                ("max-potion", 999), 
                ("full-restore", 999), 
                ("hyper-potion", 200), 
                ("super-potion", 50), 
                ("potion", 20)
            ]
            for item_name, heal_amt in potions:
                if attacker.inventory.get(item_name, 0) > 0:
                    # If popping this potion puts our HP strictly higher than their max damage, use it
                    if min(attacker.hp_max, attacker.hp + heal_amt) > max_enemy_dmg:
                        return ("ITEM", item_name)

    return ("MOVE", best_m)
