from dataclasses import dataclass
from typing import Optional
from enum import Enum


class Decade(str, Enum):
    SIXTIES = "1960s"
    SEVENTIES = "1970s"
    EIGHTIES = "1980s"
    NINETIES = "1990s"
    TWO_THOUSANDS = "2000s"
    TWENTY_TENS = "2010s"
    TWENTY_TWENTIES = "2020s"


CATEGORY_WEIGHTS: dict[str, float] = {
    "scoring": 0.25,
    "playmaking": 0.15,
    "rebounding": 0.15,
    "defense": 0.25,
    "efficiency": 0.15,
    "athleticism": 0.05,
}

CATEGORIES = list(CATEGORY_WEIGHTS.keys())


@dataclass
class PlayerStats:
    scoring: int      # Shot creation, volume, shot quality relative to era
    playmaking: int   # Assists, vision, ball handling, half-court execution
    rebounding: int   # Boards, positioning, box-out
    defense: int      # On-ball, help, blocks, steals, IQ
    efficiency: int   # TS%, FT%, turnovers, shot selection
    athleticism: int  # Physical tools, speed, durability

    def as_dict(self) -> dict[str, int]:
        return {c: getattr(self, c) for c in CATEGORIES}

    @property
    def weighted_overall(self) -> float:
        return sum(getattr(self, c) * w for c, w in CATEGORY_WEIGHTS.items())


@dataclass
class Player:
    name: str
    teams: list[str]       # Historical team names this player appeared for
    decades: list[Decade]  # Decades active (peak years)
    stats: PlayerStats
    bio: str = ""


@dataclass
class GameSlot:
    team: str
    decade: Decade
    player: Optional[Player] = None
    used_team_skip: bool = False
    used_decade_skip: bool = False

    def is_filled(self) -> bool:
        return self.player is not None

    def player_eligible(self, player: Player) -> bool:
        team_ok = self.used_team_skip or self.team in player.teams
        decade_ok = self.used_decade_skip or self.decade in player.decades
        return team_ok and decade_ok


@dataclass
class SimResult:
    wins: int
    losses: int
    grade: str
    team_stats: dict[str, float]   # Category avg across lineup
    strengths: list[str]           # Top 2 category labels
    weaknesses: list[str]          # Bottom 2 category labels with context
    gate_category: Optional[str]   # Which stat triggered the Wilt cap
    gate_multiplier: float         # How much it penalised the ceiling
    base_rating: float
    effective_rating: float

    @property
    def record_str(self) -> str:
        return f"{self.wins}-{self.losses}"
