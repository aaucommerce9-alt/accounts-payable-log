"""Game state and slot-machine logic."""

import random
from dataclasses import dataclass, field
from typing import Literal

from src.schema import Decade, GameSlot, Player
from src.players import PLAYERS, players_for_slot


ALL_DECADES = list(Decade)

# Canonical team list — slot machine draws from this pool.
NBA_TEAMS: list[str] = [
    "Lakers", "Celtics", "Bulls", "Warriors", "Spurs", "Heat",
    "Thunder", "Knicks", "Pistons", "Suns", "Jazz", "Rockets",
    "76ers", "Nets", "Raptors", "Nuggets", "Bucks", "Clippers",
    "Cavaliers", "Magic", "Blazers", "Mavericks", "Hawks", "Braves",
    "Royals",
]

GameMode = Literal["classic", "hoopiq"]


@dataclass
class GameState:
    slots: list[GameSlot] = field(default_factory=list)
    excluded_decades: list[Decade] = field(default_factory=list)
    team_skips_remaining: int = 1
    decade_skips_remaining: int = 1
    mode: GameMode = "classic"
    current_slot: int = 0  # index of the slot being drafted

    @property
    def active_decades(self) -> list[Decade]:
        return [d for d in ALL_DECADES if d not in self.excluded_decades]

    @property
    def is_complete(self) -> bool:
        return all(s.is_filled() for s in self.slots)

    @property
    def lineup(self) -> list[Player]:
        return [s.player for s in self.slots if s.player is not None]

    def eligible_players(self, slot_index: int) -> list[Player]:
        return [p for p in PLAYERS if self.slots[slot_index].player_eligible(p)]


def new_game(mode: GameMode = "classic", seed: int | None = None) -> GameState:
    """Spin up a fresh game. Excludes 2 random decades, assigns 5 team+decade slots."""
    rng = random.Random(seed)
    excluded = rng.sample(ALL_DECADES, 2)
    active = [d for d in ALL_DECADES if d not in excluded]

    slots = [GameSlot(team=rng.choice(NBA_TEAMS), decade=rng.choice(active)) for _ in range(5)]

    return GameState(slots=slots, excluded_decades=excluded, mode=mode)


def use_team_skip(state: GameState, slot_index: int) -> GameState:
    """Mark slot so the team constraint is waived. Costs 1 team skip."""
    if state.team_skips_remaining < 1:
        raise ValueError("No team skips remaining.")
    state.slots[slot_index].used_team_skip = True
    state.team_skips_remaining -= 1
    return state


def use_decade_skip(state: GameState, slot_index: int) -> GameState:
    """Mark slot so the decade constraint is waived. Costs 1 decade skip."""
    if state.decade_skips_remaining < 1:
        raise ValueError("No decade skips remaining.")
    state.slots[slot_index].used_decade_skip = True
    state.decade_skips_remaining -= 1
    return state


def draft_player(state: GameState, slot_index: int, player: Player) -> GameState:
    slot = state.slots[slot_index]
    if not slot.player_eligible(player):
        raise ValueError(
            f"{player.name} doesn't fit slot "
            f"({slot.team} / {slot.decade.value}) — "
            "use a skip or pick someone else."
        )
    slot.player = player
    state.current_slot = slot_index + 1
    return state
