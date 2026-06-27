from src.schema import Decade, Player, PlayerStats

# ~27 seed players covering all 7 decades.
# Stats are era-adjusted 0-100 ratings — not raw counting stats.
# Wilt's efficiency (FT%, usage efficiency) is intentionally low: that's the gate.

PLAYERS: list[Player] = [

    # ── 1960s ────────────────────────────────────────────────────────────────

    Player(
        name="Wilt Chamberlain",
        teams=["Warriors", "76ers", "Lakers"],
        decades=[Decade.SIXTIES, Decade.SEVENTIES],
        stats=PlayerStats(scoring=99, playmaking=62, rebounding=100, defense=88,
                          efficiency=70, athleticism=100),
        bio="Most physically dominant player ever. FT% and shot selection are real caps — "
            "the textbook gate case.",
    ),
    Player(
        name="Bill Russell",
        teams=["Celtics"],
        decades=[Decade.SIXTIES],
        stats=PlayerStats(scoring=62, playmaking=70, rebounding=97, defense=100,
                          efficiency=80, athleticism=90),
        bio="Greatest winner. Defense and IQ are all-time, offense was intentionally minimal.",
    ),
    Player(
        name="Oscar Robertson",
        teams=["Royals", "Bucks"],
        decades=[Decade.SIXTIES, Decade.SEVENTIES],
        stats=PlayerStats(scoring=90, playmaking=96, rebounding=68, defense=82,
                          efficiency=88, athleticism=85),
        bio="Averaged a triple-double for an entire season. The original complete guard.",
    ),
    Player(
        name="Jerry West",
        teams=["Lakers"],
        decades=[Decade.SIXTIES, Decade.SEVENTIES],
        stats=PlayerStats(scoring=93, playmaking=80, rebounding=52, defense=88,
                          efficiency=87, athleticism=85),
        bio="The Logo. Two-way elite minus rebounding. Clutch before clutch was a word.",
    ),
    Player(
        name="Elgin Baylor",
        teams=["Lakers"],
        decades=[Decade.SIXTIES],
        stats=PlayerStats(scoring=94, playmaking=75, rebounding=82, defense=72,
                          efficiency=80, athleticism=95),
        bio="Invented the modern wing scorer. Injuries cut the peak short.",
    ),

    # ── 1970s ────────────────────────────────────────────────────────────────

    Player(
        name="Kareem Abdul-Jabbar",
        teams=["Bucks", "Lakers"],
        decades=[Decade.SEVENTIES, Decade.EIGHTIES],
        stats=PlayerStats(scoring=96, playmaking=60, rebounding=88, defense=95,
                          efficiency=93, athleticism=90),
        bio="All-time scorer. Skyhook was unguardable for 20 years. Zero real weaknesses.",
    ),
    Player(
        name="Julius Erving",
        teams=["Nets", "76ers"],
        decades=[Decade.SEVENTIES, Decade.EIGHTIES],
        stats=PlayerStats(scoring=88, playmaking=76, rebounding=72, defense=85,
                          efficiency=84, athleticism=96),
        bio="Dr. J invented the air game. First player to make athleticism an art form.",
    ),
    Player(
        name="Walt Frazier",
        teams=["Knicks"],
        decades=[Decade.SEVENTIES],
        stats=PlayerStats(scoring=78, playmaking=88, rebounding=58, defense=92,
                          efficiency=85, athleticism=84),
        bio="Clyde was the complete guard — elite IQ, lockdown D, stylish playmaking.",
    ),
    Player(
        name="Pete Maravich",
        teams=["Hawks", "Jazz", "Celtics"],
        decades=[Decade.SEVENTIES],
        stats=PlayerStats(scoring=96, playmaking=91, rebounding=42, defense=62,
                          efficiency=74, athleticism=80),
        bio="Pistol Pete was an offensive savant. Defense and rebounding were real costs.",
    ),
    Player(
        name="Bob McAdoo",
        teams=["Braves", "Knicks", "Lakers"],
        decades=[Decade.SEVENTIES, Decade.EIGHTIES],
        stats=PlayerStats(scoring=94, playmaking=50, rebounding=80, defense=72,
                          efficiency=80, athleticism=85),
        bio="Three-time scoring champ. A pure shooter-scorer before that archetype existed.",
    ),

    # ── 1980s ────────────────────────────────────────────────────────────────

    Player(
        name="Magic Johnson",
        teams=["Lakers"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=82, playmaking=100, rebounding=68, defense=78,
                          efficiency=91, athleticism=88),
        bio="Showtime's engine. Court vision and will to win are the highest ever at PG.",
    ),
    Player(
        name="Larry Bird",
        teams=["Celtics"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=92, playmaking=91, rebounding=80, defense=77,
                          efficiency=92, athleticism=72),
        bio="Pure basketball genius. Shot, passing, IQ, competitive fire — all elite.",
    ),
    Player(
        name="Michael Jordan",
        teams=["Bulls", "Wizards"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=98, playmaking=80, rebounding=62, defense=96,
                          efficiency=91, athleticism=97),
        bio="The standard. Two-way dominance, unmatched will. Defined what clutch means.",
    ),
    Player(
        name="Isiah Thomas",
        teams=["Pistons"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=85, playmaking=94, rebounding=42, defense=78,
                          efficiency=82, athleticism=82),
        bio="Bad Boys' engine. Fearless, elite playmaking, overcame every size disadvantage.",
    ),
    Player(
        name="Charles Barkley",
        teams=["76ers", "Suns", "Rockets"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=88, playmaking=70, rebounding=90, defense=78,
                          efficiency=88, athleticism=88),
        bio="Undersized PF who forced his way to MVP. Best rebounder relative to size ever.",
    ),
    Player(
        name="John Stockton",
        teams=["Jazz"],
        decades=[Decade.EIGHTIES, Decade.NINETIES, Decade.TWO_THOUSANDS],
        stats=PlayerStats(scoring=70, playmaking=98, rebounding=42, defense=84,
                          efficiency=90, athleticism=76),
        bio="All-time assists and steals leader. Ran the pick-and-roll better than anyone.",
    ),

    # ── 1990s ────────────────────────────────────────────────────────────────

    Player(
        name="Hakeem Olajuwon",
        teams=["Rockets"],
        decades=[Decade.EIGHTIES, Decade.NINETIES],
        stats=PlayerStats(scoring=88, playmaking=65, rebounding=90, defense=98,
                          efficiency=89, athleticism=90),
        bio="The Dream. Footwork never matched. Dream shake and defensive IQ are law.",
    ),
    Player(
        name="Shaquille O'Neal",
        teams=["Magic", "Lakers", "Heat", "Suns", "Cavaliers", "Celtics"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS],
        stats=PlayerStats(scoring=93, playmaking=52, rebounding=88, defense=88,
                          efficiency=76, athleticism=99),
        bio="When healthy and locked in, the most physically dominant force ever. FTs are the gate.",
    ),
    Player(
        name="David Robinson",
        teams=["Spurs"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS],
        stats=PlayerStats(scoring=86, playmaking=55, rebounding=88, defense=95,
                          efficiency=90, athleticism=96),
        bio="The Admiral was a freakish athlete who could do everything at center.",
    ),
    Player(
        name="Allen Iverson",
        teams=["76ers", "Nuggets", "Pistons"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS],
        stats=PlayerStats(scoring=96, playmaking=75, rebounding=42, defense=75,
                          efficiency=72, athleticism=93),
        bio="The Answer carried teams on pure will. Volume and FT% are real costs.",
    ),

    # ── 2000s ────────────────────────────────────────────────────────────────

    Player(
        name="Kobe Bryant",
        teams=["Lakers"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS, Decade.TWENTY_TENS],
        stats=PlayerStats(scoring=96, playmaking=72, rebounding=60, defense=90,
                          efficiency=83, athleticism=92),
        bio="Mamba Mentality. Two-way elite, dynasty piece and solo carrier. Clutch personified.",
    ),
    Player(
        name="Tim Duncan",
        teams=["Spurs"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS, Decade.TWENTY_TENS],
        stats=PlayerStats(scoring=84, playmaking=68, rebounding=92, defense=96,
                          efficiency=90, athleticism=82),
        bio="The Big Fundamental. Most efficient great player ever. Zero exploitable weaknesses.",
    ),
    Player(
        name="Steve Nash",
        teams=["Suns", "Mavericks", "Lakers"],
        decades=[Decade.NINETIES, Decade.TWO_THOUSANDS, Decade.TWENTY_TENS],
        stats=PlayerStats(scoring=80, playmaking=99, rebounding=38, defense=58,
                          efficiency=97, athleticism=74),
        bio="Two-time MVP with the most efficient offense ever built. Defense is a real gate.",
    ),
    Player(
        name="Dirk Nowitzki",
        teams=["Mavericks"],
        decades=[Decade.TWO_THOUSANDS, Decade.TWENTY_TENS],
        stats=PlayerStats(scoring=94, playmaking=65, rebounding=72, defense=68,
                          efficiency=92, athleticism=78),
        bio="Reinvented the stretch big. Finals MVP in 2011 was all-time clutch.",
    ),

    # ── 2010s ────────────────────────────────────────────────────────────────

    Player(
        name="LeBron James",
        teams=["Cavaliers", "Heat", "Lakers"],
        decades=[Decade.TWO_THOUSANDS, Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=94, playmaking=96, rebounding=78, defense=90,
                          efficiency=93, athleticism=98),
        bio="Most complete player ever across 20 years. No real weakness at any point.",
    ),
    Player(
        name="Stephen Curry",
        teams=["Warriors"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=98, playmaking=86, rebounding=48, defense=70,
                          efficiency=98, athleticism=80),
        bio="Changed basketball. Best shooter ever. Off-ball gravity is a stat that didn't exist before him.",
    ),
    Player(
        name="Kevin Durant",
        teams=["Thunder", "Warriors", "Nets", "Suns", "Celtics"],
        decades=[Decade.TWO_THOUSANDS, Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=99, playmaking=74, rebounding=72, defense=78,
                          efficiency=97, athleticism=92),
        bio="Unguardable at 7 feet. Most fluid scorer at any size the game has ever produced.",
    ),
    Player(
        name="Kawhi Leonard",
        teams=["Spurs", "Raptors", "Clippers"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=90, playmaking=68, rebounding=72, defense=97,
                          efficiency=90, athleticism=90),
        bio="The Klaw at peak was the closest thing to zero-weakness in the modern era.",
    ),

    # ── 2020s ────────────────────────────────────────────────────────────────

    Player(
        name="Nikola Jokic",
        teams=["Nuggets"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=88, playmaking=98, rebounding=90, defense=76,
                          efficiency=99, athleticism=72),
        bio="Three-time MVP. Most efficient multi-dimensional player in history.",
    ),
    Player(
        name="Giannis Antetokounmpo",
        teams=["Bucks"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=92, playmaking=72, rebounding=88, defense=92,
                          efficiency=82, athleticism=99),
        bio="Modern Wilt. Physical freak, improving every year. FTs are still an issue.",
    ),
    Player(
        name="Jayson Tatum",
        teams=["Celtics"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=90, playmaking=70, rebounding=68, defense=80,
                          efficiency=86, athleticism=86),
        bio="Champion and Finals MVP. Best player on the most complete team in the East.",
    ),
    Player(
        name="Luka Doncic",
        teams=["Mavericks", "Lakers"],
        decades=[Decade.TWENTY_TENS, Decade.TWENTY_TWENTIES],
        stats=PlayerStats(scoring=96, playmaking=96, rebounding=72, defense=62,
                          efficiency=90, athleticism=76),
        bio="Offensive force of nature. Defense is a consistent target for opponents.",
    ),
]

# Lookup helpers
def get_player(name: str) -> Player:
    for p in PLAYERS:
        if p.name == name:
            return p
    raise KeyError(f"Player not found: {name}")


def players_for_slot(team: str, decade: Decade) -> list[Player]:
    return [p for p in PLAYERS if team in p.teams and decade in p.decades]
