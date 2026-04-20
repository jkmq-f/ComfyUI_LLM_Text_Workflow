from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.model_loader import load_llm_model, unload_model
from ..utils.language_prompt_utils import normalize_output_language, output_language_instruction

DEFAULT_OUTFIT_SYSTEM_PROMPT = (
    "You design outfit specifications for creative workflows. "
    "Use only the fields that are actually provided. "
    "If a field is empty, missing, or set to unspecified, do not mention it, do not infer it, and do not compensate for it unless the draft JSON already contains concrete values. "
    "Describe visible clothing only. Avoid vague praise words like stylish, nice, fashionable, cool unless supported by visible details. "
    "When a profession is provided, keep the clothing visibly appropriate to that profession. "
    "Do not replace, swap, generalize, or reinterpret concrete clothing items already present in the draft JSON. "
    "Keep top, bottom, outer, shoes, accessories, color scheme, and silhouette aligned with the draft unless a field is empty. "
    "Return a clean JSON object only. No markdown. No explanation."
)

STOP_TOKENS = ["<end_of_turn>", "<eos>", "<bos>"]
UNSPECIFIED_VALUES = {"", "none", "null", "unspecified", "any", "未指定", "なし", "空"}

STYLE_LIBRARY = {
    "casual": {
        "tops": ["cotton t-shirt", "relaxed knit sweater", "henley shirt", "soft hoodie"],
        "bottoms": ["straight denim pants", "easy chinos", "relaxed cargo pants"],
        "outers": ["light blouson", "zip hoodie", "denim jacket", "none"],
        "shoes": ["low-top sneakers", "canvas sneakers", "simple leather sneakers"],
        "accessories": ["simple wristwatch", "crossbody bag", "none"],
        "silhouette": "slightly relaxed",
    },
    "street": {
        "tops": ["oversized hoodie", "graphic sweatshirt", "boxy long-sleeve shirt"],
        "bottoms": ["wide cargo pants", "baggy denim pants", "tapered utility pants"],
        "outers": ["bomber jacket", "nylon windbreaker", "none"],
        "shoes": ["high-top sneakers", "chunky sneakers", "skate shoes"],
        "accessories": ["beanie", "chain necklace", "crossbody sling bag"],
        "silhouette": "loose",
    },
    "formal": {
        "tops": ["dress shirt", "fine-gauge knit", "tailored vest"],
        "bottoms": ["pressed slacks", "straight wool trousers"],
        "outers": ["tailored jacket", "single-breasted coat", "none"],
        "shoes": ["leather loafers", "plain-toe leather shoes", "side-gore dress boots"],
        "accessories": ["leather belt", "slim wristwatch", "none"],
        "silhouette": "clean",
    },
    "techwear": {
        "tops": ["mock-neck performance top", "technical hoodie", "structured utility shirt"],
        "bottoms": ["tapered utility pants", "technical cargo pants"],
        "outers": ["shell jacket", "utility vest", "hooded technical coat"],
        "shoes": ["technical sneakers", "combat boots", "trail shoes"],
        "accessories": ["utility pouch", "modular sling bag", "none"],
        "silhouette": "functional layered",
    },
    "outdoor": {
        "tops": ["thermal long-sleeve shirt", "fleece pullover", "breathable base layer"],
        "bottoms": ["trail pants", "durable cargo pants"],
        "outers": ["mountain parka", "light down jacket", "shell jacket"],
        "shoes": ["hiking boots", "trail shoes", "rugged sneakers"],
        "accessories": ["cap", "small backpack", "none"],
        "silhouette": "practical",
    },
    "mode": {
        "tops": ["high-neck top", "draped shirt", "minimal knit top"],
        "bottoms": ["wide trousers", "cropped tailored pants", "slim slacks"],
        "outers": ["long coat", "structured blazer", "none"],
        "shoes": ["leather boots", "minimal sneakers", "sleek loafers"],
        "accessories": ["silver ring", "minimal shoulder bag", "none"],
        "silhouette": "sharp with controlled volume",
    },
}


RANDOM_MODE_OPTIONS = ["input", "random"]
STYLE_OPTIONS = sorted(STYLE_LIBRARY.keys())
SEASON_OPTIONS = ["spring", "summer", "autumn", "winter"]
GENDER_OPTIONS = [
    "female", "male", "woman", "man", "non-binary", "androgynous", "feminine", "masculine"
]

