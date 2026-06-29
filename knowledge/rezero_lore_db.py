"""Re:Zero kritik anlar veritabanı — sezon/episode/zaman bazlı."""
REZERO_KEY_MOMENTS = {
    "s1e01": [
        {"start": 60, "end": 120, "label": "subaru_isekai", "title": "Subaru başka dünyaya çağrılıyor", "importance": 8},
        {"start": 480, "end": 600, "label": "puck_emilia_greet", "title": "Puck ve Emilia ile tanışma", "importance": 9},
        {"start": 1080, "end": 1200, "label": "death_loop_hint", "title": "İlk ölüm ipucu", "importance": 7},
    ],
    "s1e07": [
        {"start": 300, "end": 420, "label": "rem_intro", "title": "Rem ile tanışma", "importance": 9},
        {"start": 900, "end": 1020, "label": "rem_subaru_bond", "title": "Rem bağ kurmaya başlıyor", "importance": 7},
    ],
    "s1e15": [
        {"start": 600, "end": 720, "label": "rem_confession", "title": "Rem itiraf sahnesi", "importance": 10},
        {"start": 1200, "end": 1400, "label": "subaru_breakdown", "title": "Subaru çöküşü", "importance": 9},
    ],
    "s1e18": [
        {"start": 600, "end": 800, "label": "rem_love_confession", "title": "Rem'in aşk itirafı", "importance": 10},
        {"start": 1400, "end": 1600, "label": "subaru_rise", "title": "Subaru ayağa kalkıyor", "importance": 9},
    ],
    "s1e23": [
        {"start": 400, "end": 550, "label": "petelguese_battle", "title": "Petelguese savaşı", "importance": 8},
    ],
    "s1e25": [
        {"start": 300, "end": 500, "label": "white_whale_fight", "title": "Beyaz Balina savaşı", "importance": 9},
        {"start": 1200, "end": 1400, "label": "season_finale", "title": "Sezon finali", "importance": 10},
    ],
    "s2e04": [
        {"start": 200, "end": 350, "label": "echidna_contract", "title": "Echidna ile sözleşme", "importance": 9},
    ],
    "s2e08": [
        {"start": 500, "end": 650, "label": "subaru_otto_friendship", "title": "Otto dostluğu", "importance": 8},
    ],
    "s2e11": [
        {"start": 400, "end": 600, "label": "subaru_choose_emilia", "title": "Subaru Emilia'yı seçiyor", "importance": 10},
    ],
    "s2e24": [
        {"start": 600, "end": 800, "label": "great_spirit_finale", "title": "Büyük ruh finali", "importance": 9},
    ],
}


def lookup_moment(season: int, episode: int, timestamp: float) -> dict:
    key = f"s{season}e{episode:02d}"
    moments = REZERO_KEY_MOMENTS.get(key, [])
    for m in moments:
        if m["start"] <= timestamp <= m["end"]:
            return {"matched": True, **m}
    return {"matched": False}


def score_scene_importance(scene: dict) -> float:
    trace = scene.get("trace_moe", {})
    if not trace:
        return 0.0
    if not trace.get("is_rezero"):
        return 0.0
    moment = lookup_moment(
        trace.get("season", 0),
        trace.get("episode", 0),
        trace.get("timestamp", 0)
    )
    if moment["matched"]:
        return moment["importance"]
    return trace.get("similarity", 0.0) * 5.0
