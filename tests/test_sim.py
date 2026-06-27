"""
Sim engine calibration tests.

Expected behaviour:
  Jordan/LeBron/Duncan/Kareem/Magic     → 78-80 wins (S)
  Wilt+Elite (gated by efficiency avg)  → 73-76 wins (A/A+)
  Nash/Maravich/AI/Luka/McAdoo bad D   → ≤ 65 wins (gated by defense)
  Solid but not elite five              → 55-72 wins

Run with: python -m pytest tests/test_sim.py -v
"""

import pytest
from src.players import get_player
from src.simulator import (
    _category_gate_mult,
    simulate,
    team_stats,
)
from src.schema import CATEGORIES


def lineup(*names: str):
    return [get_player(n) for n in names]


# ── Category gate unit tests ──────────────────────────────────────────────────

def test_efficiency_no_penalty_above_85():
    assert _category_gate_mult(88, "efficiency") == 1.00

def test_efficiency_minor_below_85():
    assert _category_gate_mult(84, "efficiency") == 0.96

def test_defense_fatal_below_66():
    assert _category_gate_mult(65, "defense") == 0.74

def test_rebounding_liability_below_70():
    assert _category_gate_mult(69, "rebounding") == 0.96

def test_rebounding_fatal_below_48():
    # Rebounding fatal threshold is 48
    assert _category_gate_mult(45, "rebounding") == 0.74


# ── All-time dream lineup ─────────────────────────────────────────────────────

def test_dream_lineup_approaches_82_0():
    """Jordan + LeBron + Duncan + Kareem + Magic — should hit S grade (78+ wins)."""
    result = simulate(lineup(
        "Michael Jordan", "LeBron James", "Tim Duncan",
        "Kareem Abdul-Jabbar", "Magic Johnson",
    ))
    print(f"\nDream: {result.record_str} ({result.grade}) | "
          f"base={result.base_rating} gate={result.gate_multiplier} "
          f"gate_cat={result.gate_category}")
    assert result.wins >= 78, f"Expected 78+ wins, got {result.wins}"
    assert result.grade in ("S+", "S"), f"Expected S/S+, got {result.grade}"


# ── Wilt effect (efficiency gate) ────────────────────────────────────────────

def test_wilt_lineup_is_gated_by_efficiency():
    """
    Wilt's efficiency (70) pulls team efficiency average below 85 threshold.
    Gate should fire, capping the record below the dream-lineup ceiling.
    """
    result = simulate(lineup(
        "Wilt Chamberlain", "Michael Jordan", "LeBron James",
        "Oscar Robertson", "Bill Russell",
    ))
    print(f"\nWilt: {result.record_str} ({result.grade}) | "
          f"gate_cat={result.gate_category} mult={result.gate_multiplier}")
    assert result.gate_category is not None, "Wilt's efficiency should trigger a gate"
    assert result.wins <= 77, f"Gate should cap Wilt lineup at 77 wins, got {result.wins}"


# ── Defense-poor lineup ───────────────────────────────────────────────────────

def test_bad_defense_lineup_is_gated_by_defense():
    """
    Maravich (def=62) / Nash (def=58) / AI (def=75) / Luka (def=62) / McAdoo (def=72).
    Team defense average should be the fatal gate, identified as 'defense'.
    """
    result = simulate(lineup(
        "Pete Maravich", "Steve Nash", "Allen Iverson",
        "Luka Doncic", "Bob McAdoo",
    ))
    print(f"\nBad-D: {result.record_str} ({result.grade}) | "
          f"gate_cat={result.gate_category} mult={result.gate_multiplier}")
    assert result.gate_category == "defense", \
        f"Expected defense to be gate, got {result.gate_category}"
    assert result.wins <= 65, f"Bad-D lineup should be capped at 65, got {result.wins}"


# ── Balanced solid lineup ─────────────────────────────────────────────────────

def test_solid_lineup_lands_in_b_range():
    """A decent but not elite lineup should land 55-72 wins."""
    result = simulate(lineup(
        "Walt Frazier", "Charles Barkley", "Bob McAdoo",
        "David Robinson", "John Stockton",
    ))
    print(f"\nSolid: {result.record_str} ({result.grade})")
    assert 55 <= result.wins <= 72, f"Expected 55-72 wins, got {result.wins}"


# ── Modern elite lineup ───────────────────────────────────────────────────────

def test_modern_all_around_lineup():
    """LeBron / Curry / Durant / Jokic / Kawhi — well-rounded modern roster."""
    result = simulate(lineup(
        "LeBron James", "Stephen Curry", "Kevin Durant",
        "Nikola Jokic", "Kawhi Leonard",
    ))
    print(f"\nModern: {result.record_str} ({result.grade}) | "
          f"strengths={result.strengths}")
    assert result.wins >= 70, f"Expected 70+ wins, got {result.wins}"


# ── Result structure sanity ───────────────────────────────────────────────────

def test_result_structure_is_valid():
    result = simulate(lineup(
        "LeBron James", "Stephen Curry", "Kevin Durant",
        "Nikola Jokic", "Kawhi Leonard",
    ))
    assert 0 <= result.wins <= 82
    assert result.wins + result.losses == 82
    assert result.grade in ("S+", "S", "A+", "A", "B+", "B", "C", "D", "F")
    assert len(result.strengths) == 2
    assert len(result.weaknesses) == 2
    assert all(c in result.team_stats for c in CATEGORIES)


def test_team_stats_averages_correctly():
    players = lineup("Michael Jordan", "LeBron James")
    tstats = team_stats(players)
    assert abs(tstats["scoring"] - (98 + 94) / 2) < 0.01


def test_wrong_lineup_size_raises():
    with pytest.raises(ValueError):
        simulate(lineup("LeBron James", "Stephen Curry"))