PROFESSION_LIBRARY = {
    "carpenter": {
        "workwear": {
            "tops": ["heavy flannel work shirt", "rugged pullover hoodie", "reinforced canvas work jacket", "long-sleeve work tee"],
            "bottoms": ["carpenter pants", "reinforced work trousers", "heavy-duty duck canvas pants", "straight work denim"],
            "outers": ["canvas chore jacket", "weathered work vest", "hooded work jacket", "none"],
            "shoes": ["lace-up work boots", "safety-toe work boots", "rugged high-top work shoes"],
            "accessories": ["thick work belt", "beanie", "none"],
            "silhouette": "practical with room for movement",
        },
        "off_duty": {
            "tops": ["washed work shirt", "worn henley shirt", "rugged hoodie", "faded thermal shirt"],
            "bottoms": ["straight denim pants", "work chinos", "utility pants"],
            "outers": ["canvas jacket", "zip hoodie", "none"],
            "shoes": ["work boots", "rugged sneakers", "leather high-top shoes"],
            "accessories": ["simple cap", "plain belt", "none"],
            "silhouette": "relaxed but durable",
        },
    },
    "mechanic": {
        "workwear": {
            "tops": ["zip-front mechanic shirt", "oil-resistant work jacket", "dark work tee", "utility overshirt"],
            "bottoms": ["sturdy work trousers", "mechanic pants", "dark utility pants"],
            "outers": ["shop jacket", "light utility vest", "none"],
            "shoes": ["work boots", "safety work shoes", "slip-resistant work shoes"],
            "accessories": ["work cap", "durable belt", "none"],
            "silhouette": "compact and work-ready",
        },
        "off_duty": {
            "tops": ["dark hoodie", "heavy tee", "utility shirt"],
            "bottoms": ["dark denim pants", "utility cargo pants", "straight chinos"],
            "outers": ["garage jacket", "none"],
            "shoes": ["rugged sneakers", "work boots", "leather sneakers"],
            "accessories": ["cap", "none"],
            "silhouette": "slightly relaxed",
        },
    },
    "electrician": {
        "workwear": {
            "tops": ["structured work shirt", "light utility jacket", "long-sleeve performance work shirt"],
            "bottoms": ["utility trousers", "reinforced work pants", "straight cargo work pants"],
            "outers": ["light work vest", "weather-resistant work shell", "none"],
            "shoes": ["protective work boots", "durable work shoes", "high-ankle utility boots"],
            "accessories": ["durable belt", "none"],
            "silhouette": "clean and practical",
        },
        "off_duty": {
            "tops": ["utility overshirt", "henley shirt", "plain hoodie"],
            "bottoms": ["straight denim", "work chinos", "cargo pants"],
            "outers": ["light shell jacket", "none"],
            "shoes": ["rugged sneakers", "utility boots"],
            "accessories": ["none", "simple cap"],
            "silhouette": "slightly relaxed",
        },
    },
    "chef": {
        "workwear": {
            "tops": ["double-breasted chef jacket", "short-sleeve chef coat", "clean kitchen jacket"],
            "bottoms": ["straight kitchen pants", "dark work slacks", "check kitchen trousers"],
            "outers": ["apron", "none"],
            "shoes": ["slip-resistant kitchen shoes", "closed-toe work shoes"],
            "accessories": ["waist apron", "none"],
            "silhouette": "clean and easy to move in",
        },
        "off_duty": {
            "tops": ["clean knit polo", "plain tee", "light cardigan"],
            "bottoms": ["straight trousers", "dark denim", "relaxed chinos"],
            "outers": ["light jacket", "none"],
            "shoes": ["simple leather sneakers", "loafers", "clean sneakers"],
            "accessories": ["none", "simple watch"],
            "silhouette": "clean relaxed",
        },
    },
    "nurse": {
        "workwear": {
            "tops": ["scrub top", "clean medical tunic"],
            "bottoms": ["scrub pants", "straight medical pants"],
            "outers": ["light cardigan", "none"],
            "shoes": ["supportive work sneakers", "closed medical shoes"],
            "accessories": ["name badge", "none"],
            "silhouette": "clean functional",
        },
        "off_duty": {
            "tops": ["soft knit top", "clean hoodie", "cotton shirt"],
            "bottoms": ["easy trousers", "straight denim", "relaxed slacks"],
            "outers": ["cardigan", "none"],
            "shoes": ["clean sneakers", "flat loafers"],
            "accessories": ["simple tote bag", "none"],
            "silhouette": "soft relaxed",
        },
    },
    "teacher": {
        "workwear": {
            "tops": ["button-up shirt", "fine knit top", "clean blouse"],
            "bottoms": ["straight slacks", "clean ankle trousers", "modest skirt"],
            "outers": ["cardigan", "light blazer", "none"],
            "shoes": ["loafers", "low block-heel shoes", "clean leather flats"],
            "accessories": ["simple watch", "tote bag", "none"],
            "silhouette": "tidy and approachable",
        },
        "off_duty": {
            "tops": ["relaxed knit", "casual shirt", "hoodie"],
            "bottoms": ["straight denim", "easy trousers", "relaxed skirt"],
            "outers": ["light jacket", "none"],
            "shoes": ["sneakers", "loafers"],
            "accessories": ["shoulder bag", "none"],
            "silhouette": "comfortable neat",
        },
    },
    "office worker": {
        "workwear": {
            "tops": ["dress shirt", "fine knit", "blouse"],
            "bottoms": ["pressed slacks", "straight office trousers", "pencil skirt"],
            "outers": ["tailored jacket", "clean cardigan", "none"],
            "shoes": ["leather loafers", "plain pumps", "dress shoes"],
            "accessories": ["leather belt", "simple watch", "structured tote bag", "none"],
            "silhouette": "clean and controlled",
        },
        "off_duty": {
            "tops": ["relaxed knit", "casual shirt", "simple tee"],
            "bottoms": ["straight denim", "relaxed trousers", "easy chinos"],
            "outers": ["light coat", "none"],
            "shoes": ["clean sneakers", "loafers"],
            "accessories": ["shoulder bag", "none"],
            "silhouette": "slightly relaxed",
        },
    },
    "photographer": {
        "workwear": {
            "tops": ["utility shirt", "dark overshirt", "light technical jacket"],
            "bottoms": ["utility cargo pants", "dark outdoor trousers", "flex work pants"],
            "outers": ["utility vest", "weather shell", "none"],
            "shoes": ["trail shoes", "rugged sneakers", "light hiking boots"],
            "accessories": ["crossbody gear bag", "cap", "none"],
            "silhouette": "mobile and layered",
        },
        "off_duty": {
            "tops": ["washed tee", "hoodie", "overshirt"],
            "bottoms": ["cargo pants", "denim pants", "easy trousers"],
            "outers": ["light jacket", "none"],
            "shoes": ["sneakers", "trail shoes"],
            "accessories": ["small sling bag", "none"],
            "silhouette": "relaxed practical",
        },
    },
    "security guard": {
        "workwear": {
            "tops": ["security uniform shirt", "dark polo shirt", "structured duty shirt"],
            "bottoms": ["uniform trousers", "dark straight duty pants"],
            "outers": ["duty jacket", "light duty vest", "none"],
            "shoes": ["polished duty boots", "black duty shoes"],
            "accessories": ["duty belt", "none"],
            "silhouette": "clean and authoritative",
        },
        "off_duty": {
            "tops": ["dark hoodie", "polo shirt", "plain tee"],
            "bottoms": ["straight denim", "cargo pants", "work chinos"],
            "outers": ["light jacket", "none"],
            "shoes": ["black sneakers", "boots"],
            "accessories": ["cap", "none"],
            "silhouette": "simple relaxed",
        },
    },
    "farmer": {
        "workwear": {
            "tops": ["sun-faded work shirt", "breathable long-sleeve field shirt", "rugged henley", "lightweight work hoodie"],
            "bottoms": ["field work pants", "durable straight denim", "utility farm trousers"],
            "outers": ["canvas vest", "weathered chore jacket", "none"],
            "shoes": ["mud-resistant work boots", "rubber work boots", "rugged field shoes"],
            "accessories": ["work cap", "wide-brim hat", "none"],
            "silhouette": "practical and sun-ready",
        },
        "off_duty": {
            "tops": ["washed plaid shirt", "soft hoodie", "faded tee"],
            "bottoms": ["straight denim", "work chinos", "relaxed utility pants"],
            "outers": ["canvas jacket", "none"],
            "shoes": ["work boots", "rugged sneakers"],
            "accessories": ["cap", "none"],
            "silhouette": "relaxed durable",
        },
    },
    "delivery driver": {
        "workwear": {
            "tops": ["zip-front work jacket", "light polo shirt", "quick-dry work shirt"],
            "bottoms": ["stretch work pants", "dark utility trousers", "straight cargo pants"],
            "outers": ["weather-resistant shell", "light vest", "none"],
            "shoes": ["supportive walking sneakers", "durable work sneakers", "slip-resistant shoes"],
            "accessories": ["crossbody utility bag", "cap", "none"],
            "silhouette": "mobile and practical",
        },
        "off_duty": {
            "tops": ["hoodie", "polo shirt", "plain tee"],
            "bottoms": ["easy chinos", "straight denim", "cargo pants"],
            "outers": ["light jacket", "none"],
            "shoes": ["sneakers", "rugged sneakers"],
            "accessories": ["small shoulder bag", "none"],
            "silhouette": "easy and active",
        },
    },
    "warehouse worker": {
        "workwear": {
            "tops": ["durable work tee", "utility polo shirt", "light work sweatshirt"],
            "bottoms": ["reinforced cargo pants", "warehouse work trousers", "straight utility pants"],
            "outers": ["utility vest", "light work jacket", "none"],
            "shoes": ["safety work shoes", "protective sneakers", "work boots"],
            "accessories": ["durable belt", "none"],
            "silhouette": "compact and mobile",
        },
        "off_duty": {
            "tops": ["hoodie", "heavy tee", "overshirt"],
            "bottoms": ["cargo pants", "straight denim", "easy chinos"],
            "outers": ["work jacket", "none"],
            "shoes": ["sneakers", "work boots"],
            "accessories": ["cap", "none"],
            "silhouette": "slightly relaxed",
        },
    },
    "retail staff": {
        "workwear": {
            "tops": ["clean polo shirt", "button-up shirt", "store uniform knit"],
            "bottoms": ["straight slacks", "dark chinos", "clean ankle trousers"],
            "outers": ["light cardigan", "store jacket", "none"],
            "shoes": ["clean sneakers", "loafers", "comfortable flats"],
            "accessories": ["name badge", "simple watch", "none"],
            "silhouette": "tidy and approachable",
        },
        "off_duty": {
            "tops": ["simple knit", "casual shirt", "tee"],
            "bottoms": ["straight denim", "easy trousers", "relaxed chinos"],
            "outers": ["light jacket", "none"],
            "shoes": ["sneakers", "loafers"],
            "accessories": ["shoulder bag", "none"],
            "silhouette": "clean relaxed",
        },
    },
    "barista": {
        "workwear": {
            "tops": ["apron-ready oxford shirt", "clean tee", "dark knit top"],
            "bottoms": ["straight chinos", "dark work trousers", "clean denim"],
            "outers": ["waist apron", "bib apron", "none"],
            "shoes": ["slip-resistant sneakers", "closed-toe work shoes", "simple leather sneakers"],
            "accessories": ["apron", "cap", "none"],
            "silhouette": "clean and easy to move in",
        },
        "off_duty": {
            "tops": ["hoodie", "knit polo", "washed tee"],
            "bottoms": ["straight denim", "relaxed trousers", "easy chinos"],
            "outers": ["light cardigan", "none"],
            "shoes": ["sneakers", "loafers"],
            "accessories": ["tote bag", "none"],
            "silhouette": "soft casual",
        },
    },
    "artist": {
        "workwear": {
            "tops": ["paint-marked overshirt", "soft work tee", "loose button shirt"],
            "bottoms": ["relaxed work pants", "wide denim", "utility apron pants"],
            "outers": ["canvas apron", "light chore jacket", "none"],
            "shoes": ["paint-splattered sneakers", "work clogs", "simple boots"],
            "accessories": ["canvas tote bag", "bandana", "none"],
            "silhouette": "relaxed and expressive",
        },
        "off_duty": {
            "tops": ["draped shirt", "soft knit", "washed tee"],
            "bottoms": ["wide trousers", "relaxed denim", "cropped pants"],
            "outers": ["light coat", "none"],
            "shoes": ["sneakers", "minimal boots", "slip-ons"],
            "accessories": ["shoulder bag", "silver ring", "none"],
            "silhouette": "creative relaxed",
        },
    },
    "scientist": {
        "workwear": {
            "tops": ["clean button shirt", "fine knit top", "lab-ready polo shirt"],
            "bottoms": ["straight slacks", "clean work trousers", "ankle pants"],
            "outers": ["lab coat", "light cardigan", "none"],
            "shoes": ["closed lab shoes", "clean loafers", "supportive sneakers"],
            "accessories": ["ID badge", "simple watch", "none"],
            "silhouette": "clean and controlled",
        },
        "off_duty": {
            "tops": ["knit sweater", "button shirt", "plain tee"],
            "bottoms": ["straight denim", "easy trousers", "slacks"],
            "outers": ["cardigan", "light coat", "none"],
            "shoes": ["sneakers", "loafers"],
            "accessories": ["shoulder bag", "none"],
            "silhouette": "quiet neat",
        },
    },
    "police officer": {
        "workwear": {
            "tops": ["structured uniform shirt", "dark duty polo shirt", "patrol uniform top"],
            "bottoms": ["duty trousers", "dark uniform pants"],
            "outers": ["patrol jacket", "duty vest", "none"],
            "shoes": ["duty boots", "polished patrol boots", "black duty shoes"],
            "accessories": ["duty belt", "cap", "none"],
            "silhouette": "firm and professional",
        },
        "off_duty": {
            "tops": ["dark hoodie", "plain polo", "tee"],
            "bottoms": ["straight denim", "cargo pants", "work chinos"],
            "outers": ["light jacket", "none"],
            "shoes": ["black sneakers", "boots"],
            "accessories": ["cap", "none"],
            "silhouette": "simple relaxed",
        },
    },
    "firefighter": {
        "workwear": {
            "tops": ["station uniform tee", "dark duty shirt", "protective station jacket"],
            "bottoms": ["station cargo pants", "duty work trousers"],
            "outers": ["protective jacket", "light station vest", "none"],
            "shoes": ["station boots", "protective work boots"],
            "accessories": ["durable belt", "none"],
            "silhouette": "strong and ready",
        },
        "off_duty": {
            "tops": ["hoodie", "heavy tee", "polo shirt"],
            "bottoms": ["straight denim", "cargo pants", "work chinos"],
            "outers": ["light jacket", "none"],
            "shoes": ["boots", "rugged sneakers"],
            "accessories": ["cap", "none"],
            "silhouette": "sturdy relaxed",
        },
    },
    "caregiver": {
        "workwear": {
            "tops": ["clean scrub top", "soft care tunic", "light knit top"],
            "bottoms": ["straight care pants", "scrub pants", "easy work trousers"],
            "outers": ["cardigan", "light care jacket", "none"],
            "shoes": ["supportive sneakers", "closed work shoes"],
            "accessories": ["name badge", "none"],
            "silhouette": "soft and functional",
        },
        "off_duty": {
            "tops": ["soft hoodie", "knit top", "cotton shirt"],
            "bottoms": ["easy trousers", "straight denim", "relaxed slacks"],
            "outers": ["cardigan", "none"],
            "shoes": ["clean sneakers", "flats"],
            "accessories": ["tote bag", "none"],
            "silhouette": "soft relaxed",
        },
    },
    # Additional profession names are resolved through PROFESSION_ALIAS_LIBRARY below.
}

