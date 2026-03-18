# engine/damage.py
# Gen 3 damage formula and expected-damage helper for AI decisions.

from __future__ import annotations
import math
import random

from data.moves import Move
from data.type_chart import type_effectiveness


# Gen 3 physical types (determines which attack/defense stat to use)
PHYS_TYPES = frozenset({
    "normal","fighting","flying","poison","ground","rock","bug","ghost","steel"
})

# Sound-based moves (blocked by Soundproof)
SOUND_MOVES = frozenset({
    "growl","roar","sing","supersonic","screech","snore","uproar",
    "heal-bell","perish-song","grasswhistle","hyper-voice","metal-sound",
})


def _ability_immunity(move: Move, attacker, defender, is_prediction: bool = False) -> str:
    """
    Check Gen 3 ability-based immunity.
    If is_prediction is True (AI scoring), it only considers `revealed_ability`.
    If is_prediction is False (actual combat), it checks real `ability` and reveals it if activated.
    Returns:
      'immune'  — move does nothing (0 damage)
      'absorb'  — move heals the defender (return 0 but heal)
      'block'   — move is completely negated
      'wonder'  — Wonder Guard: only super-effective hits land
      ''        — no immunity, proceed normally
    """
    ab = getattr(defender, 'revealed_ability' if is_prediction else 'ability', 'none') or 'none'
    mt = move.type

    result = ''
    
    # Flash Fire: immune to Fire, raises fire-type moves on activation
    if ab == 'flash-fire' and mt == 'fire':
        result = 'immune'

    # Levitate: immune to Ground
    elif ab == 'levitate' and mt == 'ground':
        result = 'immune'

    # Volt Absorb: immune to Electric, heals 25% max HP
    elif ab == 'volt-absorb' and mt == 'electric':
        result = 'absorb'

    # Water Absorb / Dry Skin: immune to Water
    elif ab in ('water-absorb', 'dry-skin') and mt == 'water':
        result = 'absorb'

    # Wonder Guard: only super-effective hits deal damage
    elif ab == 'wonder-guard':
        eff = type_effectiveness(mt, list(defender.types))
        if eff <= 1.0:
            result = 'immune'

    # Soundproof: immune to sound-based moves
    elif ab == 'soundproof' and move.name in SOUND_MOVES:
        result = 'immune'

    # Damp: blocks Explosion and Self-Destruct
    elif ab == 'damp' and move.name in ('explosion', 'self-destruct', 'mind-blown'):
        result = 'immune'
        
    # If this was an actual attack and an immunity triggered, the ability is now revealed!
    if not is_prediction and result != '' and ab != 'none':
        defender.revealed_ability = ab
        
    return result


def _stat_multiplier(stage: int) -> float:
    """Gen 3 stat multiplier for Atk, Def, SpA, SpD, Spe."""
    stage = max(-6, min(6, stage))
    if stage >= 0:
        return (2 + stage) / 2.0
    else:
        return 2.0 / (2 - stage)

def _acc_multiplier(acc_stage: int, eva_stage: int) -> float:
    """Gen 3 accuracy multiplier."""
    stage = max(-6, min(6, acc_stage - eva_stage))
    if stage >= 0:
        return (3 + stage) / 3.0
    else:
        return 3.0 / (3 - stage)

