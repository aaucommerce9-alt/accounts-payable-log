"""
82-0: Can you build the all-time lineup that goes undefeated?

Phases implemented:
  Phase 1 ✅  Data schema + 31-player seed pool
  Phase 2 ✅  Sim engine + calibrated win curve + Wilt-effect gate
  Phase 3 🔜  Game loop UI (slot machine, draft, skips)
  Phase 4 🔜  Result screen (record, grade, strengths, weakness)
  Phase 5 🔜  Full player pool
  Phase 6 🔜  HoopIQ mode (stats hidden), social layer
"""

import streamlit as st
from src.simulator import simulate
from src.players import PLAYERS, get_player, players_for_slot
from src.game import new_game, draft_player, use_team_skip, use_decade_skip
from src.schema import Decade

st.set_page_config(page_title="82-0", page_icon="🏀", layout="centered")

st.title("🏀 82-0")
st.caption("Build the all-time lineup. Go undefeated.")

# ── Debug / dev mode: quick sim tester ───────────────────────────────────────

with st.expander("⚙️ Dev: Quick Sim Tester", expanded=True):
    st.write("Pick 5 players to see their simulated record.")
    player_names = [p.name for p in PLAYERS]

    picks = []
    cols = st.columns(5)
    for i, col in enumerate(cols):
        with col:
            pick = st.selectbox(
                f"Slot {i+1}",
                options=["—"] + player_names,
                key=f"pick_{i}",
            )
            picks.append(pick)

    if all(p != "—" for p in picks) and len(set(picks)) == 5:
        lineup = [get_player(n) for n in picks]
        result = simulate(lineup)

        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("Record", result.record_str)
        c2.metric("Grade", result.grade)
        c3.metric("Gate", result.gate_category or "none")

        st.write("**Team stats:**")
        st.bar_chart(result.team_stats)

        st.write(f"**Strengths:** {' · '.join(result.strengths)}")
        st.write(f"**Weaknesses:** {' · '.join(result.weaknesses)}")

        if result.gate_category:
            st.warning(
                f"🔒 **{result.gate_category.capitalize()}** is your gate "
                f"(×{result.gate_multiplier:.2f} cap on wins). "
                "That's the Wilt effect."
            )
    elif len(set(picks)) < 5 and all(p != "—" for p in picks):
        st.error("Each slot must be a different player.")

st.markdown("---")
st.info("Full game loop (slot machine → draft → result screen) coming in Phase 3.")
