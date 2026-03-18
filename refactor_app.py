import sys

with open("app.py", "r", encoding="utf-8") as f:
    text = f.read()

split_marker = "# ── Session state defaults ────────────────────────────────────────────────────"
idx = text.find(split_marker)
upper_code = text[:idx]

new_ui_code = """# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "w_potions": 0, "w_super_potions": 0, "w_hyper_potions": 0, 
    "w_max_potions": 0, "w_full_heals": 0, "w_full_restores": 0,
    "w_ai_knowledge": "Unknown (50% Chance of 1 vs 2 Abilities)",
    "n_seeds": 5000,
}
for i in range(1, 5):
    DEFAULTS[f"w{i}_name"] = "Kingler" if i == 1 else ""
    DEFAULTS[f"w{i}_level"] = 9 if i == 1 else 9
    DEFAULTS[f"w{i}_type1"] = "water" if i == 1 else "normal"
    DEFAULTS[f"w{i}_type2"] = "—"
    DEFAULTS[f"w{i}_bst"] = 0
    DEFAULTS[f"w{i}_hp"] = 44 if i == 1 else 45
    DEFAULTS[f"w{i}_atk"] = 10 if i == 1 else 45
    DEFAULTS[f"w{i}_def"] = 16 if i == 1 else 45
    DEFAULTS[f"w{i}_spatk"] = 29 if i == 1 else 45
    DEFAULTS[f"w{i}_spdef"] = 26 if i == 1 else 45
    DEFAULTS[f"w{i}_spe"] = 9 if i == 1 else 45
    for s in ["hp", "atk", "def", "spatk", "spdef", "spe"]:
        DEFAULTS[f"w{i}_{s}_ntr"] = "·"
    DEFAULTS[f"w{i}_move1"] = "screech" if i == 1 else ""
    DEFAULTS[f"w{i}_move2"] = "flame-wheel" if i == 1 else ""
    DEFAULTS[f"w{i}_move3"] = "fire-blast" if i == 1 else ""
    DEFAULTS[f"w{i}_move4"] = "mirror-coat" if i == 1 else ""
    DEFAULTS[f"w{i}_ability"] = "pressure" if i == 1 else "none"
    DEFAULTS[f"w{i}_held_item"] = "none"
    DEFAULTS[f"_w{i}_prev_name"] = ""
    DEFAULTS[f"_w{i}_prev_bst"] = 0
    DEFAULTS[f"_w{i}_af_msg"] = ""

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def render_mon_tab(idx):
    c1, c2 = st.columns([2,1])
    with c1: st.text_input("Name", key=f"w{idx}_name")
    with c2: st.number_input("Level", 1, 100, key=f"w{idx}_level")

    # autofill
    cur_name = st.session_state[f"w{idx}_name"].lower().strip().replace(" ","-").replace("_","-")
    prev_name_key = f"_w{idx}_prev_name"
    if cur_name and cur_name != st.session_state[prev_name_key]:
        pj = lookup_pokemon(cur_name)
        if pj:
            from data.moves import load_move_pool
            pool_names = {m.name for m in load_move_pool()}
            pd = parse_pkmn(pj, int(st.session_state[f"w{idx}_level"]))
            if pd:
                types = pd["types"]
                st.session_state[f"w{idx}_type1"] = types[0]
                st.session_state[f"w{idx}_type2"] = types[1] if len(types) > 1 else "—"
                st.session_state[f"w{idx}_bst"]   = pd["bst"]
                st.session_state[f"w{idx}_hp"]    = pd["hp"]
                st.session_state[f"w{idx}_atk"]   = pd["atk"]
                st.session_state[f"w{idx}_def"]   = pd["def_"]
                st.session_state[f"w{idx}_spatk"] = pd["spatk"]
                st.session_state[f"w{idx}_spdef"] = pd["spdef"]
                st.session_state[f"w{idx}_spe"]   = pd["spe"]
                if pd["abilities"]: st.session_state[f"w{idx}_ability"] = pd["abilities"][0]
                moves = autofill_moves(pd["lv_moves"], int(st.session_state[f"w{idx}_level"]), pool_names)
                for i, key in enumerate(["move1","move2","move3","move4"]):
                    st.session_state[f"w{idx}_{key}"] = moves[i] if i < len(moves) else ""
                actual_name = pj.get("name","")
                st.session_state[prev_name_key] = actual_name
                st.session_state[f"_w{idx}_prev_bst"] = pd["bst"]
                st.session_state[f"_w{idx}_af_msg"] = f"✓ Autofilled from {actual_name.title()}"
                st.rerun()
        st.session_state[prev_name_key] = cur_name

    msg_key = f"_w{idx}_af_msg"
    if st.session_state[msg_key]:
        st.markdown(f'<div class="autofill-banner">{st.session_state[msg_key]}</div>', unsafe_allow_html=True)
        st.session_state[msg_key] = ""

    ct1, ct2 = st.columns(2)
    t1 = st.session_state[f"w{idx}_type1"]
    t1_idx = ALL_TYPES.index(t1) if t1 in ALL_TYPES else 0
    t2 = st.session_state[f"w{idx}_type2"]
    t2_opts = ["—"] + ALL_TYPES
    t2_idx  = t2_opts.index(t2) if t2 in t2_opts else 0
    with ct1: st.selectbox("Type 1", ALL_TYPES, index=t1_idx, key=f"w{idx}_type1")
    with ct2: st.selectbox("Type 2 (opt)", t2_opts, index=t2_idx, key=f"w{idx}_type2")

    st.markdown('<div class="section-header">Stats &amp; BST</div>', unsafe_allow_html=True)
    lv = int(st.session_state[f"w{idx}_level"])
    raw_ranges = [
        compatible_base_range_hp(int(st.session_state[f"w{idx}_hp"]), lv),
        compatible_base_range_stat(int(st.session_state[f"w{idx}_atk"]), lv),
        compatible_base_range_stat(int(st.session_state[f"w{idx}_def"]), lv),
        compatible_base_range_stat(int(st.session_state[f"w{idx}_spatk"]), lv),
        compatible_base_range_stat(int(st.session_state[f"w{idx}_spdef"]), lv),
        compatible_base_range_stat(int(st.session_state[f"w{idx}_spe"]), lv),
    ]
    range_keys = ["hp", "atk", "def", "spatk", "spdef", "spe"]
    known_bst = int(st.session_state[f"w{idx}_bst"] or 0)
    pt_estimates = bst_constrained_estimate(raw_ranges, known_bst) if known_bst > 0 else [round((lo + hi) / 2) for lo, hi in raw_ranges]
    rev_bases = dict(zip(range_keys, pt_estimates))
    rev_ranges = dict(zip(range_keys, raw_ranges))

    st.number_input("BST", 0, 780, key=f"w{idx}_bst")
    stat_pairs = [("hp","HP"), ("atk","Atk"), ("def","Def"), ("spatk","SpAtk"), ("spdef","SpDef"), ("spe","Spe")]
    for s_key, label in stat_pairs:
        base_pt, (lo, hi) = rev_bases[s_key], rev_ranges[s_key]
        cs, cv, cn = st.columns([2, 3, 2])
        with cs: st.markdown(f'<div style="padding-top:24px;line-height:1.3;"><span style="color:#94a3b8;font-size:.75rem;">{label}</span><br><span style="color:#34d399;font-weight:700;font-size:.78rem;">~{base_pt}</span><span style="color:#475569;font-size:.65rem;"> [{lo}–{hi}]</span></div>', unsafe_allow_html=True)
        with cv: st.number_input(label, 1, 999, key=f"w{idx}_{s_key}", label_visibility="collapsed")
        with cn: st.select_slider(f"Nature {label}", options=NATURE_OPTS, key=f"w{idx}_{s_key}_ntr", label_visibility="collapsed")

    st.markdown('<div class="section-header">Moves</div>', unsafe_allow_html=True)
    st.text_input("Move 1", key=f"w{idx}_move1")
    st.text_input("Move 2", key=f"w{idx}_move2")
    st.text_input("Move 3", key=f"w{idx}_move3")
    st.text_input("Move 4", key=f"w{idx}_move4")

    st.markdown('<div class="section-header">Ability & Item</div>', unsafe_allow_html=True)
    st.text_input("Ability", key=f"w{idx}_ability")
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

    st.markdown("## ⚙️ Options")
    st.radio("AI Knowledge of My Ability", 
        ["Unknown (50% Chance of 1 vs 2 Abilities)", "1 Ability (AI knows immediately)", "2 Abilities (AI doesn't know until triggered)"],
        key="w_ai_knowledge")
    st.select_slider("Seeds", options=[500,1000,2000,5000,10000,25000], key="n_seeds")
    run_btn = st.button("⚡ Run Simulation", use_container_width=True)

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown(\"\"\"<div class="hero-banner">
  <p class="hero-title">Viridian Forest Simulator</p>
  <p class="hero-sub">Gen 3 IronMon · Multi-Compare · Monte Carlo</p>
</div>\"\"\", unsafe_allow_html=True)

if not run_btn:
    st.markdown(\"\"\"
    <div style="text-align:center;padding:60px 20px;">
      <div style="font-size:64px;margin-bottom:16px;">🌿</div>
      <p style="font-size:1.1rem;color:#64748b;margin:0;">
        Configure up to 4 Pokémon in the sidebar tabs to compare them directly!
      </p>
    </div>\"\"\", unsafe_allow_html=True)
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
"""

with open("app.py", "w", encoding="utf-8") as f:
    f.write(upper_code + new_ui_code)
print("Updated app.py successfully.")
