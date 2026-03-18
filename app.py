"""
app.py — Viridian Forest IronMon Simulator
Streamlit web app wrapping the Monte Carlo engine.
Run: streamlit run app.py
"""
from __future__ import annotations

import json
import math
import random
import pathlib
from functools import lru_cache

import streamlit as st
import plotly.graph_objects as go
from data.pokemon import Species

st.set_page_config(
    page_title="Viridian Forest Simulator",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap');
  html,body,[class*="css"]{font-family:'Inter',sans-serif;}
  .stApp{background:#0a0f1a;}
  section[data-testid="stSidebar"]{background:#0d1526;border-right:1px solid #1e2d47;}
  section[data-testid="stSidebar"] .stTextInput input,
  section[data-testid="stSidebar"] .stNumberInput input,
  section[data-testid="stSidebar"] .stSelectbox>div>div{
    background:#111c30!important;border:1px solid #1e3a5f!important;color:#e2e8f0!important;border-radius:8px;}
  .hero-banner{background:linear-gradient(135deg,#0d1526,#0f2744,#091d35);border:1px solid #1e3a5f;
    border-radius:16px;padding:28px 36px;margin-bottom:24px;position:relative;overflow:hidden;}
  .hero-banner::before{content:"🌿";position:absolute;font-size:120px;right:20px;top:-10px;opacity:.08;}
  .hero-title{font-size:2.2rem;font-weight:900;
    background:linear-gradient(90deg,#34d399,#60a5fa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0 0 8px;}
  .hero-sub{color:#94a3b8;font-size:.95rem;margin:0;}
  .metric-card{background:#0d1526;border:1px solid #1e3a5f;border-radius:14px;padding:22px 24px;text-align:center;height:100%;}
  .metric-label{color:#64748b;font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px;}
  .metric-value{font-size:2.4rem;font-weight:900;line-height:1.1;}
  .metric-ci{color:#64748b;font-size:.8rem;margin-top:4px;}
  .rate-high{color:#34d399;}.rate-mid{color:#fbbf24;}.rate-low{color:#f87171;}
  .section-header{color:#e2e8f0;font-size:1.1rem;font-weight:700;letter-spacing:.03em;
    margin:20px 0 8px;padding-bottom:8px;border-bottom:1px solid #1e3a5f;}
  .stButton>button{width:100%;background:linear-gradient(135deg,#059669,#0ea5e9)!important;
    color:white!important;font-weight:700!important;font-size:1rem!important;border:none!important;
    border-radius:10px!important;padding:14px!important;margin-top:4px;letter-spacing:.04em;}
  .stButton>button:hover{opacity:.88!important;transform:translateY(-1px)!important;}
  .type-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;
    font-weight:700;letter-spacing:.05em;text-transform:uppercase;margin-right:4px;}
  .stSidebar label{color:#94a3b8!important;font-size:.82rem!important;}
  div[data-testid="stSidebarNav"]{display:none;}
  .autofill-banner{background:#0d2a1f;border:1px solid #065f46;border-radius:10px;
    padding:10px 14px;margin-bottom:10px;font-size:.83rem;color:#6ee7b7;}
  /* Shrink nature sliders */
  div[data-testid="stSlider"] .stSlider {padding:0!important;}
  div[data-testid="stSlider"] label {display:none!important;}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TYPE_COLOURS = {
    "normal":"#A8A878","fire":"#F08030","water":"#6890F0","grass":"#78C850",
    "electric":"#F8D030","ice":"#98D8D8","fighting":"#C03028","poison":"#A040A0",
    "ground":"#E0C068","flying":"#A890F0","psychic":"#F85888","bug":"#A8B820",
    "rock":"#B8A038","ghost":"#705898","dragon":"#7038F8","dark":"#705848","steel":"#B8B8D0",
}
ALL_TYPES  = list(TYPE_COLOURS.keys())
STAT_KEY_MAP = {"hp":"hp","attack":"atk","defense":"def","special-attack":"spatk",
                "special-defense":"spdef","speed":"spe"}
TRAINER_LEVELS = {"Rick":"Lv 9×2","Anthony":"Lv 11–12","Charlie":"Lv 11×3","Doug":"Lv 11×3","Sammy":"Lv 14"}
STAT_KEYS = ["hp","atk","def","spatk","spdef","spe"]
STAT_LABELS = {"hp":"HP","atk":"Atk","def":"Def","spatk":"SpAtk","spdef":"SpDef","spe":"Spe"}
NATURE_OPTS = ["−","·","+"]

def type_badge(t):
    c = TYPE_COLOURS.get(t,"#666")
    return f'<span class="type-badge" style="background:{c};color:white;">{t}</span>'
def rate_class(r): return "rate-high" if r>=.5 else ("rate-mid" if r>=.25 else "rate-low")
def bar_colour(s): return f"rgb({int(255*(1-s))},{int(200*s)},60)"
def nature_mult(n): return 1.1 if n=="+" else (0.9 if n=="−" else 1.0)


# ── Gen 3 stat helpers ────────────────────────────────────────────────────────
def gen3_hp(base: int, level: int, iv: float = 15.5) -> int:
    return math.floor((2 * base + iv) * level / 100) + level + 10

def gen3_stat(base: int, level: int, iv: float = 15.5) -> int:
    return math.floor((2 * base + iv) * level / 100) + 5

def reverse_base_hp(stat_val: int, level: int, avg_iv: float = 15.5) -> int:
    """Inverse of gen3_hp — estimates base HP given the in-game HP value."""
    return max(1, round(((stat_val - level - 10) * 100 / level - avg_iv) / 2))

def reverse_base_stat(stat_val: int, level: int, avg_iv: float = 15.5) -> int:
    """Inverse of gen3_stat — estimates base stat given the in-game value."""
    return max(1, round(((stat_val - 5) * 100 / level - avg_iv) / 2))

def compatible_base_range_hp(stat_val: int, level: int) -> tuple[int, int]:
    """
    Enumerate every base HP (1-255) and keep those where IV in [0,31]
    can produce the observed stat value.  Returns (min_base, max_base).
    """
    lo, hi = 256, 0
    for base in range(1, 256):
        s_lo = math.floor((2 * base + 0)  * level / 100) + level + 10
        s_hi = math.floor((2 * base + 31) * level / 100) + level + 10
        if s_lo <= stat_val <= s_hi:
            lo = min(lo, base)
            hi = max(hi, base)
    return (lo, hi) if lo <= hi else (1, 255)

def compatible_base_range_stat(stat_val: int, level: int, nature: float = 1.0) -> tuple[int, int]:
    """
    Enumerate every non-HP base stat (1-255) and keep those where IV in [0,31]
    can produce the observed stat value with the given nature multiplier.
    Returns (min_base, max_base).
    """
    lo, hi = 256, 0
    for base in range(1, 256):
        # Stat = floor(floor((2*base + IV)*level/100 + 5) * nature)
        s_lo_unstaged = math.floor((2 * base + 0)  * level / 100) + 5
        s_hi_unstaged = math.floor((2 * base + 31) * level / 100) + 5
        
        res_lo = math.floor(s_lo_unstaged * nature)
        res_hi = math.floor(s_hi_unstaged * nature)
        
        if res_lo <= stat_val <= res_hi:
            lo = min(lo, base)
            hi = max(hi, base)
    return (lo, hi) if lo <= hi else (1, 255)

def bst_constrained_estimate(
    ranges: list[tuple[int, int]], bst: int
) -> list[int]:
    """
    Given compatible base ranges and known BST, return estimated base stats
    that sum to BST by scaling each range's midpoint proportionally.
    Each estimate is clamped to its compatible range.
    """
    mids = [(lo + hi) / 2.0 for lo, hi in ranges]
    mid_sum = sum(mids) or 1.0
    estimates = [max(lo, min(hi, round(m * bst / mid_sum)))
                 for (lo, hi), m in zip(ranges, mids)]
    # Adjust rounding error so they sum exactly to bst
    diff = bst - sum(estimates)
    for i in range(abs(diff)):
        idx = i % 6
        estimates[idx] = max(ranges[idx][0], min(ranges[idx][1],
                            estimates[idx] + (1 if diff > 0 else -1)))
    return estimates

def distribute_bst(bst: int, level: int) -> dict[str, int]:
    """Evenly distribute BST across 6 stats, compute Gen 3 stat at given level with avg IV=15.5."""
    per = bst // 6
    rem = bst - per * 6  # give remainder to HP
    return {
        "hp":    gen3_hp(per + rem, level),
        "atk":   gen3_stat(per, level),
        "def":   gen3_stat(per, level),
        "spatk": gen3_stat(per, level),
        "spdef": gen3_stat(per, level),
        "spe":   gen3_stat(per, level),
    }


# ── Pokémon lookup ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _pkmn_cache() -> dict[str, Species]:
    from data.pokemon import load_species_pool
    try:
        pool = load_species_pool()
        if not pool:
            st.error("No Pokémon species found. Check your data files.")
            return {}
        return {s.name.lower(): s for s in pool if hasattr(s, 'name')}
    except Exception as e:
        st.error(f"Error loading Pokémon data: {e}")
        return {}

def lookup_pokemon(slug: str) -> Species | None:
    c = _pkmn_cache()
    slug = slug.lower().strip().replace(" ","-").replace("_","-")
    if slug in c: return c[slug]
    m = [k for k in c if slug in k]
    return c[m[0]] if len(m) == 1 else None

def parse_pkmn(s: Species) -> dict:
    return {
        "types": list(s.types) if hasattr(s, 'types') else ["normal"], 
        "bst": s.bst if hasattr(s, 'bst') else 0,
    }


# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "w_potions": 0, "w_super_potions": 0, "w_hyper_potions": 0, 
    "w_max_potions": 0, "w_full_heals": 0, "w_full_restores": 0,
    "w_antidotes": 0, "w_paralyze_heals": 0, "w_awakenings": 0,
    "w_burn_heals": 0, "w_ice_heals": 0,
    "w_ai_knowledge": "Unknown (50% Chance of 1 vs 2 Abilities)",
    "n_seeds": 5000,
}
for i in range(1, 5):
    DEFAULTS[f"w{i}_name"] = ""
    DEFAULTS[f"w{i}_level"] = 8
    DEFAULTS[f"w{i}_type1"] = "normal"
    DEFAULTS[f"w{i}_type2"] = "—"
    DEFAULTS[f"w{i}_bst"] = 0
    DEFAULTS[f"w{i}_hp"] = 15
    DEFAULTS[f"w{i}_atk"] = 15
    DEFAULTS[f"w{i}_def"] = 15
    DEFAULTS[f"w{i}_spatk"] = 15
    DEFAULTS[f"w{i}_spdef"] = 15
    DEFAULTS[f"w{i}_spe"] = 15
    DEFAULTS[f"w{i}_hp_ntr"] = "·"
    for s in ["atk", "def", "spatk", "spdef", "spe"]:
        DEFAULTS[f"w{i}_{s}_ntr"] = "·"
    DEFAULTS[f"w{i}_move1"] = ""
    DEFAULTS[f"w{i}_move2"] = ""
    DEFAULTS[f"w{i}_move3"] = ""
    DEFAULTS[f"w{i}_move4"] = ""
    DEFAULTS[f"w{i}_ability"] = "none"
    DEFAULTS[f"w{i}_held_item"] = "none"
    DEFAULTS[f"_w{i}_prev_name"] = ""
    DEFAULTS[f"_w{i}_prev_bst"] = 0
    DEFAULTS[f"_w{i}_af_msg"] = ""

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def render_mon_tab(idx):
    c1, c2 = st.columns([2,1])
    names = [""] + list(_pkmn_cache().keys())
    cur_n = st.session_state[f"w{idx}_name"].lower()
    n_idx = names.index(cur_n) if cur_n in names else 0
    with c1: st.selectbox("Name (Autocomplete)", names, index=n_idx, key=f"w{idx}_name")
    with c2: st.number_input("Level", 1, 100, key=f"w{idx}_level")

    # autofill
    cur_name = st.session_state[f"w{idx}_name"].lower().strip().replace(" ","-").replace("_","-")
    prev_name_key = f"_w{idx}_prev_name"
    if cur_name and cur_name != st.session_state[prev_name_key]:
        s = lookup_pokemon(cur_name)
        if s and hasattr(s, 'name'):
            from data.moves import load_move_pool
            mv_pool = load_move_pool()
            pool_names = {m.name for m in mv_pool if hasattr(m, 'name')}
            pd = parse_pkmn(s)
            if pd:
                types = pd["types"]
                st.session_state[f"w{idx}_type1"] = types[0]
                st.session_state[f"w{idx}_type2"] = types[1] if len(types) > 1 else "—"
                st.session_state[f"w{idx}_bst"]   = pd["bst"]
                actual_name = s.name if hasattr(s, 'name') else cur_name
                st.session_state[prev_name_key] = actual_name
                st.session_state[f"_w{idx}_prev_bst"] = pd["bst"]
                st.session_state[f"_w{idx}_af_msg"] = f"✓ Autofilled from {actual_name.title()}"
                st.rerun()
        st.session_state[prev_name_key] = cur_name

    msg_key = f"_w{idx}_af_msg"
    if st.session_state[msg_key]:
        st.markdown(f'<div class="autofill-banner">{st.session_state[msg_key]}</div>', unsafe_allow_html=True)
        st.session_state[msg_key] = ""
    
    # Check species for specific auto-complete lists
    s_obj = lookup_pokemon(st.session_state[f"w{idx}_name"])
    species_moves = []
    species_abilities = []
    if s_obj and hasattr(s_obj, 'level_up_moves'):
        species_moves = list(set([m[1] for m in s_obj.level_up_moves]))
    if s_obj and hasattr(s_obj, 'abilities'):
        species_abilities = list(s_obj.abilities)
    
    from data.moves import load_move_pool
    mv_pool = load_move_pool()
    all_moves = sorted([m.name for m in mv_pool if hasattr(m, 'name')])
    all_abilities_set = set()
    for s in _pkmn_cache().values():
        if hasattr(s, 'abilities'):
            for ab in s.abilities: all_abilities_set.add(ab)
    all_abilities = sorted(list(all_abilities_set))

    ct1, ct2 = st.columns(2)
    t1 = st.session_state[f"w{idx}_type1"]
    t1_idx = ALL_TYPES.index(t1) if t1 in ALL_TYPES else 0
    t2 = st.session_state[f"w{idx}_type2"]
    t2_opts = ["—"] + ALL_TYPES
    t2_idx  = t2_opts.index(t2) if t2 in t2_opts else 0
    with ct1: st.selectbox("Type 1", ALL_TYPES, index=t1_idx, key=f"w{idx}_type1")
    with ct2: st.selectbox("Type 2 (opt)", t2_opts, index=t2_idx, key=f"w{idx}_type2")

    st.markdown('<div class="section-header">Stats &amp; BST Estimation</div>', unsafe_allow_html=True)
    lv = int(st.session_state[f"w{idx}_level"])
    
    # HP never has nature
    raw_ranges = [compatible_base_range_hp(int(st.session_state[f"w{idx}_hp"]), lv)]
    
    # Other stats
    for s_k in ["atk", "def", "spatk", "spdef", "spe"]:
        ntr = st.session_state.get(f"w{idx}_{s_k}_ntr", "·")
        mult = 1.1 if ntr == "+" else (0.9 if ntr == "−" else 1.0)
        raw_ranges.append(compatible_base_range_stat(int(st.session_state[f"w{idx}_{s_k}"]), lv, mult))

    range_keys = ["hp", "atk", "def", "spatk", "spdef", "spe"]
    known_bst = int(st.session_state[f"w{idx}_bst"] or 0)
    pt_estimates = bst_constrained_estimate(raw_ranges, known_bst) if known_bst > 0 else [round((lo + hi) / 2) for lo, hi in raw_ranges]
    rev_bases = dict(zip(range_keys, pt_estimates))
    rev_ranges = dict(zip(range_keys, raw_ranges))
    
    st.number_input("BST Total", 0, 780, key=f"w{idx}_bst")
    
    # HP Row
    s_key, label = "hp", "HP"
    base_pt, (lo, hi) = rev_bases[s_key], rev_ranges[s_key]
    cs, cv, cn = st.columns([2.5, 2.5, 5.0])
    with cs: st.markdown(f'<div style="padding-top:24px;line-height:1.3;"><span style="color:#94a3b8;font-size:.75rem;">{label}</span><br><span style="color:#34d399;font-weight:700;font-size:.78rem;">~{base_pt}</span><span style="color:#475569;font-size:.65rem;"> [{lo}–{hi}]</span></div>', unsafe_allow_html=True)
    with cv: st.number_input(label, 1, 999, key=f"w{idx}_{s_key}", label_visibility="collapsed")
    with cn: st.markdown('<div style="margin-top:22px;color:#475569;font-size:.7rem;text-align:center;">Fixed</div>', unsafe_allow_html=True)

    # Other stats with Nature radio buttons
    stat_pairs = [("atk","Atk"), ("def","Def"), ("spatk","SpAtk"), ("spdef","SpDef"), ("spe","Spe")]
    for s_key, label in stat_pairs:
        base_pt, (lo, hi) = rev_bases[s_key], rev_ranges[s_key]
        cs, cv, cn = st.columns([2.5, 2.5, 5.0])
        with cs: st.markdown(f'<div style="padding-top:24px;line-height:1.3;"><span style="color:#94a3b8;font-size:.75rem;">{label}</span><br><span style="color:#34d399;font-weight:700;font-size:.78rem;">~{base_pt}</span><span style="color:#475569;font-size:.65rem;"> [{lo}–{hi}]</span></div>', unsafe_allow_html=True)
        with cv: st.number_input(label, 1, 999, key=f"w{idx}_{s_key}", label_visibility="collapsed")
        
        # Nature Buttons (Mutually Exclusive)
        with cn:
            cur_ntr = st.session_state.get(f"w{idx}_{s_key}_ntr", "·")
            # Use segmented_control if available (modern Streamlit), else fallback to radio
            if hasattr(st, "segmented_control"):
                st.segmented_control(label, NATURE_OPTS, key=f"w{idx}_{s_key}_ntr", label_visibility="collapsed")
            else:
                sel_idx = NATURE_OPTS.index(cur_ntr) if cur_ntr in NATURE_OPTS else 1
                st.radio(label, NATURE_OPTS, index=sel_idx, key=f"w{idx}_{s_key}_ntr", horizontal=True, label_visibility="collapsed")

    st.markdown('<div class="section-header">Moves & Ability (Autocomplete as Typed)</div>', unsafe_allow_html=True)
    
    # Move choices: show species moves first, then others
    other_moves = sorted(list(set(all_moves) - set(species_moves)))
    move_opts = sorted(species_moves) + ["--- ALL MOVES ---"] + other_moves
    if "" not in move_opts: move_opts = [""] + move_opts
    
    def get_idx(val, opts):
        if val in opts: return opts.index(val)
        return 0

    st.selectbox("Move 1", move_opts, index=get_idx(st.session_state[f"w{idx}_move1"], move_opts), key=f"w{idx}_move1")
    st.selectbox("Move 2", move_opts, index=get_idx(st.session_state[f"w{idx}_move2"], move_opts), key=f"w{idx}_move2")
    st.selectbox("Move 3", move_opts, index=get_idx(st.session_state[f"w{idx}_move3"], move_opts), key=f"w{idx}_move3")
    st.selectbox("Move 4", move_opts, index=get_idx(st.session_state[f"w{idx}_move4"], move_opts), key=f"w{idx}_move4")

    # Ability choices: species abilities first
    other_abs = sorted(list(set(all_abilities) - set(species_abilities)))
    ab_opts = sorted(species_abilities) + ["--- ALL ABILITIES ---"] + other_abs
    if "none" not in ab_opts: ab_opts = ["none"] + ab_opts
    st.selectbox("Ability", ab_opts, index=get_idx(st.session_state[f"w{idx}_ability"], ab_opts), key=f"w{idx}_ability")
    
    from sim.randomizer import VALID_BERRIES
    st.selectbox("Held Item (Berry)", ["none"] + VALID_BERRIES, key=f"w{idx}_held_item")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎮 Pokémon")
    tabs = st.tabs(["Mon 1", "Mon 2", "Mon 3", "Mon 4"])
    for i, tab in enumerate(tabs):
        with tab:
            render_mon_tab(i + 1)
            
    st.markdown("## 🎒 Bag Items")
    ic1, ic2 = st.columns(2)
    with ic1: st.number_input("Potions (20)", 0, 999, key="w_potions")
    with ic1: st.number_input("Super Pots (50)", 0, 999, key="w_super_potions")
    with ic1: st.number_input("Hyper Pots (200)", 0, 999, key="w_hyper_potions")
    with ic2: st.number_input("Max Potions (Full)", 0, 999, key="w_max_potions")
    with ic2: st.number_input("Full Heals", 0, 999, key="w_full_heals")
    with ic2: st.number_input("Full Restores", 0, 999, key="w_full_restores")
    
    st.markdown("### Specific Cures")
    sc1, sc2 = st.columns(2)
    with sc1: st.number_input("Antidotes", 0, 999, key="w_antidotes")
    with sc1: st.number_input("Paralyze Heals", 0, 999, key="w_paralyze_heals")
    with sc1: st.number_input("Awakenings", 0, 999, key="w_awakenings")
    with sc2: st.number_input("Burn Heals", 0, 999, key="w_burn_heals")
    with sc2: st.number_input("Ice Heals", 0, 999, key="w_ice_heals")

    st.markdown("## ⚙️ Options")
    st.radio("AI Knowledge of My Ability", 
        ["Unknown (50% Chance of 1 vs 2 Abilities)", "1 Ability (AI knows immediately)", "2 Abilities (AI doesn't know until triggered)"],
        key="w_ai_knowledge")
    st.select_slider("Seeds", options=[500,1000,2000,5000,10000,25000], key="n_seeds")
    run_btn = st.button("⚡ Run Simulation", use_container_width=True)

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("""<div class="hero-banner">
  <p class="hero-title">Viridian Forest Simulator</p>
  <p class="hero-sub">Gen 3 IronMon · Multi-Compare · Monte Carlo</p>
</div>""", unsafe_allow_html=True)

if not run_btn:
    st.markdown("""
    <div style="text-align:center;padding:60px 20px;">
      <div style="font-size:64px;margin-bottom:16px;">🌿</div>
      <p style="font-size:1.1rem;color:#64748b;margin:0;">
        Configure up to 4 Pokémon in the sidebar tabs to compare them directly!
      </p>
    </div>""", unsafe_allow_html=True)
    st.stop()

def natured(val: int, ntr: str) -> int:
    return math.floor(val * nature_mult(ntr))

with st.spinner("Loading data…"):
    from data.moves import load_move_pool, Move
    from data.pokemon import load_species_pool
    from engine.pokemon_instance import make_player_instance
    from sim.monte_carlo import run_simulation
    move_pool = load_move_pool()

pool_by_name = {m.name: m for m in move_pool}
def resolve(slug):
    s = slug.lower().strip().replace(" ","-").replace("_","-")
    if s in pool_by_name: return pool_by_name[s]
    m = [k for k in pool_by_name if s in k]
    return pool_by_name[m[0]] if len(m)==1 else None

kb_map = {
    "Unknown (50% Chance of 1 vs 2 Abilities)": "unknown",
    "1 Ability (AI knows immediately)": "1-ability",
    "2 Abilities (AI doesn't know until triggered)": "2-abilities"
}

active_configs = []
for i in range(1, 5):
    if st.session_state[f"w{i}_name"].strip():
        active_configs.append(i)

if not active_configs:
    st.error("❌ Enter at least one Pokémon Name."); st.stop()

inventory = {
    "potion": st.session_state["w_potions"],
    "super-potion": st.session_state["w_super_potions"],
    "hyper-potion": st.session_state["w_hyper_potions"],
    "max-potion": st.session_state["w_max_potions"],
    "full-heal": st.session_state["w_full_heals"],
    "full-restore": st.session_state["w_full_restores"],
    "antidote": st.session_state["w_antidotes"],
    "paralyze-heal": st.session_state["w_paralyze_heals"],
    "awakening": st.session_state["w_awakenings"],
    "burn-heal": st.session_state["w_burn_heals"],
    "ice-heal": st.session_state["w_ice_heals"],
}

# Run sims
sim_results = {}
players = {}

prog = st.progress(0, text="Starting simulations...")
total_runs = len(active_configs) * st.session_state["n_seeds"]

runs_completed = 0
for idx in active_configs:
    raw_moves = [st.session_state[f"w{idx}_move{m}"] for m in (1,2,3,4)]
    good = [resolve(m) for m in raw_moves if m.strip() and resolve(m)]
    bad  = [m for m in raw_moves if m.strip() and not resolve(m)]
    
    name = st.session_state[f"w{idx}_name"].strip().title()
    if bad: 
        st.error(f"❌ {name}: Unknown move(s): **{', '.join(bad)}**"); st.stop()
    if not good: 
        st.error(f"❌ {name}: Enter at least one valid move."); st.stop()
        
    types = (st.session_state[f"w{idx}_type1"],) if st.session_state[f"w{idx}_type2"] == "—" else (st.session_state[f"w{idx}_type1"], st.session_state[f"w{idx}_type2"])
    
    player = make_player_instance(
        name=name, types=types, level=int(st.session_state[f"w{idx}_level"]),
        hp_max=natured(int(st.session_state[f"w{idx}_hp"]), st.session_state[f"w{idx}_hp_ntr"]),
        atk=natured(int(st.session_state[f"w{idx}_atk"]), st.session_state[f"w{idx}_atk_ntr"]),
        def_=natured(int(st.session_state[f"w{idx}_def"]), st.session_state[f"w{idx}_def_ntr"]),
        spatk=natured(int(st.session_state[f"w{idx}_spatk"]), st.session_state[f"w{idx}_spatk_ntr"]),
        spdef=natured(int(st.session_state[f"w{idx}_spdef"]), st.session_state[f"w{idx}_spdef_ntr"]),
        spe=natured(int(st.session_state[f"w{idx}_spe"]), st.session_state[f"w{idx}_spe_ntr"]),
        moveset=good, rng=random.Random(),
        ability=st.session_state[f"w{idx}_ability"].strip().lower().replace(" ", "-").replace("_", "-") or "none",
        held_item=st.session_state[f"w{idx}_held_item"],
        inventory=dict(inventory),
        ai_knowledge=kb_map.get(st.session_state["w_ai_knowledge"], "unknown"),
    )
    players[name] = player
    
    def _local_prog(done, total):
        global runs_completed
        prog.progress(min((runs_completed + done) / total_runs, 1.0), text=f"Simulating {name}… run {done:,} / {total:,}")

    res = run_simulation(player, n_seeds=st.session_state["n_seeds"], progress_callback=_local_prog)
    sim_results[name] = res
    runs_completed += st.session_state["n_seeds"]

prog.progress(1.0, text=f"Done!")

st.markdown('<div class="section-header">🏆 Simulation Results</div>', unsafe_allow_html=True)

# Comparison Cards
r_cols = st.columns(len(sim_results))
colors = ["#34d399", "#60a5fa", "#f472b6", "#fbbf24"]
for i, (name, res) in enumerate(sim_results.items()):
    with r_cols[i]:
        c = colors[i % len(colors)]
        wr = res.win_rate * 100
        st.markdown(f'<div class="metric-card" style="border-top:3px solid {c};">'
                    f'<div style="font-weight:900;font-size:1.4rem;color:#e2e8f0;margin-bottom:8px;">{name}</div>'
                    f'<div class="metric-label">Win Rate</div>'
                    f'<div class="metric-value" style="color:{c};">{wr:.1f}%</div>'
                    f'<div class="metric-ci">95% CI: {res.ci_low*100:.1f}%–{res.ci_high*100:.1f}%</div></div>',
                    unsafe_allow_html=True)
                    
# Charts
ch1, ch2 = st.columns([1, 1])

with ch1:
    st.markdown('<div class="section-header">📈 Survival Funnel Chart</div>', unsafe_allow_html=True)
    fig_funnel = go.Figure()
    from data.trainers import TRAINER_NAMES
    for i, (name, res) in enumerate(sim_results.items()):
        survivals = [res.trainer_survival.get(t, 0)*100 for t in TRAINER_NAMES]
        fig_funnel.add_trace(go.Scatter(x=TRAINER_NAMES, y=survivals, mode='lines+markers', name=name,
                                        line=dict(color=colors[i%len(colors)], width=3)))
    fig_funnel.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             yaxis=dict(title="Survival %", range=[0,105], gridcolor="#1a2840", color="#64748b"),
                             xaxis=dict(color="#64748b", showgrid=False),
                             margin=dict(l=10,r=10,t=10,b=10), height=400,
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_funnel, use_container_width=True)

with ch2:
    st.markdown('<div class="section-header">⚠️ Loss Rate at Trainer</div>', unsafe_allow_html=True)
    fig_loss = go.Figure()
    for i, (name, res) in enumerate(sim_results.items()):
        loss_rates = [res.trainer_loss_rate.get(t, 0)*100 for t in TRAINER_NAMES]
        fig_loss.add_trace(go.Bar(x=TRAINER_NAMES, y=loss_rates, name=name, marker_color=colors[i%len(colors)]))
    fig_loss.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", barmode='group',
                           yaxis=dict(title="Loss %", gridcolor="#1a2840", color="#64748b"),
                           xaxis=dict(color="#64748b"), margin=dict(l=10,r=10,t=10,b=10), height=400,
                           legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_loss, use_container_width=True)
