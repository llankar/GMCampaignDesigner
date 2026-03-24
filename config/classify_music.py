import json
import copy

INPUT_FILE = "audio_library.json"
OUTPUT_FILE = "audio_library_with_moods.json"

KEYWORDS = {
    "combat": [
        "battle","fight","war","wrath","siege","attack","brawl","clash","duel",
        "strike","rage","fury","assault","skirmish","blood","violence","weapon",
        "steel","army","soldier","boss","final","epic","confrontation","destruction",
        "aggressive","brutal","intense","chaos","violent","conflict","engage",
        "combat","charge","offensive","defense","kill","slay","victory","defeat",
        "impact","thunder","explosion","domination","onslaught","rampage",
        "crush","power","force","battlefield","warfare", "die"
    ],
    "chase": [
        "chase","escape","ride","run","storm","flight","pursuit","rush","speed",
        "fast","gallop","hunt","tracking","flee","panic","danger","urgent",
        "race","charge","drive","rapid","tense","pressure","alert","escape",
        "thrill","sprint","dash","hurry","movement","evasion","pursue","follow",
        "trail","search","survive","dangerous","intensity","adrenaline",
        "breathless","wild","unstoppable","reckless","rush","swift","velocity",
        "momentum","breakthrough","rush","escape","flight"
    ],
    "calm": [
        "peaceful","calm","quiet","soft","gentle","rest","safe","relax","serene",
        "tranquil","still","dream","sleep","lullaby","breeze","light","sun",
        "warm","comfort","slow","smooth","tender","mild","ease","harmony",
        "balance","meditative","ambient","floating","healing","restful",
        "soothing","delicate","clear","pure","open","wide","nature","sky",
        "water","flow","silence","easeful","calming","softness","peace",
        "relief","gentleness","airy","dreamy"
    ],
    "mystery": [
        "shadow","dark","black","fear","whisper","unknown","mystery","secret",
        "hidden","veil","curse","crypt","necromancer","ghost","haunt","eerie",
        "ominous","strange","void","night","abyss","occult","arcane","enigmatic",
        "obscure","veil","mask","forbidden","ritual","ancient","lost","forgotten",
        "whispers","lurking","creeping","silent","cold","fog","mist","horror",
        "uncertain","cryptic","dread","tenebrous","twilight","shadowy","darkness",
        "murmur","suspense","haunting","disturbing"
    ],
    "emotional": [
        "love","theme","heart","memory","hope","sad","sorrow","loss","grief",
        "tears","cry","farewell","longing","nostalgia","emotion","feeling",
        "romance","passion","beautiful","melancholy","dream","soul","tragic",
        "emotional","touching","moving","sentimental","yearning","affection",
        "bond","connection","warmth","devotion","pain","healing","regret",
        "despair","lonely","alone","reunion","goodbye","promise","faith",
        "inspiration","uplifting","bittersweet","soft","delicate","heartfelt"
    ],
    "exploration": [
        "journey","adventure","travel","road","path","quest","explore",
        "discovery","wander","lands","world","forest","mountain","valley",
        "desert","sea","island","horizon","expedition","unknown","roam",
        "venture","trail","crossing","voyage","frontier","wild","nature",
        "open","vast","distance","far","beyond","new","discover","search",
        "mapping","terrain","traveling","movement","odyssey","pilgrimage",
        "exploration","walk","trek","climb","river","sky","earth","journeying"
    ]
}

def classify(name):
    name = name.lower()
    scores = {k: 0 for k in KEYWORDS}

    for category, words in KEYWORDS.items():
        for w in words:
            if w in name:
                scores[category] += 1

    best = max(scores, key=scores.get)

    if scores[best] == 0:
        return "no mood"

    return best


# 🔹 Lecture
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

# 🔹 Copie
new_data = copy.deepcopy(data)

# 🔹 Traitement
for category in new_data["music"]["categories"]:
    for track in new_data["music"]["categories"][category]["tracks"]:
        track["mood"] = classify(track["name"])

# 🔹 Sauvegarde
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(new_data, f, indent=2, ensure_ascii=False)

print("✅ New file generated:", OUTPUT_FILE)