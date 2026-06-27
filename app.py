import random
import streamlit as st
from src.players import PLAYERS, players_for_slot
from src.simulator import simulate
from src.schema import Decade, Player

st.set_page_config(page_title="82-0", page_icon="🏀", layout="centered")

st.markdown("""
<style>
/* slot cards */
.slot-box {
    background: #1a1a2e;
    border: 2px solid #333;
    border-radius: 10px;
    padding: 10px 6px;
    text-align: center;
    min-height: 72px;
    font-size: 0.82rem;
    line-height: 1.4;
}
.slot-active  { border-color: #f4a261 !important; box-shadow: 0 0 14px rgba(244,162,97,.35); }
.slot-filled  { border-color: #2d6a4f !important; }
.slot-empty   { border-color: #333; color: #888; }

/* player cards */
.p-card {
    background: #1a1a2e;
    border: 1.5px solid #333;
    border-radius: 10px;
    padding: 12px 10px;
    margin-bottom: 6px;
}
.p-card:hover { border-color: #f4a261; }

/* stat pill */
.stat { font-size: 0.78rem; }
.s90  { color: #FFD700; font-weight: 700; }
.s80  { color: #FFFFFF; font-weight: 600; }
.s70  { color: #AAAAAA; }
.slow { color: #FF6B6B; }

/* big result */
.result-box {
    background: #1a1a2e;
    border: 3px solid #f4a261;
    border-radius: 16px;
    text-align: center;
    padding: 2rem 1rem;
    margin: 1rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

ALL_DECADES = list(Decade)


@st.cache_data
def valid_combos() -> list[tuple[str, Decade]]:
    seen: set[tuple[str, str]] = set()
    out = []
    for p in PLAYERS:
        for team in p.teams:
            for decade in p.decades:
                key = (team, decade.value)
                if key not in seen:
                    seen.add(key)
                    out.append((team, decade))
    return out


VALID_COMBOS = valid_combos()

GRADE_COLOUR = {
    "S+": "#FFD700", "S": "#FFD700",
    "A+": "#f4a261", "A": "#f4a261",
    "B+": "#FFFFFF", "B": "#FFFFFF",
    "C": "#AAAAAA", "D": "#888888", "F": "#FF6B6B",
}


def sc(v: int) -> str:
    """Return CSS class for a stat value."""
    if v >= 90: return "s90"
    if v >= 80: return "s80"
    if v >= 70: return "s70"
    return "slow"


def stat_line(stats) -> str:
    """Build compact coloured stat HTML for a player."""
    rows = [
        ("SCR", stats.scoring), ("DEF", stats.defense),
        ("EFF", stats.efficiency), ("PLY", stats.playmaking),
        ("REB", stats.rebounding), ("ATH", stats.athleticism),
    ]
    parts = [
        f'<span class="stat {sc(v)}"><b>{lbl}</b>&nbsp;{v}</span>'
        for lbl, v in rows
    ]
    return (
        "  ".join(parts[:3]) + "<br>"
        + "  ".join(parts[3:])
    )


def eligible(slot_idx: int) -> list[Player]:
    s = st.session_state
    team, decade = s.slots[slot_idx]
    skip_team   = s.skip_team[slot_idx]
    skip_decade = s.skip_decade[slot_idx]

    if skip_team and skip_decade:
        pool = PLAYERS
    elif skip_team:
        pool = [p for p in PLAYERS if decade in p.decades]
    elif skip_decade:
        pool = [p for p in PLAYERS if team in p.teams]
    else:
        pool = players_for_slot(team, decade)

    already = {p.name for p in s.picks if p}
    return [p for p in pool if p.name not in already]


# ── Game init ─────────────────────────────────────────────────────────────────

def start_game(mode: str) -> None:
    excluded = random.sample(ALL_DECADES, 2)
    active   = [d for d in ALL_DECADES if d not in excluded]
    pool     = [(t, d) for t, d in VALID_COMBOS if d in active]
    slots    = random.choices(pool, k=5)

    st.session_state.update({
        "phase":             "draft",
        "mode":              mode,
        "slots":             slots,
        "picks":             [None] * 5,
        "current":           0,
        "team_skips":        1,
        "decade_skips":      1,
        "skip_team":         [False] * 5,
        "skip_decade":       [False] * 5,
        "excluded_decades":  excluded,
    })


# ── Slot bar (top of draft screen) ───────────────────────────────────────────

def render_slot_bar() -> None:
    s = st.session_state
    cols = st.columns(5)
    for i, col in enumerate(cols):
        team, decade = s.slots[i]
        pick = s.picks[i]
        if pick:
            css  = "slot-box slot-filled"
            body = f"<b style='color:#56cf8d'>{pick.name.split()[-1]}</b><br><small>{team}<br>{decade.value}</small>"
        elif i == s.current:
            css  = "slot-box slot-active"
            body = f"<b style='color:#f4a261'>ROUND {i+1}</b><br><small>{team}<br>{decade.value}</small>"
        else:
            css  = "slot-box slot-empty"
            body = f"<small>{team}<br>{decade.value}</small>"
        col.markdown(f'<div class="{css}">{body}</div>', unsafe_allow_html=True)


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_home() -> None:
    st.markdown("# 🏀 82-0")
    st.markdown("#### Can you build the lineup that goes undefeated?")
    st.markdown("""
Each round, a **random team + decade** is assigned by the slot machine.
Pick a player who played for that team in that era.
Fill all 5 slots, then simulate the season.

> You get **1 team skip** + **1 decade skip**. Use them wisely.
> One weak link can gate your whole record — that's the **Wilt effect**.
> 82-0 is rare. Go build it.
    """)
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🏆  Classic Mode", use_container_width=True, type="primary"):
            start_game("classic")
            st.rerun()
    with c2:
        if st.button("🧠  HoopIQ Mode  *(stats hidden)*", use_container_width=True):
            start_game("hoopiq")
            st.rerun()


def page_draft() -> None:
    s   = st.session_state
    idx = s.current
    team, decade = s.slots[idx]

    render_slot_bar()
    st.markdown("---")

    # Big slot reveal
    st.markdown(f"### Round {idx + 1} of 5")
    st.markdown(
        f"<h2 style='letter-spacing:2px; color:#f4a261'>"
        f"{team.upper()}&nbsp; × &nbsp;{decade.value}</h2>",
        unsafe_allow_html=True,
    )

    exc_str = " · ".join(d.value for d in s.excluded_decades)
    st.caption(f"Excluded this game: {exc_str}")

    # Skip buttons
    scol1, scol2, _ = st.columns([1, 1, 2])
    with scol1:
        if not s.skip_team[idx]:
            disabled = s.team_skips < 1
            label    = f"Skip Team  ({s.team_skips} left)" if not disabled else "No team skips left"
            if st.button(label, disabled=disabled, key="btn_skip_team"):
                s.skip_team[idx]  = True
                s.team_skips     -= 1
                st.rerun()
        else:
            st.markdown("*Team skipped — any team OK*")
    with scol2:
        if not s.skip_decade[idx]:
            disabled = s.decade_skips < 1
            label    = f"Skip Decade  ({s.decade_skips} left)" if not disabled else "No decade skips left"
            if st.button(label, disabled=disabled, key="btn_skip_decade"):
                s.skip_decade[idx]  = True
                s.decade_skips     -= 1
                st.rerun()
        else:
            st.markdown("*Decade skipped — any era OK*")

    st.markdown("---")

    players = eligible(idx)

    if not players:
        st.error(
            "No players match this slot with the current constraints. "
            "Use a skip token to open it up."
        )
        return

    st.markdown(f"**{len(players)} eligible player{'s' if len(players) != 1 else ''}** — pick one:")

    # Player grid
    n_cols = 3
    for row_start in range(0, len(players), n_cols):
        row = players[row_start : row_start + n_cols]
        cols = st.columns(n_cols)
        for j, player in enumerate(row):
            with cols[j]:
                if s.mode == "classic":
                    stats_html = stat_line(player.stats)
                    st.markdown(
                        f'<div class="p-card">'
                        f"<b>{player.name}</b><br>"
                        f"<small style='color:#888'>"
                        f"{', '.join(player.teams[:2])} &nbsp;·&nbsp; "
                        f"{' / '.join(d.value for d in player.decades[:2])}"
                        f"</small><br><br>"
                        f"{stats_html}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    # HoopIQ — no stats
                    st.markdown(
                        f'<div class="p-card">'
                        f"<b>{player.name}</b><br>"
                        f"<small style='color:#888'>"
                        f"{', '.join(player.teams[:2])}"
                        f"</small>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                if st.button("Draft →", key=f"draft_{idx}_{player.name}", use_container_width=True):
                    s.picks[idx] = player
                    s.current   += 1
                    if s.current >= 5:
                        s.phase = "result"
                    st.rerun()


def page_result() -> None:
    s    = st.session_state
    picks = [p for p in s.picks if p]
    result = simulate(picks)

    grade_col = GRADE_COLOUR.get(result.grade, "#FFFFFF")

    # Big record
    st.markdown(
        f'<div class="result-box">'
        f'<p style="font-size:0.9rem;color:#888;margin:0">FINAL RECORD</p>'
        f'<h1 style="font-size:4.5rem;margin:0.2rem 0;letter-spacing:4px">'
        f'{result.record_str}</h1>'
        f'<span style="font-size:2rem;color:{grade_col};font-weight:700">'
        f'{result.grade}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Lineup
    st.markdown("### Your Lineup")
    for i, (player, (team, decade)) in enumerate(zip(picks, s.slots)):
        skip_note = ""
        if s.skip_team[i]:   skip_note += " *(team skipped)*"
        if s.skip_decade[i]: skip_note += " *(decade skipped)*"
        st.markdown(f"**{i+1}.** {player.name} — {team} / {decade.value}{skip_note}")
        if s.mode == "classic":
            st.markdown(
                stat_line(player.stats) + "<br>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # Strengths / weaknesses
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**💪 Strengths**")
        for item in result.strengths:
            st.markdown(f"- {item}")
    with c2:
        st.markdown("**⚠️ Weaknesses**")
        for item in result.weaknesses:
            st.markdown(f"- {item}")

    if result.gate_category:
        st.warning(
            f"🔒 **{result.gate_category.capitalize()} gate** fired  (×{result.gate_multiplier:.2f} on wins). "
            f"One weak link capped this lineup — that's the Wilt effect."
        )
    else:
        st.success("✅ No gate — this lineup had no exploitable weakness.")

    # Team stat chart (Classic mode only)
    if s.mode == "classic":
        import pandas as pd
        st.markdown("**Team averages**")
        df = pd.DataFrame(
            list(result.team_stats.values()),
            index=[k.capitalize() for k in result.team_stats],
            columns=["Score"],
        )
        st.bar_chart(df, height=220)

    st.markdown("---")
    if st.button("🔄  Play Again", type="primary", use_container_width=True):
        s.phase = "home"
        st.rerun()


# ── Router ────────────────────────────────────────────────────────────────────

phase = st.session_state.get("phase", "home")
if   phase == "home":   page_home()
elif phase == "draft":  page_draft()
elif phase == "result": page_result()
