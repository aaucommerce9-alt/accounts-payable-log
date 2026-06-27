"""
Simulation engine for 82-0.

Two-part gate system:
  1. Team-average gate: per-category thresholds (categories like rebounding
     use lower floors since guards don't rebound).
  2. Individual floor gate: only for defense and efficiency — the two stats
     that CANNOT be hidden by teammates (bad FT% gets fouled on purpose,
     bad defenders get hunted every possession).

Gate multiplier is applied to wins, not to the pre-curve rating.
This keeps the effect proportional regardless of where on the curve the
team lands.

Win curve: sigmoid centered at 65 (an average team sits ~41 wins).
82-0 requires an effective rating near 95+ with no gate penalty.
"""

import math
from src.schema import CATEGORIES, CATEGORY_WEIGHTS, Player, SimResult


# ── Per-category gate thresholds ──────────────────────────────────────────────
# (minor, liability, fatal, disqualifying) — team averages
# Lower floors on rebounding/playmaking because role players acceptably skew
# those for the whole team; defense/efficiency have higher floors because
# individual weaknesses there ARE directly exploited.

_CAT_THRESHOLDS: dict[str, tuple[int, int, int, int]] = {
    "scoring":     (82, 72, 62, 52),
    "playmaking":  (75, 65, 55, 45),
    "rebounding":  (70, 58, 48, 38),
    "defense":     (84, 76, 66, 55),
    "efficiency":  (85, 78, 68, 55),
    "athleticism": (78, 68, 58, 45),
}

# Multipliers indexed by gate level 0-4 (none, minor, liability, fatal, disq)
_GATE_MULTS = (1.00, 0.96, 0.86, 0.74, 0.58)

# Individual floor — only for stats that can't be covered by teammates
_INDIVIDUAL_FLOORS = {"defense": 68, "efficiency": 72}
_FLOOR_PENALTY_RATE = 0.012  # 1.2% per point below floor, capped at 0.55


# ── Gate helpers ──────────────────────────────────────────────────────────────

def _category_gate_mult(score: float, cat: str) -> float:
    minor, liability, fatal, disq = _CAT_THRESHOLDS[cat]
    if score >= minor:   return _GATE_MULTS[0]
    if score >= liability: return _GATE_MULTS[1]
    if score >= fatal:   return _GATE_MULTS[2]
    if score >= disq:    return _GATE_MULTS[3]
    return _GATE_MULTS[4]


def _team_gate(tstats: dict[str, float]) -> tuple[float, str | None]:
    """Worst gate across all team average categories."""
    worst_mult, worst_cat = 1.0, None
    for cat in CATEGORIES:
        m = _category_gate_mult(tstats[cat], cat)
        if m < worst_mult:
            worst_mult, worst_cat = m, cat
    return worst_mult, worst_cat


def _individual_gate(lineup: list[Player]) -> tuple[float, str | None]:
    """Additional penalty when any single player is below the exploitability floor."""
    worst_mult, worst_cat = 1.0, None
    for cat, floor in _INDIVIDUAL_FLOORS.items():
        min_val = min(getattr(p.stats, cat) for p in lineup)
        if min_val < floor:
            deficit = floor - min_val
            mult = max(0.55, 1.0 - deficit * _FLOOR_PENALTY_RATE)
            if mult < worst_mult:
                worst_mult, worst_cat = mult, cat
    return worst_mult, worst_cat


# ── Win curve ─────────────────────────────────────────────────────────────────

def _win_curve(base_rating: float) -> float:
    """
    Sigmoid with center=65, k=0.15.
    ~41 wins at rating 65, ~79 wins at ~87.5, ~82 wins near ~98+.
    Gate is applied multiplicatively to the output, keeping effect proportional.
    """
    return 82.0 / (1.0 + math.exp(-0.15 * (base_rating - 65.0)))


# ── Grade ─────────────────────────────────────────────────────────────────────

def _grade(wins: int) -> str:
    if wins == 82: return "S+"
    if wins >= 78: return "S"
    if wins >= 73: return "A+"
    if wins >= 68: return "A"
    if wins >= 63: return "B+"
    if wins >= 57: return "B"
    if wins >= 50: return "C"
    if wins >= 40: return "D"
    return "F"


# ── Team stat aggregation ─────────────────────────────────────────────────────

def team_stats(lineup: list[Player]) -> dict[str, float]:
    n = len(lineup)
    return {cat: sum(getattr(p.stats, cat) for p in lineup) / n for cat in CATEGORIES}


# ── Main simulate ─────────────────────────────────────────────────────────────

def simulate(lineup: list[Player]) -> SimResult:
    if len(lineup) != 5:
        raise ValueError(f"Need exactly 5 players, got {len(lineup)}")

    tstats = team_stats(lineup)
    base_rating = sum(tstats[cat] * CATEGORY_WEIGHTS[cat] for cat in CATEGORIES)

    # Combined gate: worst of team-average gate and individual-floor gate
    team_mult, team_gate_cat = _team_gate(tstats)
    ind_mult, ind_gate_cat = _individual_gate(lineup)

    if team_mult <= ind_mult:
        gate_mult = team_mult
        gate_cat = team_gate_cat
    else:
        gate_mult = ind_mult
        gate_cat = ind_gate_cat

    wins_raw = _win_curve(base_rating)
    wins = round(min(82, max(1, wins_raw * gate_mult)))
    losses = 82 - wins

    sorted_cats = sorted(tstats.items(), key=lambda x: x[1], reverse=True)
    strengths = [f"{c.capitalize()} ({s:.1f})" for c, s in sorted_cats[:2]]
    weaknesses = []
    for c, s in sorted_cats[-2:]:
        label = f"{c.capitalize()} ({s:.1f})"
        if c == gate_cat and gate_mult < 1.0:
            label += " ← gate"
        weaknesses.append(label)

    return SimResult(
        wins=wins,
        losses=losses,
        grade=_grade(wins),
        team_stats=tstats,
        strengths=strengths,
        weaknesses=weaknesses,
        gate_category=gate_cat if gate_mult < 1.0 else None,
        gate_multiplier=round(gate_mult, 4),
        base_rating=round(base_rating, 2),
        effective_rating=round(base_rating * gate_mult, 2),
    )