def _attacker_stat(move: Move, attacker, is_crit: bool = False, is_prediction: bool = False) -> int:
    """Return Atk or SpAtk depending on move category. Apply Burn penalty and stat stages."""
    ab = getattr(attacker, 'ability', 'none') or 'none'

    if move.type in PHYS_TYPES:
        stat = attacker.atk
        if attacker.status == "burn" and ab != "guts":
            stat = max(1, stat // 2)
        
        stage = attacker.stat_stages["attack"]
        # Crits ignore negative attack stages
        if is_crit and stage < 0:
            stage = 0
            
        stat = math.floor(stat * _stat_multiplier(stage))
        
        # Huge Power / Pure Power doubles the final calculated Attack stat
        if ab in ('huge-power', 'pure-power'):
            stat *= 2
        elif ab == 'guts' and attacker.status != "none":
            stat = math.floor(stat * 1.5)
        elif ab == 'hustle':
            stat = math.floor(stat * 1.5)
            
        return max(1, stat)
    else:
        stat = attacker.spatk
        stage = attacker.stat_stages["special-attack"]
        if is_crit and stage < 0:
            stage = 0
            
        stat = math.floor(stat * _stat_multiplier(stage))
        
        # Plus / Minus ignore, no doubles
        
        return max(1, stat)


def _defender_stat(move: Move, defender, is_crit: bool = False, is_prediction: bool = False) -> int:
    """Return Def or SpDef depending on move category. Apply stat stages."""
    ab = getattr(defender, 'revealed_ability' if is_prediction else 'ability', 'none') or 'none'

    if move.type in PHYS_TYPES:
        stat = defender.def_
        stage = defender.stat_stages["defense"]
        # Crits ignore positive defense stages
        if is_crit and stage > 0:
            stage = 0
            
        stat = math.floor(stat * _stat_multiplier(stage))
        
        if ab == 'marvel-scale' and defender.status != "none":
            stat = math.floor(stat * 1.5)
            
        return max(1, stat)
        
    stat = defender.spdef
    stage = defender.stat_stages["special-defense"]
    if is_crit and stage > 0:
        stage = 0
        
    stat = math.floor(stat * _stat_multiplier(stage))
    return max(1, stat)


def _get_actual_power(move: Move, attacker) -> int:
    """Calculate effective power for variable-power moves based on current HP."""
    if not move.variable_power:
        return move.power
    
    if move.name in ("eruption", "water-spout"):
        return max(1, math.floor(150 * attacker.hp / attacker.hp_max))
    
    if move.name in ("flail", "reversal"):
        p = math.floor(48 * attacker.hp / attacker.hp_max)
        if p <= 1: return 200
        elif p <= 4: return 150
        elif p <= 9: return 100
        elif p <= 16: return 80
        elif p <= 32: return 40
        else: return 20
        
    return move.power


def calc_damage(
    move: Move,
    attacker,
    defender,
    rng: random.Random | None = None,
    weather: str = "none"
) -> int:
    """
    Gen 3 damage formula:
      damage = floor(floor((floor(2*L/5+2) * power * A/D) / 50) + 2)
               * critical * rand_roll * stab * type_eff

    Returns 0 on miss or immunity.
    rng=None uses deterministic max rolls (no crit, roll=1.0).
    """
    if move.power == 0:
        return 0

    # Ability immunity check
    immunity = _ability_immunity(move, attacker, defender)
    if immunity in ('immune', 'block'):
        return 0
    if immunity == 'absorb':
        # Heal defender for 1/4 max HP; return 0 so no damage is recorded
        heal = max(1, defender.hp_max // 4)
        defender.hp = min(defender.hp_max, defender.hp + heal)
        return 0

    # 1. Accuracy check
    if not move.never_miss:
        roll = rng.random() if rng else 0.0
        acc_mult = _acc_multiplier(attacker.stat_stages["accuracy"], defender.stat_stages["evasion"])
        final_acc = (move.accuracy / 100.0) * acc_mult
        
        attacker_ab = getattr(attacker, 'ability', 'none') or 'none'
        if attacker_ab == 'hustle' and move.type in PHYS_TYPES:
            final_acc *= 0.8
            
        if rng and roll > final_acc:
            return 0

    # 2. Base Stats & Power
    level = attacker.level
    power = _get_actual_power(move, attacker)
    
    attacker_ab = getattr(attacker, 'ability', 'none') or 'none'
    defender_ab = getattr(defender, 'ability', 'none') or 'none'
    
    # Pinch abilities
    hp_thresh = attacker.hp_max / 3.0
    if attacker.hp <= hp_thresh:
        if attacker_ab == 'overgrow' and move.type == 'grass':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'blaze' and move.type == 'fire':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'torrent' and move.type == 'water':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'swarm' and move.type == 'bug':
            power = math.floor(power * 1.5)
            
    # Thick Fat
    if defender_ab == 'thick-fat' and move.type in ('fire', 'ice'):
        power = max(1, power // 2)
    
    # 3. Critical Hit (1/16 chance)
    is_crit = False
    crit_mult = 1.0
    if rng and rng.random() < 0.0625:
        is_crit = True
        crit_mult = 2.0

    A = _attacker_stat(move, attacker, is_crit)
    D = max(1, _defender_stat(move, defender, is_crit))

    # 4. Core Formula
    damage = math.floor(2 * level / 5 + 2)
    damage = math.floor(damage * power * A / D)
    damage = math.floor(damage / 50) + 2

    # 5. Modifiers
    damage = math.floor(damage * crit_mult)
    
    # 6. Random Roll (0.85 - 1.0)
    roll = rng.uniform(0.85, 1.0) if rng else 1.0
    damage = math.floor(damage * roll)

    # 7. STAB
    if move.type in attacker.types:
        damage = math.floor(damage * 1.5)

    # 8. Weather Modifiers
    if weather == "sun":
        if move.type == "fire":
            damage = math.floor(damage * 1.5)
        elif move.type == "water":
            damage = math.floor(damage * 0.5)
    elif weather == "rain":
        if move.type == "water":
            damage = math.floor(damage * 1.5)
        elif move.type == "fire":
            damage = math.floor(damage * 0.5)

    # 9. Type Effectiveness
    eff = type_effectiveness(move.type, list(defender.types))
    damage = math.floor(damage * eff)

    return max(1, damage) if eff > 0 else 0


def expected_damage(move: Move, attacker, defender, weather: str = "none") -> float:
    """
    Deterministic expected value of damage.
    Used by the AI to rank moves.
    """
    if move.power == 0:
        return 0.0

    # Ability immunity — treat as 0 expected damage so AI avoids the move
    # Passing is_prediction=True means AI relies on revealed_ability
    immunity = _ability_immunity(move, attacker, defender, is_prediction=True)
    if immunity in ('immune', 'block', 'absorb', 'wonder'):
        return 0.0

    level = attacker.level
    power = _get_actual_power(move, attacker)
    
    attacker_ab = getattr(attacker, 'ability', 'none') or 'none'
    defender_ab = getattr(defender, 'revealed_ability', 'none') or 'none'
    
    # Pinch abilities
    hp_thresh = attacker.hp_max / 3.0
    if attacker.hp <= hp_thresh:
        if attacker_ab == 'overgrow' and move.type == 'grass':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'blaze' and move.type == 'fire':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'torrent' and move.type == 'water':
            power = math.floor(power * 1.5)
        elif attacker_ab == 'swarm' and move.type == 'bug':
            power = math.floor(power * 1.5)
            
    # Thick Fat
    if defender_ab == 'thick-fat' and move.type in ('fire', 'ice'):
        power = max(1, power // 2)
    
    # Avg normal damage (15/16)
    A_nom = _attacker_stat(move, attacker, False, is_prediction=True)
    D_nom = max(1, _defender_stat(move, defender, False, is_prediction=True))
    dmg_nom = math.floor(2 * level / 5 + 2)
    dmg_nom = math.floor(dmg_nom * power * A_nom / D_nom)
    dmg_nom = math.floor(dmg_nom / 50) + 2
    
    # Avg crit damage (1/16)
    A_crit = _attacker_stat(move, attacker, True, is_prediction=True)
    D_crit = max(1, _defender_stat(move, defender, True, is_prediction=True))
    dmg_crit = math.floor(2 * level / 5 + 2)
    dmg_crit = math.floor(dmg_crit * power * A_crit / D_crit)
    dmg_crit = math.floor(dmg_crit / 50) + 2
    dmg_crit = math.floor(dmg_crit * 2.0)

    acc = 1.0 if move.never_miss else move.accuracy / 100.0
    stab = 1.5 if move.type in attacker.types else 1.0
    eff = type_effectiveness(move.type, list(defender.types))
    
    weather_mod = 1.0
    if weather == "sun":
        if move.type == "fire": weather_mod = 1.5
        elif move.type == "water": weather_mod = 0.5
    elif weather == "rain":
        if move.type == "water": weather_mod = 1.5
        elif move.type == "fire": weather_mod = 0.5
    
    avg_base = (dmg_nom * 15/16 + dmg_crit * 1/16)
    return avg_base * 0.925 * stab * eff * acc * weather_mod
