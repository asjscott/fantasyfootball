"""Identity crosswalk: reconciles season-scoped FPL ids to stable internal ids.

Both the historical GitHub repo and the live FPL API expose a `code` field
that is stable for a given real-world player/team across seasons and API
sources (unlike `id`, which is season-scoped and changes on transfers). The
primary resolution path is therefore an exact join on `code`. Fuzzy
name+team matching is only a fallback for the rare case where `code` is
missing or malformed, and every resolution (exact or fuzzy) is logged to
`player_id_map` for audit.
"""

from rapidfuzz import fuzz, process


def upsert_team(cur, fpl_code: int, name: str) -> int:
    cur.execute(
        """
        INSERT INTO teams (fpl_code, name)
        VALUES (%s, %s)
        ON CONFLICT (fpl_code) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        (fpl_code, name),
    )
    return cur.fetchone()[0]


def upsert_team_season(
    cur,
    team_id: int,
    season: str,
    fpl_season_team_id: int,
    strength: int | None,
    strength_attack_home: int | None,
    strength_attack_away: int | None,
    strength_defence_home: int | None,
    strength_defence_away: int | None,
) -> int:
    cur.execute(
        """
        INSERT INTO team_seasons (
            team_id, season, fpl_season_team_id, strength,
            strength_attack_home, strength_attack_away,
            strength_defence_home, strength_defence_away
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (team_id, season) DO UPDATE SET
            fpl_season_team_id = EXCLUDED.fpl_season_team_id,
            strength = EXCLUDED.strength,
            strength_attack_home = EXCLUDED.strength_attack_home,
            strength_attack_away = EXCLUDED.strength_attack_away,
            strength_defence_home = EXCLUDED.strength_defence_home,
            strength_defence_away = EXCLUDED.strength_defence_away
        RETURNING id
        """,
        (team_id, season, fpl_season_team_id, strength,
         strength_attack_home, strength_attack_away,
         strength_defence_home, strength_defence_away),
    )
    return cur.fetchone()[0]


def _find_player_by_code(cur, fpl_code: int) -> int | None:
    cur.execute("SELECT id FROM players WHERE fpl_code = %s", (fpl_code,))
    row = cur.fetchone()
    return row[0] if row else None


def _fuzzy_match_player(cur, first_name: str, second_name: str) -> tuple[int, float] | None:
    """Fallback only: used when `code` is missing/malformed for a source row."""
    full_name = f"{first_name} {second_name}"
    cur.execute("SELECT id, first_name, second_name FROM players")
    candidates = {row[0]: f"{row[1]} {row[2]}" for row in cur.fetchall()}
    if not candidates:
        return None

    match = process.extractOne(full_name, candidates, scorer=fuzz.WRatio)
    if match is None:
        return None
    matched_name, score, player_id = match
    if score < 85:
        return None
    return player_id, score / 100


def resolve_player(
    cur,
    season: str,
    fpl_season_element_id: int,
    fpl_code: int | None,
    first_name: str,
    second_name: str,
    web_name: str,
) -> int:
    """Returns the internal player_id for a source row, creating a new
    `players` row if this code has never been seen before. Logs the
    resolution decision to `player_id_map`.
    """
    player_id: int | None = None
    match_method = "exact_code"
    confidence = 1.0

    if fpl_code is not None:
        player_id = _find_player_by_code(cur, fpl_code)
        if player_id is None:
            cur.execute(
                """
                INSERT INTO players (fpl_code, first_name, second_name, web_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (fpl_code, first_name, second_name, web_name),
            )
            player_id = cur.fetchone()[0]
    else:
        match_method = "fuzzy_name"
        fuzzy_result = _fuzzy_match_player(cur, first_name, second_name)
        if fuzzy_result is not None:
            player_id, confidence = fuzzy_result
        else:
            match_method = "manual"
            confidence = 0.0

    cur.execute(
        """
        INSERT INTO player_id_map (
            season, source_element_id, source_code, matched_player_id,
            match_method, confidence, reviewed
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (season, fpl_season_element_id, fpl_code, player_id, match_method,
         confidence, match_method == "exact_code"),
    )

    if player_id is None:
        raise ValueError(
            f"Could not resolve player for season={season} element_id={fpl_season_element_id} "
            f"({first_name} {second_name}) — needs manual review in player_id_map"
        )

    return player_id


def upsert_player_season(
    cur, player_id: int, season: str, fpl_season_element_id: int, team_season_id: int, position: str
) -> int:
    cur.execute(
        """
        INSERT INTO player_seasons (player_id, season, fpl_season_element_id, team_id, position)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (player_id, season) DO UPDATE SET
            fpl_season_element_id = EXCLUDED.fpl_season_element_id,
            team_id = EXCLUDED.team_id,
            position = EXCLUDED.position
        RETURNING id
        """,
        (player_id, season, fpl_season_element_id, team_season_id, position),
    )
    return cur.fetchone()[0]