# Simple aliases share fuller profiles.
PROFESSION_ALIAS_LIBRARY = {
    "builder": "carpenter",
    "construction worker": "carpenter",
    "woodworker": "carpenter",
    "plumber": "electrician",
    "welder": "mechanic",
    "roofer": "carpenter",
    "painter": "carpenter",
    "landscaper": "farmer",
    "gardener": "farmer",
    "technician": "mechanic",
    "maintenance worker": "mechanic",
    "factory worker": "warehouse worker",
    "driver": "delivery driver",
    "courier": "delivery driver",
    "warehouse staff": "warehouse worker",
    "doctor": "nurse",
    "pharmacist": "scientist",
    "dentist": "nurse",
    "therapist": "caregiver",
    "researcher": "scientist",
    "lab technician": "scientist",
    "cook": "chef",
    "baker": "chef",
    "pastry chef": "chef",
    "bartender": "barista",
    "waiter": "retail staff",
    "server": "retail staff",
    "professor": "teacher",
    "daycare worker": "teacher",
    "childcare worker": "teacher",
    "nanny": "caregiver",
    "shop staff": "retail staff",
    "store clerk": "retail staff",
    "cashier": "retail staff",
    "salesperson": "retail staff",
    "engineer": "office worker",
    "programmer": "office worker",
    "developer": "office worker",
    "designer": "office worker",
    "writer": "office worker",
    "editor": "office worker",
    "accountant": "office worker",
    "banker": "office worker",
    "consultant": "office worker",
    "architect": "office worker",
    "police": "police officer",
    "guard": "security guard",
    "soldier": "police officer",
    "military": "police officer",
    "videographer": "photographer",
    "filmmaker": "photographer",
    "journalist": "photographer",
    "reporter": "photographer",
    "illustrator": "artist",
    "musician": "artist",
}
for alias, target in PROFESSION_ALIAS_LIBRARY.items():
    if target in PROFESSION_LIBRARY:
        PROFESSION_LIBRARY[alias] = json.loads(json.dumps(PROFESSION_LIBRARY[target]))


