"""Music mood classification helpers."""

from __future__ import annotations

NO_MOOD = "no mood"

MOOD_KEYWORDS: dict[str, list[str]] = {
    "combat": [
        "battle", "fight", "war", "wrath", "siege", "attack", "brawl", "clash", "duel",
        "strike", "rage", "fury", "assault", "skirmish", "blood", "violence", "weapon",
        "steel", "army", "soldier", "boss", "final", "epic", "confrontation", "destruction",
        "aggressive", "brutal", "intense", "chaos", "violent", "conflict", "engage",
        "combat", "charge", "offensive", "defense", "kill", "slay", "victory", "defeat",
        "impact", "thunder", "explosion", "domination", "onslaught", "rampage",
        "crush", "power", "force", "battlefield", "warfare", "die",
    ],
    "chase": [
        "chase", "escape", "ride", "run", "storm", "flight", "pursuit", "rush", "speed",
        "fast", "gallop", "hunt", "tracking", "flee", "panic", "danger", "urgent",
        "race", "charge", "drive", "rapid", "tense", "pressure", "alert", "thrill",
        "sprint", "dash", "hurry", "movement", "evasion", "pursue", "follow", "trail",
        "search", "survive", "dangerous", "intensity", "adrenaline", "breathless", "wild",
        "unstoppable", "reckless", "swift", "velocity", "momentum", "breakthrough",
    ],
    "calm": [
        "peaceful", "calm", "quiet", "soft", "gentle", "rest", "safe", "relax", "serene",
        "tranquil", "still", "dream", "sleep", "lullaby", "breeze", "light", "sun",
        "warm", "comfort", "slow", "smooth", "tender", "mild", "ease", "harmony",
        "balance", "meditative", "ambient", "floating", "healing", "restful", "soothing",
        "delicate", "clear", "pure", "open", "wide", "nature", "sky", "water", "flow",
        "silence", "easeful", "calming", "softness", "peace", "relief", "gentleness", "airy", "dreamy",
    ],
    "mystery": [
        "shadow", "dark", "black", "fear", "whisper", "unknown", "mystery", "secret", "hidden",
        "veil", "curse", "crypt", "necromancer", "ghost", "haunt", "eerie", "ominous", "strange",
        "void", "night", "abyss", "occult", "arcane", "enigmatic", "obscure", "mask", "forbidden",
        "ritual", "ancient", "lost", "forgotten", "whispers", "lurking", "creeping", "silent",
        "cold", "fog", "mist", "horror", "uncertain", "cryptic", "dread", "tenebrous", "twilight",
        "shadowy", "darkness", "murmur", "suspense", "haunting", "disturbing",
    ],
    "emotional": [
        "love", "theme", "heart", "memory", "hope", "sad", "sorrow", "loss", "grief", "tears",
        "cry", "farewell", "longing", "nostalgia", "emotion", "feeling", "romance", "passion",
        "beautiful", "melancholy", "dream", "soul", "tragic", "touching", "moving", "sentimental",
        "yearning", "affection", "bond", "connection", "warmth", "devotion", "pain", "healing",
        "regret", "despair", "lonely", "alone", "reunion", "goodbye", "promise", "faith",
        "inspiration", "uplifting", "bittersweet", "soft", "delicate", "heartfelt",
    ],
    "exploration": [
        "journey", "adventure", "travel", "road", "path", "quest", "explore", "discovery", "wander",
        "lands", "world", "forest", "mountain", "valley", "desert", "sea", "island", "horizon",
        "expedition", "unknown", "roam", "venture", "trail", "crossing", "voyage", "frontier", "wild",
        "nature", "open", "vast", "distance", "far", "beyond", "new", "discover", "search",
        "mapping", "terrain", "traveling", "movement", "odyssey", "pilgrimage", "walk", "trek",
        "climb", "river", "sky", "earth", "journeying",
    ],
}


def classify_track_mood(track_name: str) -> str:
    """Handle classify track mood."""
    normalized_name = (track_name or "").casefold()
    scores = {mood: 0 for mood in MOOD_KEYWORDS}
    for mood, keywords in MOOD_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized_name:
                scores[mood] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return NO_MOOD
    return best