def _normalize_profession_token(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").replace("-", " ").split())


def _load_external_profession_data():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    catalog_path = data_dir / "profession_catalog_1000.json"
    archetype_path = data_dir / "profession_archetypes.json"
    if not catalog_path.exists() or not archetype_path.exists():
        return None, None
    try:
        catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        archetype_data = json.loads(archetype_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    profession_library = {}
    profession_index = {}
    archetypes = archetype_data.get("archetypes", {})
    for entry in catalog_data.get("professions", []):
        key = entry.get("key", "").strip()
        archetype = entry.get("archetype", "").strip()
        pack = archetypes.get(archetype)
        if not key or not pack:
            continue
        profession_library[key] = pack
        terms = [key, entry.get("label_en", ""), entry.get("label_ja", "")] + entry.get("aliases", []) + entry.get("aliases_ja", [])
        for term in terms:
            token = _normalize_profession_token(term)
            if token:
                profession_index[token] = key
    return profession_library, profession_index




def _load_external_profession_archetype_map():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    catalog_path = data_dir / "profession_catalog_1000.json"
    if not catalog_path.exists():
        return {}
    try:
        catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    result = {}
    for entry in catalog_data.get("professions", []):
        key = str(entry.get("key", "") or "").strip()
        archetype = str(entry.get("archetype", "") or "").strip().lower()
        if key and archetype:
            result[key] = archetype
    return result

_EXTERNAL_PROFESSION_LIBRARY, _EXTERNAL_PROFESSION_INDEX = _load_external_profession_data()
if _EXTERNAL_PROFESSION_LIBRARY:
    PROFESSION_LIBRARY.update(_EXTERNAL_PROFESSION_LIBRARY)
else:
    _EXTERNAL_PROFESSION_INDEX = {}

_EXTERNAL_PROFESSION_ARCHETYPE_MAP = _load_external_profession_archetype_map()

PROFESSION_OPTIONS = sorted({*PROFESSION_LIBRARY.keys(), *PROFESSION_ALIAS_LIBRARY.keys()})


SEASON_COLOR_LIBRARY = {
    "spring": ["off-white", "light gray", "soft blue", "sage green", "beige"],
    "summer": ["white", "sand beige", "light blue", "charcoal", "olive"],
    "autumn": ["brown", "charcoal", "deep olive", "navy", "cream"],
    "winter": ["black", "charcoal", "dark navy", "deep brown", "cold gray"],
}

SHOE_MATERIAL_BY_TYPE = {
    "sneakers": "canvas and rubber",
    "low-top sneakers": "canvas and rubber",
    "high-top sneakers": "canvas and rubber",
    "chunky sneakers": "mesh and synthetic leather",
    "skate shoes": "suede and rubber",
    "leather loafers": "smooth leather",
    "plain-toe leather shoes": "polished leather",
    "side-gore dress boots": "smooth leather",
    "technical sneakers": "matte nylon and rubber",
    "combat boots": "matte leather",
    "trail shoes": "mesh and rubber",
    "hiking boots": "water-resistant leather",
    "rugged sneakers": "mesh and suede",
    "leather boots": "matte leather",
    "minimal sneakers": "smooth leather",
    "sleek loafers": "smooth leather",
    "work boots": "thick leather and rubber",
    "lace-up work boots": "thick leather and rubber",
    "safety-toe work boots": "reinforced leather and rubber",
    "rugged high-top work shoes": "reinforced leather and rubber",
    "protective work boots": "reinforced leather and rubber",
    "slip-resistant kitchen shoes": "synthetic leather and rubber",
    "supportive work sneakers": "mesh and rubber",
    "closed medical shoes": "synthetic leather",
    "black duty shoes": "polished leather",
    "polished duty boots": "polished leather and rubber",
    "mud-resistant work boots": "rubber and reinforced synthetic",
    "rubber work boots": "rubber",
    "rugged field shoes": "rubber and matte synthetic",
    "supportive walking sneakers": "mesh and rubber",
    "durable work sneakers": "synthetic leather and rubber",
    "slip-resistant shoes": "synthetic leather and rubber",
    "protective sneakers": "reinforced mesh and rubber",
    "comfortable flats": "synthetic leather",
    "slip-resistant sneakers": "mesh and rubber",
    "work clogs": "rubberized synthetic",
    "closed lab shoes": "synthetic leather",
    "duty boots": "polished leather and rubber",
    "polished patrol boots": "polished leather and rubber",
    "station boots": "thick leather and rubber",
    "supportive sneakers": "mesh and rubber",
}


COLOR_TRANSLATIONS = {
    "black": "黒",
    "white": "白",
    "gray": "グレー",
    "grey": "グレー",
    "light gray": "ライトグレー",
    "dark gray": "ダークグレー",
    "charcoal": "チャコール",
    "navy": "ネイビー",
    "dark navy": "ダークネイビー",
    "blue": "青",
    "light blue": "ライトブルー",
    "soft blue": "ソフトブルー",
    "brown": "茶色",
    "deep brown": "ダークブラウン",
    "beige": "ベージュ",
    "sand beige": "サンドベージュ",
    "cream": "クリーム色",
    "off-white": "オフホワイト",
    "olive": "オリーブ",
    "deep olive": "ダークオリーブ",
    "sage green": "セージグリーン",
    "green": "緑",
    "khaki": "カーキ",
    "pink": "ピンク",
    "red": "赤",
    "burgundy": "バーガンディ",
    "orange": "オレンジ",
    "yellow": "黄色",
    "gold": "ゴールド",
    "silver": "シルバー",
    "cold gray": "クールグレー",
    "faded olive": "くすんだオリーブ",
}

EN_JA_REPLACEMENTS = {
    "safety-toe work boots": "安全先芯入りワークブーツ",
    "high-top work shoes": "ハイカットワークシューズ",
    "supportive work sneakers": "サポート性の高いワークスニーカー",
    "closed medical shoes": "つま先まで覆われた医療用シューズ",
    "slip-resistant kitchen shoes": "滑りにくいキッチンシューズ",
    "plain-toe leather shoes": "プレーントゥのレザーシューズ",
    "side-gore dress boots": "サイドゴアのドレスブーツ",
    "double-breasted chef jacket": "ダブル仕立てのシェフジャケット",
    "short-sleeve chef coat": "半袖のシェフコート",
    "check kitchen trousers": "チェック柄のキッチントラウザー",
    "heavy-duty duck canvas pants": "丈夫なダックキャンバスパンツ",
    "canvas chore jacket": "キャンバスのチョアジャケット",
    "heavy flannel work shirt": "厚手のフランネルワークシャツ",
    "rugged pullover hoodie": "無骨なプルオーバーフーディー",
    "reinforced canvas work jacket": "補強入りのキャンバスワークジャケット",
    "long-sleeve work tee": "長袖ワークTシャツ",
    "straight work denim": "ストレートのワークデニム",
    "weathered work vest": "使い込まれたワークベスト",
    "hooded work jacket": "フード付きワークジャケット",
    "lace-up work boots": "レースアップのワークブーツ",
    "rugged high-top work shoes": "無骨なハイカットの作業靴",
    "supportive walking sneakers": "サポート性のあるウォーキングスニーカー",
    "durable work sneakers": "耐久性のあるワークスニーカー",
    "closed lab shoes": "ラボ向けの閉じたシューズ",
    "polished patrol boots": "磨かれたパトロールブーツ",
    "name badge": "ネームバッジ",
    "crossbody gear bag": "クロスボディのギアバッグ",
    "structured duty shirt": "構築的なデューティーシャツ",
    "security uniform shirt": "警備制服シャツ",
    "uniform trousers": "制服用トラウザー",
    "duty jacket": "デューティージャケット",
    "duty belt": "デューティーベルト",
    "scrub top": "スクラブトップ",
    "scrub pants": "スクラブパンツ",
    "medical tunic": "メディカルチュニック",
    "medical pants": "メディカルパンツ",
    "work sneakers": "ワークスニーカー",
    "work shoes": "作業靴",
    "work boots": "ワークブーツ",
    "technical sneakers": "テクニカルスニーカー",
    "combat boots": "コンバットブーツ",
    "trail shoes": "トレイルシューズ",
    "hiking boots": "ハイキングブーツ",
    "rugged sneakers": "ラギッドスニーカー",
    "minimal sneakers": "ミニマルスニーカー",
    "sleek loafers": "すっきりしたローファー",
    "dress shoes": "ドレスシューズ",
    "leather loafers": "レザーローファー",
    "clean leather flats": "クリーンなレザーフラット",
    "low block-heel shoes": "低めブロックヒールの靴",
    "work clogs": "ワーククロッグ",
    "plain tee": "無地のTシャツ",
    "dark work tee": "ダークカラーのワークTシャツ",
    "graphic sweatshirt": "グラフィックスウェット",
    "boxy long-sleeve shirt": "ボクシーな長袖シャツ",
    "oversized hoodie": "オーバーサイズフーディー",
    "soft hoodie": "ソフトなフーディー",
    "zip hoodie": "ジップフーディー",
    "hoodie": "フーディー",
    "henley shirt": "ヘンリーシャツ",
    "dress shirt": "ドレスシャツ",
    "work shirt": "ワークシャツ",
    "utility shirt": "ユーティリティシャツ",
    "cotton shirt": "コットンシャツ",
    "button-up shirt": "ボタンアップシャツ",
    "overshirt": "オーバーシャツ",
    "flannel shirt": "フランネルシャツ",
    "polo shirt": "ポロシャツ",
    "blouse": "ブラウス",
    "tunic": "チュニック",
    "tee": "Tシャツ",
    "t-shirt": "Tシャツ",
    "shirt": "シャツ",
    "fine-gauge knit": "ハイゲージニット",
    "relaxed knit sweater": "リラックスしたニットセーター",
    "light cardigan": "ライトカーディガン",
    "cardigan": "カーディガン",
    "tailored jacket": "テーラードジャケット",
    "denim jacket": "デニムジャケット",
    "shell jacket": "シェルジャケット",
    "light jacket": "ライトジャケット",
    "work jacket": "ワークジャケット",
    "shop jacket": "ショップジャケット",
    "garage jacket": "ガレージジャケット",
    "jacket": "ジャケット",
    "coat": "コート",
    "parka": "パーカー",
    "blazer": "ブレザー",
    "vest": "ベスト",
    "apron": "エプロン",
    "work trousers": "ワークトラウザー",
    "straight trousers": "ストレートトラウザー",
    "utility trousers": "ユーティリティトラウザー",
    "office trousers": "オフィストラウザー",
    "straight denim pants": "ストレートデニムパンツ",
    "baggy denim pants": "バギーデニムパンツ",
    "denim pants": "デニムパンツ",
    "work chinos": "ワークチノ",
    "easy chinos": "イージーチノ",
    "cargo pants": "カーゴパンツ",
    "utility pants": "ユーティリティパンツ",
    "tapered utility pants": "テーパードユーティリティパンツ",
    "technical cargo pants": "テクニカルカーゴパンツ",
    "wide cargo pants": "ワイドカーゴパンツ",
    "carpenter pants": "カーペンターパンツ",
    "scrub pants": "スクラブパンツ",
    "pants": "パンツ",
    "trousers": "トラウザー",
    "slacks": "スラックス",
    "skirt": "スカート",
    "pencil skirt": "ペンシルスカート",
    "ankle trousers": "アンクルトラウザー",
    "loafers": "ローファー",
    "sneakers": "スニーカー",
    "boots": "ブーツ",
    "shoes": "シューズ",
    "belt": "ベルト",
    "bag": "バッグ",
    "backpack": "バックパック",
    "sling bag": "スリングバッグ",
    "crossbody": "クロスボディ",
    "shoulder bag": "ショルダーバッグ",
    "tote bag": "トートバッグ",
    "watch": "腕時計",
    "necklace": "ネックレス",
    "ring": "リング",
    "beanie": "ビーニー",
    "cap": "キャップ",
    "hat": "帽子",
    "badge": "バッジ",
    "canvas and rubber": "キャンバスとラバー",
    "mesh and synthetic leather": "メッシュと合成皮革",
    "suede and rubber": "スエードとラバー",
    "smooth leather": "スムースレザー",
    "polished leather": "磨かれたレザー",
    "matte nylon and rubber": "マットナイロンとラバー",
    "matte leather": "マットレザー",
    "mesh and rubber": "メッシュとラバー",
    "thick leather and rubber": "厚手レザーとラバー",
    "reinforced leather and rubber": "補強レザーとラバー",
    "synthetic leather and rubber": "合成皮革とラバー",
    "synthetic leather": "合成皮革",
    "rubber and reinforced synthetic": "ラバーと補強合成素材",
    "rubber and matte synthetic": "ラバーとマット合成素材",
    "rubber": "ラバー",
    "canvas": "キャンバス",
    "denim": "デニム",
    "flannel": "フランネル",
    "cotton": "コットン",
    "wool": "ウール",
    "nylon": "ナイロン",
    "leather": "レザー",
    "suede": "スエード",
    "mesh": "メッシュ",
    "synthetic": "合成素材",
    "heavy-duty": "ヘビーデューティーな",
    "heavy": "厚手の",
    "lightweight": "軽量の",
    "light": "ライトな",
    "dark": "ダークな",
    "clean": "クリーンな",
    "reinforced": "補強入りの",
    "rugged": "ラギッドな",
    "structured": "構築的な",
    "straight": "ストレートの",
    "tailored": "テーラードの",
    "relaxed": "リラックスした",
    "supportive": "サポート性のある",
    "protective": "保護性のある",
    "slip-resistant": "滑りにくい",
    "polished": "磨かれた",
    "technical": "テクニカルな",
    "utility": "ユーティリティの",
    "breathable": "通気性のある",
    "weathered": "使い込まれた",
    "washed": "ウォッシュド",
    "faded": "色落ちした",
    "quick-dry": "速乾性のある",
    "durable": "耐久性のある",
    "practical with room for movement": "実用的で動きやすいシルエット",
    "compact and work-ready": "コンパクトで作業向きのシルエット",
    "clean and practical": "クリーンで実用的なシルエット",
    "clean and easy to move in": "クリーンで動きやすいシルエット",
    "clean functional": "クリーンで機能的なシルエット",
    "tidy and approachable": "整っていて親しみやすいシルエット",
    "clean and controlled": "整って制御されたシルエット",
    "mobile and layered": "動きやすくレイヤードしやすいシルエット",
    "clean and authoritative": "整っていて威圧感のあるシルエット",
    "practical and sun-ready": "実用的で日差しに備えたシルエット",
    "slightly relaxed": "ややリラックスしたシルエット",
    "loose": "ゆったりしたシルエット",
    "functional layered": "機能的なレイヤードシルエット",
    "clean": "整ったシルエット",
    "workwear": "仕事着",
    "off duty": "私服寄り",
    "generic": "汎用",
    "profession-first": "職業優先",
    "style-first": "スタイル優先",
    "work": "仕事",
    "practical condition with visible use": "実用的で使用感のある状態",
    "clean with light wear": "軽い使用感のある清潔な状態",
    "matched to the profession": "職業に合った仕様",
    "balanced with the outfit silhouette": "服装シルエットとのバランスを取った仕様",
}


class LLMOutfitGeneratorNode:
    CATEGORY = "text"
    FUNCTION = "generate_outfit"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("outfit_description", "outfit_tags", "outfit_json", "save_name_out", "outfit_json_path")
    OUTPUT_NODE = False

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "gender_mode": (RANDOM_MODE_OPTIONS, {"default": "input"}),
                "gender": ("STRING", {"default": "", "multiline": False}),
                "season_mode": (RANDOM_MODE_OPTIONS, {"default": "input"}),
                "season": ("STRING", {"default": "", "multiline": False}),
                "style_mode": (RANDOM_MODE_OPTIONS, {"default": "input"}),
                "style": ("STRING", {"default": "", "multiline": False}),
                "profession_mode_select": (RANDOM_MODE_OPTIONS, {"default": "input"}),
                "profession": ("STRING", {"default": "", "multiline": False}),
                "mood": ("STRING", {"default": "", "multiline": True}),
                "age_range": ("STRING", {"default": "", "multiline": False}),
                "avoid_items": ("STRING", {"default": "", "multiline": True}),
                "outerwear_mode": (["auto", "none", "input"], {"default": "auto"}),
                "outerwear_type": ("STRING", {"default": "", "multiline": False}),
                "socks_mode": (["auto", "none", "random"], {"default": "auto"}),
                "shoe_mode": (["auto", "random", "input", "none"], {"default": "auto"}),
                "include_shoes": (["auto", "yes", "no"], {"default": "auto"}),
                "shoe_type": ("STRING", {"default": "", "multiline": False}),
                "shoe_avoid": ("STRING", {"default": "", "multiline": True}),
                "randomness": ("INT", {"default": 50, "min": 0, "max": 100, "step": 1}),
                "detail_strength": ("INT", {"default": 65, "min": 0, "max": 100, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0x7FFFFFFF, "step": 1}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "save_dir": ("STRING", {"default": "./llm_outfit_outputs", "multiline": False}),
                "save_name": ("STRING", {"default": "", "multiline": False}),
                "model_path": ("STRING", {"default": "", "multiline": False}),
                "load_strategy": (["keep_loaded", "reload_every_run"], {"default": "reload_every_run"}),
                "max_tokens": ("INT", {"default": 896, "min": 128, "max": 8192, "step": 64}),
                "temperature": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 2.0, "step": 0.05}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _is_blank(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip().lower() in UNSPECIFIED_VALUES
        if isinstance(value, (list, tuple, set)):
            return len(value) == 0
        if isinstance(value, dict):
            return len(value) == 0
        return False

    def _split_items(self, text: str) -> list[str]:
        if self._is_blank(text):
            return []
        raw = str(text).replace("\n", ",")
        parts = []
        for item in raw.split(","):
            cleaned = item.strip()
            if cleaned:
                parts.append(cleaned)
        return parts

    def _clean_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if self._is_blank(value):
                continue
            if isinstance(value, dict):
                nested = self._clean_payload(value)
                if nested:
                    result[key] = nested
                continue
            if isinstance(value, list):
                filtered = [item for item in value if not self._is_blank(item)]
                if filtered:
                    result[key] = filtered
                continue
            if isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    result[key] = cleaned
                continue
            result[key] = value
        return result

    def _resolve_random_basis(self, mode: str, value: str, options: list[str], rng: random.Random, fallback: str = "") -> str:
        selected_mode = (mode or "input").strip().lower()
        if selected_mode == "random":
            pool = [str(x).strip() for x in options if str(x).strip()]
            if pool:
                return rng.choice(pool)
            return fallback
        return str(value or "").strip()

    def _style_key(self, style: str) -> str:
        s = (style or "").strip().lower()
        if not s:
            return ""
        for key in STYLE_LIBRARY.keys():
            if key in s:
                return key
        return "casual"

    def _season_key(self, season: str) -> str:
        s = (season or "").strip().lower()
        for key in SEASON_COLOR_LIBRARY.keys():
            if key in s:
                return key
        return "autumn"

    def _normalize_profession(self, profession: str) -> str:
        raw = (profession or "").strip()
        p = _normalize_profession_token(raw)
        if not p:
            return ""
        if p in _EXTERNAL_PROFESSION_INDEX:
            return _EXTERNAL_PROFESSION_INDEX[p]
        aliases = {
            "大工": "carpenter",
            "木工": "cabinet_maker",
            "建設作業員": "construction_worker",
            "整備士": "fleet_technician",
            "電気工事士": "electrician",
            "配管工": "plumber",
            "シェフ": "chef",
            "料理人": "cook",
            "看護師": "nurse",
            "医師": "doctor",
            "教師": "teacher",
            "先生": "teacher",
            "会社員": "office_worker",
            "事務職": "office_worker",
            "カメラマン": "photographer",
            "写真家": "photographer",
            "警備員": "security_guard",
            "エンジニア": "project_manager",
            "プログラマー": "data_analyst",
            "デザイナー": "graphic_designer",
            "農家": "farmer",
            "酪農家": "dairyman",
            "配達員": "delivery_driver",
            "宅配": "courier",
            "倉庫作業員": "warehouse_worker",
            "物流": "logistics_coordinator",
            "販売員": "retail_staff",
            "店員": "retail_staff",
            "バリスタ": "barista",
            "アーティスト": "illustrator",
            "画家": "graphic_designer",
            "科学者": "scientist",
            "研究者": "researcher",
            "警察官": "police_officer",
            "消防士": "firefighter",
            "介護士": "caregiver",
            "介護職": "caregiver",
            "薬剤師": "pharmacist",
            "歯科医": "dentist",
            "療法士": "therapist",
            "整備工": "fleet_technician",
            "技術者": "lab_technician",
            "溶接工": "welder",
            "左官": "plasterer",
            "庭師": "gardener",
            "ウェイター": "waiter",
            "接客": "retail_staff",
            "パン職人": "baker",
            "映像作家": "filmmaker",
            "映像撮影": "videographer",
            "記者": "reporter",
            "編集者": "editor",
            "作家": "writer",
            "会計士": "accountant",
            "銀行員": "banker",
            "建築士": "project_manager",
        }
        direct = aliases.get(raw) or aliases.get(p)
        if direct:
            return direct
        raw_lower = raw.lower()
        if raw_lower in PROFESSION_LIBRARY:
            return raw_lower
        if p in PROFESSION_LIBRARY:
            return p
        return p

    def _gender_profile_key(self, gender: str) -> str:
        g = (gender or "").strip().lower()
        if any(token in g for token in ["female", "woman", "girl", "women", "feminine", "女", "女性"]):
            return "feminine"
        if any(token in g for token in ["male", "man", "boy", "men", "masculine", "男", "男性"]):
            return "masculine"
        return "neutral"

    def _gender_keywords(self, category: str, gender_key: str) -> tuple[list[str], list[str]]:
        feminine = {
            "top": ["blouse", "camisole", "fitted knit", "cropped knit", "cropped tee", "cardigan"],
            "bottom": ["skirt", "mini", "midi", "pleated", "long skirt"],
            "outer": ["cropped jacket", "cardigan", "trench", "long coat"],
            "shoes": ["pumps", "flats", "mary jane", "heel", "ankle boots"],
            "accessories": ["earrings", "hair", "necklace", "bracelet", "small bag"],
        }
        masculine = {
            "top": ["oxford", "work shirt", "hoodie", "sweatshirt", "polo", "overshirt"],
            "bottom": ["cargo", "trousers", "slacks", "jeans", "work pants"],
            "outer": ["bomber", "utility", "work jacket", "blazer", "puffer"],
            "shoes": ["loafers", "dress shoes", "boots", "derby", "sneakers"],
            "accessories": ["watch", "belt", "backpack", "cap"],
        }
        if gender_key == "feminine":
            return feminine.get(category, []), masculine.get(category, [])
        if gender_key == "masculine":
            return masculine.get(category, []), feminine.get(category, [])
        return [], []

    def _season_keywords(self, category: str, season_key: str) -> tuple[list[str], list[str]]:
        season_preferences = {
            "spring": {
                "top": ["shirt", "blouse", "light knit", "cardigan"],
                "bottom": ["light trousers", "pleated skirt", "jeans"],
                "outer": ["cardigan", "light jacket", "trench"],
                "shoes": ["loafers", "sneakers", "flats"],
            },
            "summer": {
                "top": ["tee", "t-shirt", "shirt", "polo", "camisole"],
                "bottom": ["shorts", "light trousers", "skirt"],
                "outer": ["none", "light overshirt", "thin shirt"],
                "shoes": ["sandals", "loafers", "canvas sneakers", "light sneakers"],
            },
            "autumn": {
                "top": ["knit", "shirt", "hoodie", "sweater"],
                "bottom": ["trousers", "jeans", "cargo"],
                "outer": ["jacket", "trench", "coat", "overshirt"],
                "shoes": ["boots", "loafers", "sneakers"],
            },
            "winter": {
                "top": ["knit", "sweater", "turtleneck", "thermal"],
                "bottom": ["wool", "heavy trousers", "lined pants"],
                "outer": ["coat", "puffer", "parka", "down", "wool"],
                "shoes": ["boots", "leather shoes", "high-top"],
            },
        }
        season_avoids = {
            "spring": {"outer": ["down", "parka"], "shoes": ["snow"]},
            "summer": {"top": ["heavy knit", "turtleneck"], "outer": ["coat", "puffer", "parka", "down", "wool"], "shoes": ["boots", "fur"]},
            "autumn": {"shoes": ["snow"]},
            "winter": {"top": ["camisole"], "outer": ["thin shirt"], "shoes": ["sandals"]},
        }
        prefer = season_preferences.get(season_key, {}).get(category, [])
        avoid = season_avoids.get(season_key, {}).get(category, [])
        return prefer, avoid

    def _score_structured_item(self, item: str, category: str, gender_key: str, season_key: str) -> int:
        text = str(item or "").strip().lower()
        if not text:
            return -999
        score = 0
        gender_prefer, gender_avoid = self._gender_keywords(category, gender_key)
        season_prefer, season_avoid = self._season_keywords(category, season_key)
        for keyword in gender_prefer:
            if keyword in text:
                score += 3
        for keyword in gender_avoid:
            if keyword in text:
                score -= 2
        for keyword in season_prefer:
            if keyword in text:
                score += 3
        for keyword in season_avoid:
            if keyword in text:
                score -= 4
        return score

    def _pick_structured(self, rng: random.Random, options: list[str], avoid: list[str], category: str, gender_key: str, season_key: str) -> str:
        normalized_avoid = [a.lower() for a in avoid if a]
        filtered = [opt for opt in options if all(a not in str(opt).lower() for a in normalized_avoid)]
        pool = filtered or list(options)
        if not pool:
            return ""
        scored = sorted(((opt, self._score_structured_item(opt, category, gender_key, season_key)) for opt in pool), key=lambda x: x[1], reverse=True)
        best_score = scored[0][1]
        candidates = [opt for opt, score in scored if score >= best_score - 1]
        return rng.choice(candidates or pool)

    def _pick(self, rng: random.Random, options: list[str], avoid: list[str]) -> str:
        normalized_avoid = [a.lower() for a in avoid]
        filtered = [opt for opt in options if all(a not in opt.lower() for a in normalized_avoid)]
        pool = filtered or options
        return rng.choice(pool) if pool else ""

    def _blend_options(self, base: list[str], style: list[str], strength: float) -> list[str]:
        if strength <= 0:
            return list(base)
        take = max(1, min(len(style), round(len(style) * strength)))
        return list(dict.fromkeys(list(base) + style[:take]))

    def _enforce_payload_outfit(self, generated_outfit: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        enforced = self._clean_payload(dict(generated_outfit or {}))
        payload_clean = self._clean_payload(dict(payload or {}))
        profession_first = payload_clean.get("generation_priority") == "profession-first"
        profession_mode = str(payload_clean.get("profession_mode", "")).strip().lower()
        if not profession_first:
            return enforced or payload_clean

        core_keys = [
            "style",
            "season",
            "mood",
            "gender",
            "age_range",
            "profession",
            "profession_mode",
            "generation_priority",
            "top",
            "bottom",
            "outer",
            "socks",
            "shoes",
            "accessories",
            "color_scheme",
            "part_colors",
            "silhouette",
            "detail_strength",
            "randomness",
            "include_shoes",
        ]
        if profession_mode == "workwear":
            return self._clean_payload({key: payload_clean.get(key) for key in core_keys if key in payload_clean})

        for key in ["top", "bottom", "shoes", "profession", "profession_mode", "generation_priority"]:
            if key in payload_clean:
                enforced[key] = payload_clean.get(key)
        if not enforced.get("outer") and payload_clean.get("outer"):
            enforced["outer"] = payload_clean.get("outer")
        if not enforced.get("accessories") and payload_clean.get("accessories"):
            enforced["accessories"] = payload_clean.get("accessories")
        if not enforced.get("color_scheme") and payload_clean.get("color_scheme"):
            enforced["color_scheme"] = payload_clean.get("color_scheme")
        if not enforced.get("silhouette") and payload_clean.get("silhouette"):
            enforced["silhouette"] = payload_clean.get("silhouette")
        return self._clean_payload(enforced)

    def _should_include_shoes(self, include_shoes: str, shoe_mode: str = "auto") -> bool:
        mode = (shoe_mode or "auto").strip().lower()
        if mode == "none":
            return False
        value = (include_shoes or "auto").strip().lower()
        if value == "no":
            return False
        return True

    def _profession_archetype(self, profession_key: str) -> str:
        if not profession_key:
            return ""
        external_archetype = _EXTERNAL_PROFESSION_ARCHETYPE_MAP.get(profession_key)
        if external_archetype:
            return str(external_archetype).strip().lower()
        if profession_key in PROFESSION_LIBRARY:
            return profession_key
        return ""

    def _build_sock_pool(self, style_key: str, season_key: str, profession_key: str = "") -> list[str]:
        archetype = self._profession_archetype(profession_key)
        if archetype in {"fantasy_adventure", "fantasy_magic", "fantasy_royal", "fantasy_craft"}:
            return []
        if archetype in {"office_clean", "hospitality_host"}:
            return ["dress socks", "fine rib socks", "dark dress socks"]
        if archetype in {"bar_service", "retail_service"}:
            return ["dark dress socks", "fine rib socks", "minimal socks"]
        if archetype == "medical_clean":
            return ["soft knit socks", "light compression socks", "clean ankle socks"]
        if archetype in {"construction_workwear", "field_outdoor"}:
            return ["hiking socks", "merino crew socks", "thick work socks"]
        if archetype in {"sci_fi_field", "sci_fi_command", "sci_fi_tech", "media_mobile"}:
            return ["technical socks", "performance crew socks", "minimal socks"]
        base = {
            "spring": ["ankle socks", "ribbed crew socks", "light socks"],
            "summer": ["no-show socks", "thin ankle socks", "light crew socks"],
            "autumn": ["crew socks", "ribbed socks", "soft knit socks"],
            "winter": ["thermal socks", "wool-blend socks", "thick crew socks"],
        }.get(season_key, ["crew socks"])
        style_bonus = {
            "formal": ["dress socks", "fine rib socks"],
            "street": ["sports crew socks", "logo crew socks"],
            "techwear": ["technical socks", "performance crew socks"],
            "outdoor": ["hiking socks", "merino crew socks"],
            "mode": ["fine rib socks", "minimal socks"],
            "casual": ["cotton crew socks", "ankle socks"],
        }.get(style_key, ["cotton crew socks"])
        return list(dict.fromkeys(base + style_bonus))

    def _profession_pack(self, profession_key: str) -> dict[str, Any] | None:
        if not profession_key:
            return None
        profile = PROFESSION_LIBRARY.get(profession_key)
        if not profile:
            return None
        return profile.get("workwear") or profile.get("off_duty")

    def _build_base_profile(
        self,
        gender_mode,
        gender,
        season_mode,
        season,
        style_mode,
        style,
        mood,
        age_range,
        profession_mode_select,
        profession,
        avoid_items,
        outerwear_mode,
        outerwear_type,
        socks_mode,
        shoe_mode,
        include_shoes,
        shoe_type,
        shoe_avoid,
        randomness,
        detail_strength,
        seed,
    ) -> dict[str, Any]:
        pre_rng = random.Random(int(seed))
        resolved_gender = self._resolve_random_basis(gender_mode, gender, GENDER_OPTIONS, pre_rng)
        resolved_season = self._resolve_random_basis(season_mode, season, SEASON_OPTIONS, pre_rng, "autumn")
        resolved_style = self._resolve_random_basis(style_mode, style, STYLE_OPTIONS, pre_rng, "casual")
        resolved_profession = self._resolve_random_basis(profession_mode_select, profession, PROFESSION_OPTIONS, pre_rng)

        style_key = self._style_key(resolved_style)
        season_key = self._season_key(resolved_season)
        profession_key = self._normalize_profession(resolved_profession)
        gender_key = self._gender_profile_key(resolved_gender)
        rng_seed = int(seed) + sum(ord(c) for c in f"{resolved_gender}|{season_key}|{style_key}|{profession_key}|{mood}|{age_range}")
        rng = random.Random(rng_seed)
        style_provided = not self._is_blank(style_key)
        style_pack = STYLE_LIBRARY.get(style_key, STYLE_LIBRARY["casual"]) if style_provided else None
        profession_pack = self._profession_pack(profession_key)
        avoid = self._split_items(avoid_items) + self._split_items(shoe_avoid)
        preferred_colors = []
        part_colors = {}
        season_colors = SEASON_COLOR_LIBRARY.get(season_key, SEASON_COLOR_LIBRARY["autumn"])
        palette = []

        if profession_pack:
            tops = list(profession_pack["tops"])
            bottoms = list(profession_pack["bottoms"])
            outers = list(profession_pack["outers"])
            shoes_pool = list(profession_pack["shoes"])
            accessories_pool = list(profession_pack["accessories"])
            silhouette = profession_pack["silhouette"]
        else:
            tops = style_pack["tops"] if style_pack else STYLE_LIBRARY["casual"]["tops"]
            bottoms = style_pack["bottoms"] if style_pack else STYLE_LIBRARY["casual"]["bottoms"]
            outers = style_pack["outers"] if style_pack else STYLE_LIBRARY["casual"]["outers"]
            shoes_pool = style_pack["shoes"] if style_pack else STYLE_LIBRARY["casual"]["shoes"]
            accessories_pool = style_pack["accessories"] if style_pack else STYLE_LIBRARY["casual"]["accessories"]
            silhouette = style_pack["silhouette"] if style_pack else STYLE_LIBRARY["casual"]["silhouette"]

        top = self._pick_structured(rng, tops, avoid, "top", gender_key, season_key)
        bottom = self._pick_structured(rng, bottoms, avoid, "bottom", gender_key, season_key)
        if str(outerwear_mode or "auto").strip().lower() == "none":
            outer = ""
        elif str(outerwear_mode or "auto").strip().lower() == "input":
            outer = str(outerwear_type or "").strip()
        else:
            outer = self._pick_structured(rng, outers, avoid, "outer", gender_key, season_key)
        accessory = self._pick_structured(rng, accessories_pool, avoid, "accessories", gender_key, season_key)

        if str(shoe_mode or "auto").strip().lower() == "input" and not self._is_blank(shoe_type):
            selected_shoe_type = str(shoe_type).strip()
        else:
            selected_shoe_type = self._pick_structured(rng, shoes_pool, avoid, "shoes", gender_key, season_key)

        socks_pool = self._build_sock_pool(style_key, season_key, profession_key)
        selected_socks = ""
        socks_mode_key = str(socks_mode or "auto").strip().lower()
        if socks_mode_key == "none":
            selected_socks = ""
        elif socks_mode_key in {"auto", "random"}:
            selected_socks = self._pick_structured(rng, socks_pool, avoid, "socks", gender_key, season_key)

        selected_shoe_color = ""
        shoe_material = "mixed material"
        for key, material in SHOE_MATERIAL_BY_TYPE.items():
            if key in selected_shoe_type.lower():
                shoe_material = material
                break

        if int(randomness) >= 75 and not profession_pack:
            silhouette = f"{silhouette} with a slightly unexpected accent"
        elif int(detail_strength) >= 75:
            silhouette = f"{silhouette} with clearly readable clothing volume"

        profile = {
            "style": resolved_style if not self._is_blank(resolved_style) else style_key,
            "season": resolved_season if not self._is_blank(resolved_season) else season_key,
            "mood": self._split_items(mood),
            "gender": resolved_gender,
            "age_range": age_range,
            "profession": resolved_profession,
            "basis_modes": {
                "gender": str(gender_mode),
                "season": str(season_mode),
                "style": str(style_mode),
                "profession": str(profession_mode_select),
            },
            "profession_mode": "workwear" if profession_pack else "generic",
            "generation_priority": "profession-first" if profession_pack else "style-first",
            "selection_basis": [value for value in [resolved_gender if not self._is_blank(resolved_gender) else gender_key, resolved_season if not self._is_blank(resolved_season) else season_key, resolved_style if not self._is_blank(resolved_style) else style_key, resolved_profession if not self._is_blank(resolved_profession) else profession_key] if value],
            "top": top,
            "bottom": bottom,
            "outer": "" if outer == "none" else outer,
            "socks": selected_socks,
            "accessories": [] if accessory == "none" else [accessory],
            "color_scheme": palette,
            "part_colors": part_colors,
            "silhouette": silhouette,
            "detail_strength": int(detail_strength),
            "randomness": int(randomness),
            "include_shoes": str(include_shoes),
            "outerwear_mode": str(outerwear_mode),
            "socks_mode": str(socks_mode),
            "shoe_mode": str(shoe_mode),
        }

        if self._should_include_shoes(include_shoes, shoe_mode):
            shoe_detail = "matched to the profession" if profession_pack else "balanced with the outfit silhouette"
            profile["shoes"] = {
                "type": selected_shoe_type,
                "color": selected_shoe_color,
                "material": shoe_material,
                "condition": "practical condition with visible use" if profession_pack else "clean with light wear",
                "details": [shoe_detail],
            }
        else:
            profile["shoes"] = None

        return self._clean_payload(profile)

    def _build_instruction(self, payload: dict[str, Any], language: str) -> str:
        lang = normalize_output_language(language)
        schema = {
            "outfit_description": "one compact paragraph describing visible outfit details only",
            "outfit_tags": ["short tags only"],
            "outfit": {
                "style": "string if provided or decided",
                "season": "string if provided or decided",
                "top": "string",
                "bottom": "string",
                "outer": "string if present",
                "socks": "string if present",
                "shoes": {
                    "type": "string",
                    "color": "string if intentionally present",
                    "material": "string",
                    "condition": "string",
                    "details": ["strings only"],
                },
                "accessories": ["strings only if present"],
                "color_scheme": ["strings only if intentionally present"],
                "part_colors": {
                    "top": "string if intentionally present",
                    "bottom": "string if intentionally present",
                    "outer": "string if intentionally present",
                    "shoes": "string if intentionally present",
                    "accessories": "string if intentionally present"
                },
                "silhouette": "string",
                "mood": ["strings only if provided"],
                "gender": "string if provided",
                "age_range": "string if provided",
                "profession": "string if provided",
                "profession_mode": "string if present",
                "basis_modes": {
                    "gender": "input or random",
                    "season": "input or random",
                    "style": "input or random",
                    "profession": "input or random"
                },
                "outerwear_mode": "auto or none or input",
                "socks_mode": "auto or none or random",
                "shoe_mode": "auto or random or input or none",
                "generation_priority": "string if present",
            },
            "used_fields": ["names of fields actually used"],
        }
        return (
            f"Output language: {lang}\n"
            f"Language rule: {output_language_instruction(lang, json_mode=True)}\n\n"
            "Task:\n"
            "Generate a visible outfit specification from the provided draft JSON.\n"
            "Treat gender, season, style, and profession as the primary decision basis for clothing and shoes.\n"
            "Do not use or mention omitted fields.\n"
            "Do not replace concrete clothing with vague praise words.\n"
            "Always keep top, bottom, outerwear state, footwear state, and silhouette visible in the result.\n"
            "If profession and profession_mode exist, keep the outfit visibly appropriate to that profession.\n"
            "If generation_priority is profession-first, do not drift into generic casual clothing that ignores the profession.\n"
            "If shoes is null in the input, keep shoes omitted or null in the output and do not mention footwear in the description.\n"
            "If shoes exists in the input, keep it consistent and visible.\n"
            "Do not invent or emphasize colors unless they are intentionally provided in the draft JSON.\n"
            "Return compact, usable output for creative prompt workflows.\n\n"
            f"Provided draft JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            f"Return JSON schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            "Rules:\n"
            "- Return JSON only\n"
            "- No markdown\n"
            "- No comments\n"
            "- Keep keys in English exactly as shown\n"
            "- Write every user-facing value in the requested output language\n"
            "- outfit_tags must be short and concrete\n"
            "- used_fields must list only keys that were actually used\n"
        )

    def _clean_text(self, text: str) -> str:
        cleaned = text or ""
        for token in STOP_TOKENS:
            cleaned = cleaned.replace(token, "")
        return cleaned.strip()

    def _extract_json(self, text: str) -> dict[str, Any]:
        raw = self._clean_text(text)
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start:end + 1])
            raise ValueError("Model did not return valid JSON.")

    def _translate_color_to_japanese(self, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return raw
        lowered = raw.lower()
        for key in sorted(COLOR_TRANSLATIONS.keys(), key=len, reverse=True):
            if lowered == key:
                return COLOR_TRANSLATIONS[key]
        return raw

    def _translate_phrase_to_japanese(self, value: str) -> str:
        raw = (value or "").strip()
        if not raw:
            return raw
        if not any("a" <= ch.lower() <= "z" for ch in raw):
            return raw
        out = raw.lower()
        for key in sorted(EN_JA_REPLACEMENTS.keys(), key=len, reverse=True):
            out = out.replace(key, EN_JA_REPLACEMENTS[key])
        for key in sorted(COLOR_TRANSLATIONS.keys(), key=len, reverse=True):
            out = out.replace(key, COLOR_TRANSLATIONS[key])
        out = out.replace("  ", " ").replace(" ,", ",").strip()
        if " and " in out:
            out = out.replace(" and ", " と ")
        while "  " in out:
            out = out.replace("  ", " ")
        out = out.replace(" な ", "な").replace(" の ", "の")
        return out.strip()

    def _render_colored_item(self, item: str, color: str, language: str) -> str:
        lang = normalize_output_language(language)
        item_text = self._translate_phrase_to_japanese(item) if lang == "Japanese" else (item or "")
        color_text = self._translate_color_to_japanese(color) if lang == "Japanese" else (color or "")
        if not color_text:
            return item_text
        if not item_text:
            return color_text
        if lang == "Japanese":
            return f"{color_text}の{item_text}"
        return f"{color_text} {item_text}".strip()

    def _build_part_colors(self, top_color: str, bottom_color: str, outer_color: str, shoe_color: str, accessory_color: str) -> dict[str, str]:
        part_colors = {}
        for key, value in {
            "top": top_color,
            "bottom": bottom_color,
            "outer": outer_color,
            "shoes": shoe_color,
            "accessories": accessory_color,
        }.items():
            if not self._is_blank(value):
                part_colors[key] = str(value).strip()
        return part_colors

    def _apply_part_colors_to_palette(self, preferred_colors: list[str], part_colors: dict[str, str], season_colors: list[str]) -> list[str]:
        ordered = []
        for value in list(part_colors.values()) + list(preferred_colors):
            cleaned = str(value).strip()
            lowered = cleaned.lower()
            if cleaned and lowered not in [x.lower() for x in ordered]:
                ordered.append(cleaned)
        for value in season_colors:
            if len(ordered) >= 3:
                break
            if value.lower() not in [x.lower() for x in ordered]:
                ordered.append(value)
        return ordered[:3]

    def _localize_outfit_payload(self, outfit: dict[str, Any], language: str) -> dict[str, Any]:
        if normalize_output_language(language) != "Japanese":
            return outfit
        localized = json.loads(json.dumps(outfit, ensure_ascii=False))
        for key in ["style", "season", "profession_mode", "generation_priority", "silhouette", "outerwear_mode", "socks_mode", "shoe_mode"]:
            if isinstance(localized.get(key), str):
                localized[key] = self._translate_phrase_to_japanese(localized[key])
        if isinstance(localized.get("top"), str):
            localized["top"] = self._translate_phrase_to_japanese(localized["top"])
        if isinstance(localized.get("bottom"), str):
            localized["bottom"] = self._translate_phrase_to_japanese(localized["bottom"])
        if isinstance(localized.get("outer"), str):
            localized["outer"] = self._translate_phrase_to_japanese(localized["outer"])
        if isinstance(localized.get("socks"), str):
            localized["socks"] = self._translate_phrase_to_japanese(localized["socks"])
        if isinstance(localized.get("accessories"), list):
            localized["accessories"] = [self._translate_phrase_to_japanese(str(x)) for x in localized["accessories"]]
        if isinstance(localized.get("color_scheme"), list):
            localized["color_scheme"] = [self._translate_color_to_japanese(str(x)) for x in localized["color_scheme"]]
        if isinstance(localized.get("part_colors"), dict):
            localized["part_colors"] = {k: self._translate_color_to_japanese(str(v)) for k, v in localized["part_colors"].items()}
        shoes = self._coerce_part_entry(localized.get("shoes"))
        if shoes:
            localized["shoes"] = shoes
            if isinstance(shoes.get("type"), str):
                shoes["type"] = self._translate_phrase_to_japanese(shoes["type"])
            if isinstance(shoes.get("color"), str):
                shoes["color"] = self._translate_color_to_japanese(shoes["color"])
            if isinstance(shoes.get("material"), str):
                shoes["material"] = self._translate_phrase_to_japanese(shoes["material"])
            if isinstance(shoes.get("condition"), str):
                shoes["condition"] = self._translate_phrase_to_japanese(shoes["condition"])
            if isinstance(shoes.get("details"), list):
                shoes["details"] = [self._translate_phrase_to_japanese(str(x)) for x in shoes["details"]]
        if isinstance(localized.get("mood"), list):
            localized["mood"] = [self._translate_phrase_to_japanese(str(x)) for x in localized["mood"]]
        return localized

    def _contains_ascii_letters(self, value: str) -> bool:
        return any(("a" <= ch.lower() <= "z") for ch in (value or ""))

    def _join_japanese_list(self, items: list[str]) -> str:
        values = [str(x).strip() for x in items if str(x).strip()]
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]}と{values[1]}"
        return f"{ '、'.join(values[:-1]) }、{values[-1]}"

    def _normalize_japanese_item_text(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return text
        replacements = [
            ("ラギッドな", "無骨な"),
            ("ワークシューズ", "作業靴"),
            ("ハイカット作業靴", "ハイカットの作業靴"),
            ("色落ちしたオリーブ", "くすんだオリーブ"),
            ("サポート性のある", "サポート性の高い"),
            ("医療向けの閉じたシューズ", "つま先まで覆われた医療用シューズ"),
            ("ヘビーデューティーな", "丈夫な"),
        ]
        for old, new in replacements:
            text = text.replace(old, new)
        text = text.replace("  ", " ").strip()
        return text

    def _coerce_part_entry(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            return {"type": text, "color": ""}
        return {}

    def _compose_japanese_description(self, outfit: dict[str, Any], profession: str, accessories: list[str], color_scheme: list[str], part_colors: dict[str, str], language: str) -> str:
        parts = []
        if profession:
            parts.append(f"{profession}向けの仕事着として")

        body = []
        if outfit.get("top"):
            body.append(f"上半身は{self._normalize_japanese_item_text(self._render_colored_item(outfit['top'], part_colors.get('top', ''), language))}")
        if outfit.get("bottom"):
            body.append(f"下半身は{self._normalize_japanese_item_text(self._render_colored_item(outfit['bottom'], part_colors.get('bottom', ''), language))}")
        if outfit.get("outer"):
            body.append(f"羽織は{self._normalize_japanese_item_text(self._render_colored_item(outfit['outer'], part_colors.get('outer', ''), language))}")
        if outfit.get("socks"):
            body.append(f"靴下は{self._normalize_japanese_item_text(self._render_colored_item(outfit['socks'], '', language))}")
        shoes = self._coerce_part_entry(outfit.get("shoes"))
        if shoes:
            shoe_text = self._normalize_japanese_item_text(self._render_colored_item(shoes.get('type', ''), shoes.get('color', part_colors.get('shoes', '')), language))
            body.append(f"足元は{shoe_text}")
        if body:
            parts.append("、".join(body))

        tail_parts = []
        if color_scheme and outfit.get("silhouette"):
            colors = self._join_japanese_list(color_scheme[:3])
            tail_parts.append(f"全体は{colors}を基調にした{outfit['silhouette']}")
        elif color_scheme:
            colors = self._join_japanese_list(color_scheme[:3])
            tail_parts.append(f"全体は{colors}を基調にまとめる")
        elif outfit.get("silhouette"):
            tail_parts.append(f"全体は{outfit['silhouette']}")

        if accessories:
            accessory_items = [self._normalize_japanese_item_text(self._render_colored_item(str(x), part_colors.get('accessories', ''), language)) for x in accessories]
            tail_parts.append(f"小物は{self._join_japanese_list(accessory_items)}")

        sentence = "、".join([p for p in parts if p])
        if tail_parts:
            if sentence:
                sentence = f"{sentence}。{'、'.join(tail_parts)}。"
            else:
                sentence = f"{'、'.join(tail_parts)}。"
        elif sentence:
            sentence = sentence + "。"
        return sentence.strip()

    def _fallback_result(self, payload: dict[str, Any], language: str) -> dict[str, Any]:
        lang = normalize_output_language(language)
        outfit = self._clean_payload(dict(payload))
        used_fields = list(outfit.keys())
        shoes = self._coerce_part_entry(outfit.get("shoes"))
        accessories = outfit.get("accessories", [])
        color_scheme = outfit.get("color_scheme", [])
        part_colors = outfit.get("part_colors", {}) if isinstance(outfit.get("part_colors"), dict) else {}
        profession = outfit.get("profession")

        if lang == "Japanese":
            description = self._compose_japanese_description(outfit, str(profession or ""), accessories, color_scheme, part_colors, language)
            tags = []
            for value in [profession, outfit.get("style"), outfit.get("top"), outfit.get("bottom"), outfit.get("outer"), outfit.get("socks"), outfit.get("silhouette")]:
                if value:
                    tags.append(self._normalize_japanese_item_text(str(value)))
            if shoes:
                tags.append(self._normalize_japanese_item_text(str(shoes.get("type", ""))))
        else:
            parts = []
            if profession:
                parts.append(f"for {profession} workwear")
            if outfit.get("top"):
                parts.append(f"top: {self._render_colored_item(outfit['top'], part_colors.get('top', ''), language)}")
            if outfit.get("bottom"):
                parts.append(f"bottom: {self._render_colored_item(outfit['bottom'], part_colors.get('bottom', ''), language)}")
            if outfit.get("outer"):
                parts.append(f"outer: {self._render_colored_item(outfit['outer'], part_colors.get('outer', ''), language)}")
            if outfit.get("socks"):
                parts.append(f"socks: {self._render_colored_item(outfit['socks'], '', language)}")
            if shoes:
                parts.append(f"shoes: {self._render_colored_item(shoes.get('type', ''), shoes.get('color', part_colors.get('shoes', '')), language)}")
            if outfit.get("silhouette"):
                parts.append(f"silhouette: {outfit['silhouette']}")
            if accessories:
                accessory_items = [self._render_colored_item(str(x), part_colors.get('accessories', ''), language) for x in accessories]
                parts.append(f"accessories: {', '.join(accessory_items)}")
            description = "; ".join(parts)
            tags = [str(v) for v in [profession, outfit.get("style"), outfit.get("top"), outfit.get("bottom"), outfit.get("outer"), outfit.get("socks"), outfit.get("silhouette")] if v]
            if shoes:
                tags.append(str(shoes.get("type", "")))

        return {
            "outfit_description": description,
            "outfit_tags": [t for t in tags if t],
            "outfit": outfit,
            "used_fields": used_fields,
        }

    def generate_outfit(
        self,
        gender_mode,
        gender,
        season_mode,
        season,
        style_mode,
        style,
        mood,
        age_range,
        profession_mode_select,
        profession,
        avoid_items,
        outerwear_mode,
        outerwear_type,
        socks_mode,
        shoe_mode,
        include_shoes,
        shoe_type,
        shoe_avoid,
        randomness,
        detail_strength,
        seed,
        language,
        save_dir,
        save_name,
        model_path,
        load_strategy,
        max_tokens,
        temperature,
        top_p,
    ):
        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "outfit")
        json_path = str(base_dir / f"{save_name_out}_outfit.json")

        payload = self._build_base_profile(
            gender_mode,
            gender,
            season_mode,
            season,
            style_mode,
            style,
            mood,
            age_range,
            profession_mode_select,
            profession,
            avoid_items,
            outerwear_mode,
            outerwear_type,
            socks_mode,
            shoe_mode,
            include_shoes,
            shoe_type,
            shoe_avoid,
            randomness,
            detail_strength,
            seed,
        )

        result = None
        try:
            try:
                loaded = load_llm_model(local_model_path=str(model_path or ""), temperature=float(temperature))
                response = loaded.model.create_chat_completion(
                    messages=[
                        {"role": "system", "content": f"{DEFAULT_OUTFIT_SYSTEM_PROMPT} {output_language_instruction(language, json_mode=True)}"},
                        {"role": "user", "content": self._build_instruction(payload, str(language))},
                    ],
                    max_tokens=int(max_tokens),
                    temperature=float(temperature),
                    top_p=float(top_p),
                    stop=STOP_TOKENS,
                    response_format={"type": "json_object"},
                )
                result = self._extract_json(response["choices"][0]["message"]["content"])
            except Exception:
                result = self._fallback_result(payload, str(language))

            outfit = self._clean_payload(result.get("outfit", {})) if isinstance(result, dict) else payload
            outfit = self._enforce_payload_outfit(outfit, payload)
            if normalize_output_language(language) == "Japanese":
                outfit = self._localize_outfit_payload(outfit, language)
            used_fields = [key for key in result.get("used_fields", []) if key in outfit] if isinstance(result, dict) else list(outfit.keys())
            outfit_description = self._clean_text(str((result or {}).get("outfit_description", "")))
            outfit_tags = [self._clean_text(str(x)) for x in (result or {}).get("outfit_tags", []) if self._clean_text(str(x))]
            if normalize_output_language(language) == "Japanese":
                outfit_tags = [self._translate_phrase_to_japanese(x) for x in outfit_tags]

            profession_first = payload.get("generation_priority") == "profession-first"
            profession_mode = str(payload.get("profession_mode", "")).strip().lower()
            if profession_first and profession_mode == "workwear":
                fallback = self._fallback_result(outfit or payload, str(language))
                outfit_description = fallback["outfit_description"]
                outfit_tags = fallback["outfit_tags"]
            elif not outfit_description or not outfit_tags:
                fallback = self._fallback_result(outfit or payload, str(language))
                if not outfit_description:
                    outfit_description = fallback["outfit_description"]
                if not outfit_tags:
                    outfit_tags = fallback["outfit_tags"]
            if normalize_output_language(language) == "Japanese" and (self._contains_ascii_letters(outfit_description) or any(self._contains_ascii_letters(x) for x in outfit_tags)):
                fallback = self._fallback_result(outfit or payload, str(language))
                outfit_description = fallback["outfit_description"]
                outfit_tags = fallback["outfit_tags"]
            if not used_fields:
                used_fields = list(outfit.keys())

            final_result = {
                "save_name": save_name_out,
                "node": "outfit_generator",
                "inputs": {
                    "gender_mode": gender_mode,
                    "gender": gender,
                    "season_mode": season_mode,
                    "season": season,
                    "style_mode": style_mode,
                    "style": style,
                    "mood": mood,
                    "age_range": age_range,
                    "profession_mode_select": profession_mode_select,
                    "profession": profession,
                    "avoid_items": avoid_items,
                    "outerwear_mode": outerwear_mode,
                    "outerwear_type": outerwear_type,
                    "socks_mode": socks_mode,
                    "shoe_mode": shoe_mode,
                    "include_shoes": include_shoes,
                    "shoe_type": shoe_type,
                    "shoe_avoid": shoe_avoid,
                    "randomness": int(randomness),
                    "detail_strength": int(detail_strength),
                    "seed": int(seed),
                },
                "outputs": {
                    "outfit_description": outfit_description,
                    "outfit_tags": outfit_tags,
                    "outfit": outfit,
                    "used_fields": used_fields,
                },
                "settings": {
                    "language": str(language),
                    "save_dir": base_dir_str,
                    "model_path": str(model_path),
                    "load_strategy": str(load_strategy),
                    "max_tokens": int(max_tokens),
                    "temperature": float(temperature),
                    "top_p": float(top_p),
                },
            }

            write_text(base_dir / f"{save_name_out}_outfit.txt", outfit_description)
            write_text(base_dir / f"{save_name_out}_outfit_tags.txt", ", ".join(outfit_tags))
            write_json(base_dir / f"{save_name_out}_outfit.json", final_result)
            return (
                outfit_description,
                ", ".join(outfit_tags),
                json.dumps(final_result["outputs"], ensure_ascii=False, indent=2),
                save_name_out,
                json_path,
            )
        finally:
            if str(load_strategy) == "reload_every_run":
                unload_model()
