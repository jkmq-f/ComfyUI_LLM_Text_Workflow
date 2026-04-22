from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..utils.io_utils import ensure_save_context, write_json, write_text
from ..utils.language_prompt_utils import normalize_output_language


MOOD_PROFILES: Dict[str, Dict[str, Any]] = {
    "natural": {
        "base_weight": 24,
        "keywords": ["natural", "casual", "daily", "simple", "ナチュラル", "日常", "自然", "素朴", "普通"],
        "slot_weights": {
            "style.length": {"medium_hair": 16, "long_hair": 14, "short_hair": 11, "shoulder_length_hair": 10},
            "style.front": {"parted_bangs": 13, "swept_bangs": 11, "wispy_bangs": 8, "see_through_bangs": 6},
            "style.parting": {"center_part": 11, "side_part": 11, "off_center_part": 8},
            "style.arrangement": {"bob_cut": 9, "low_ponytail": 8, "single_braid": 7, "half_updo": 5},
            "style.shape": {"straight_hair": 14, "wavy_hair": 12, "layered_hair": 10, "layer_bob": 8, "hush_cut": 6},
            "style.extra": {"face_framing_strands": 8, "loose_strands": 5, "ear_tucks": 4},
            "texture.surface": {"smooth_hair": 13, "silky_hair": 11, "soft_texture_hair": 10, "glass_hair": 5},
            "texture.volume": {"airy_hair": 9, "fluffy_hair": 6, "flat_hair": 4},
            "texture.irregularity": {"tousled_hair": 5, "piecey_hair": 4},
            "color.base": {"black_hair": 14, "brown_hair": 13, "light_brown_hair": 9, "ash_brown_hair": 7, "dark_brown_hair": 6},
            "color.pattern": {"highlighted_hair": 4, "balayage_hair": 3, "inner_colored_hair": 2},
        },
        "slot_probability": {
            "style.front": 0.92,
            "style.parting": 0.90,
            "style.arrangement": 0.32,
            "style.extra": 0.28,
            "texture.surface": 0.95,
            "texture.volume": 0.34,
            "texture.irregularity": 0.12,
            "texture.state": 0.04,
            "color.pattern": 0.14,
        },
    },
    "cool": {
        "base_weight": 16,
        "keywords": ["cool", "sharp", "stoic", "modern", "クール", "冷静", "無口", "都会", "シャープ"],
        "slot_weights": {
            "style.length": {"long_hair": 15, "medium_hair": 13, "short_hair": 10},
            "style.front": {"swept_bangs": 13, "curtain_bangs": 11, "parted_bangs": 9, "asymmetrical_bangs": 9},
            "style.parting": {"side_part": 12, "deep_side_part": 11, "center_part": 8},
            "style.arrangement": {"low_ponytail": 8, "side_ponytail": 6, "half_updo": 4},
            "style.shape": {"straight_hair": 14, "wolf_cut": 12, "undercut": 10, "hush_cut": 9, "slicked_back_hair": 7},
            "style.extra": {"face_framing_strands": 7, "ear_tucks": 5, "sideburn_strands": 4},
            "texture.surface": {"smooth_hair": 11, "shiny_hair": 11, "glass_hair": 9, "sleek_hair": 8, "matte_hair": 5},
            "texture.irregularity": {"piecey_hair": 4, "tousled_hair": 3},
            "color.base": {"black_hair": 16, "silver_hair": 10, "grey_hair": 9, "navy_blue_hair": 8, "dark_brown_hair": 8, "white_hair": 5},
            "color.pattern": {"money_piece_hair": 3, "streaked_hair": 3},
        },
        "slot_probability": {
            "style.front": 0.86,
            "style.parting": 0.95,
            "style.arrangement": 0.22,
            "style.extra": 0.20,
            "texture.surface": 0.96,
            "texture.volume": 0.16,
            "texture.irregularity": 0.10,
            "texture.state": 0.02,
            "color.pattern": 0.08,
        },
    },
    "cute": {
        "base_weight": 14,
        "keywords": ["cute", "sweet", "idol", "girly", "かわいい", "可愛い", "アイドル", "ポップ", "甘い"],
        "slot_weights": {
            "style.length": {"medium_hair": 15, "long_hair": 13, "short_hair": 8, "shoulder_length_hair": 8},
            "style.front": {"blunt_bangs": 13, "see_through_bangs": 9, "curled_bangs": 9, "wispy_bangs": 8, "micro_bangs": 5},
            "style.parting": {"center_part": 9, "side_part": 8},
            "style.arrangement": {"twintails": 14, "low_twintails": 10, "short_twintails": 8, "high_ponytail": 11, "double_bun": 9, "half_twintails": 9},
            "style.shape": {"wavy_hair": 13, "curly_hair": 11, "straight_hair": 9, "jellyfish_cut": 8, "mash_wolf": 5},
            "style.extra": {"ahoge": 10, "hair_intakes": 8, "heart_ahoge": 6, "face_framing_strands": 5},
            "texture.surface": {"silky_hair": 10, "soft_texture_hair": 10, "shiny_hair": 8, "glossy_hair": 7},
            "texture.volume": {"fluffy_hair": 11, "airy_hair": 8, "bouncy_hair": 8, "puffy_hair": 5},
            "texture.irregularity": {"piecey_hair": 4, "tousled_hair": 4},
            "color.base": {"brown_hair": 12, "light_brown_hair": 10, "blonde_hair": 10, "pink_hair": 10, "strawberry_blonde_hair": 7, "lavender_hair": 6, "silver_hair": 5},
            "color.pattern": {"inner_colored_hair": 5, "gradient_hair": 5, "colored_tips": 5, "money_piece_hair": 4, "two_tone_hair": 3},
        },
        "slot_probability": {
            "style.front": 0.95,
            "style.parting": 0.72,
            "style.arrangement": 0.60,
            "style.extra": 0.44,
            "texture.surface": 0.96,
            "texture.volume": 0.46,
            "texture.irregularity": 0.12,
            "texture.state": 0.02,
            "color.pattern": 0.22,
        },
    },
    "elegant": {
        "base_weight": 14,
        "keywords": ["elegant", "noble", "lady", "refined", "上品", "優雅", "気品", "お嬢様", "端正"],
        "slot_weights": {
            "style.length": {"long_hair": 17, "very_long_hair": 12, "shoulder_length_hair": 8, "medium_hair": 7},
            "style.front": {"swept_bangs": 11, "parted_bangs": 10, "long_bangs": 8, "curtain_bangs": 7},
            "style.parting": {"center_part": 12, "side_part": 9},
            "style.arrangement": {"hime_cut": 12, "low_bun": 10, "single_braid": 8, "crown_braid": 7, "low_ponytail": 7},
            "style.shape": {"straight_hair": 12, "wavy_hair": 10, "drill_hair": 9, "feathered_hair": 7},
            "style.extra": {"sidelocks": 10, "face_framing_strands": 7, "curled_sidelocks": 6, "temple_locks": 5},
            "texture.surface": {"silky_hair": 12, "shiny_hair": 10, "glass_hair": 8, "smooth_hair": 8},
            "texture.volume": {"voluminous_hair": 7, "airy_hair": 5},
            "color.base": {"black_hair": 12, "dark_brown_hair": 10, "brown_hair": 9, "silver_hair": 7, "white_hair": 6, "chestnut_hair": 5},
            "color.pattern": {"highlighted_hair": 2, "lowlights_hair": 2},
        },
        "slot_probability": {
            "style.front": 0.84,
            "style.parting": 0.92,
            "style.arrangement": 0.45,
            "style.extra": 0.34,
            "texture.surface": 0.97,
            "texture.volume": 0.22,
            "texture.irregularity": 0.05,
            "texture.state": 0.01,
            "color.pattern": 0.06,
        },
    },
    "active": {
        "base_weight": 11,
        "keywords": ["active", "sporty", "energetic", "fast", "活発", "スポーティ", "元気", "快活"],
        "slot_weights": {
            "style.length": {"short_hair": 14, "medium_hair": 14, "shoulder_length_hair": 8, "long_hair": 6, "very_short_hair": 6},
            "style.front": {"swept_bangs": 11, "parted_bangs": 10, "short_bangs": 7},
            "style.parting": {"side_part": 10, "off_center_part": 8, "center_part": 6},
            "style.arrangement": {"high_ponytail": 13, "ponytail": 12, "side_ponytail": 7, "half_ponytail": 7, "bob_cut": 5},
            "style.shape": {"straight_hair": 10, "wavy_hair": 8, "wolf_cut": 9, "pixie_cut": 8, "shag_cut": 7},
            "style.extra": {"ahoge": 5, "loose_strands": 6, "floating_strands": 4},
            "texture.surface": {"soft_texture_hair": 9, "dry_texture_hair": 8, "smooth_hair": 7},
            "texture.volume": {"airy_hair": 10, "bouncy_hair": 8, "fluffy_hair": 6},
            "texture.irregularity": {"messy_hair": 9, "tousled_hair": 8, "piecey_hair": 6},
            "color.base": {"brown_hair": 10, "light_brown_hair": 8, "blonde_hair": 8, "black_hair": 7, "orange_hair": 6, "red_hair": 4},
            "color.pattern": {"colored_tips": 4, "frosted_tips": 3, "inner_colored_hair": 2},
        },
        "slot_probability": {
            "style.front": 0.82,
            "style.parting": 0.78,
            "style.arrangement": 0.62,
            "style.extra": 0.22,
            "texture.surface": 0.88,
            "texture.volume": 0.40,
            "texture.irregularity": 0.34,
            "texture.state": 0.03,
            "color.pattern": 0.12,
        },
    },
    "korean_soft": {
        "base_weight": 13,
        "keywords": ["korean", "k-style", "kbeauty", "韓国", "韓国風", "シースルー", "清楚", "柔らかい", "soft"],
        "slot_weights": {
            "style.length": {"medium_hair": 16, "long_hair": 12, "shoulder_length_hair": 10},
            "style.front": {"see_through_bangs": 16, "parted_bangs": 10, "wispy_bangs": 8, "curtain_bangs": 8},
            "style.parting": {"center_part": 14, "side_part": 8, "off_center_part": 7},
            "style.arrangement": {"layer_bob": 8, "low_ponytail": 5, "half_updo": 5, "bob_cut": 4},
            "style.shape": {"straight_hair": 10, "wavy_hair": 10, "hush_cut": 12, "layer_bob": 10, "layered_hair": 8},
            "style.extra": {"face_framing_strands": 12, "ear_tucks": 5, "loose_strands": 4},
            "texture.surface": {"soft_texture_hair": 12, "silky_hair": 12, "smooth_hair": 10, "glass_hair": 8},
            "texture.volume": {"airy_hair": 12, "flat_hair": 4},
            "texture.irregularity": {"piecey_hair": 4},
            "color.base": {"black_hair": 11, "brown_hair": 11, "light_brown_hair": 9, "ash_brown_hair": 9, "ash_blonde_hair": 8, "dark_brown_hair": 7},
            "color.pattern": {"dark_roots": 5, "money_piece_hair": 4, "highlighted_hair": 3, "inner_colored_hair": 3},
        },
        "slot_probability": {
            "style.front": 0.98,
            "style.parting": 0.98,
            "style.arrangement": 0.20,
            "style.extra": 0.34,
            "texture.surface": 0.98,
            "texture.volume": 0.40,
            "texture.irregularity": 0.08,
            "texture.state": 0.01,
            "color.pattern": 0.16,
        },
    },
    "fantasy": {
        "base_weight": 8,
        "keywords": ["fantasy", "magic", "elf", "mystic", "ファンタジー", "魔法", "幻想", "妖精", "異世界"],
        "slot_weights": {
            "style.length": {"long_hair": 15, "very_long_hair": 13, "shoulder_length_hair": 6},
            "style.front": {"blunt_bangs": 9, "asymmetrical_bangs": 8, "curled_bangs": 7, "long_bangs": 6},
            "style.parting": {"center_part": 10, "side_part": 7},
            "style.arrangement": {"hime_cut": 8, "single_braid": 8, "side_braid": 7, "crown_braid": 7, "twintails": 6, "half_updo": 6},
            "style.shape": {"straight_hair": 8, "wavy_hair": 9, "jellyfish_cut": 10, "curly_hair": 7, "drill_hair": 6},
            "style.extra": {"sidelocks": 8, "face_framing_strands": 6, "floating_strands": 5},
            "texture.surface": {"silky_hair": 10, "shiny_hair": 9, "glossy_hair": 8, "velvety_hair": 6},
            "texture.volume": {"voluminous_hair": 8, "airy_hair": 6, "fluffy_hair": 6},
            "color.base": {"silver_hair": 12, "white_hair": 10, "blue_hair": 8, "purple_hair": 8, "pink_hair": 6, "aqua_hair": 5, "lavender_hair": 5},
            "color.pattern": {"gradient_hair": 8, "split_dyed_hair": 6, "rainbow_hair": 5, "color_block_hair": 4},
        },
        "slot_probability": {
            "style.front": 0.78,
            "style.parting": 0.80,
            "style.arrangement": 0.52,
            "style.extra": 0.30,
            "texture.surface": 0.94,
            "texture.volume": 0.34,
            "texture.irregularity": 0.10,
            "texture.state": 0.04,
            "color.pattern": 0.30,
        },
    },
    "anime_iconic": {
        "base_weight": 8,
        "keywords": ["anime", "iconic", "heroine", "anime style", "二次元", "アニメ", "漫画", "ヒロイン", "デフォルメ"],
        "slot_weights": {
            "style.length": {"medium_hair": 12, "long_hair": 12, "short_hair": 7},
            "style.front": {"blunt_bangs": 10, "asymmetrical_bangs": 8, "micro_bangs": 6, "see_through_bangs": 5},
            "style.parting": {"center_part": 8, "zigzag_part": 6, "side_part": 6},
            "style.arrangement": {"twintails": 12, "short_twintails": 8, "side_ponytail": 7, "double_bun": 7, "hime_cut": 6},
            "style.shape": {"straight_hair": 8, "curly_hair": 8, "jellyfish_cut": 8, "mash_wolf": 6, "wolf_cut": 6},
            "style.extra": {"ahoge": 10, "split_ahoge": 7, "twin_ahoge": 6, "antenna_hair": 6, "hair_intakes": 6},
            "texture.surface": {"silky_hair": 8, "shiny_hair": 8, "smooth_hair": 6},
            "texture.volume": {"fluffy_hair": 8, "puffy_hair": 6, "bouncy_hair": 5},
            "texture.irregularity": {"piecey_hair": 5},
            "color.base": {"black_hair": 7, "blonde_hair": 7, "silver_hair": 6, "pink_hair": 6, "blue_hair": 6, "green_hair": 5, "red_hair": 5},
            "color.pattern": {"two_tone_hair": 5, "gradient_hair": 5, "inner_colored_hair": 4, "money_piece_hair": 4},
        },
        "slot_probability": {
            "style.front": 0.90,
            "style.parting": 0.66,
            "style.arrangement": 0.58,
            "style.extra": 0.52,
            "texture.surface": 0.92,
            "texture.volume": 0.38,
            "texture.irregularity": 0.14,
            "texture.state": 0.01,
            "color.pattern": 0.24,
        },
    },
}

CULTURE_PROFILES: Dict[str, Dict[str, Any]] = {
    "neutral": {
        "base_weight": 1,
        "keywords": [],
        "slot_weights": {},
        "slot_probability": {},
    },
    "japanese": {
        "base_weight": 6,
        "keywords": ["japanese", "japan", "和風", "和装", "着物", "巫女", "侍", "大和", "和"],
        "slot_weights": {
            "style.length": {"long_hair": 10, "very_long_hair": 6, "medium_hair": 4},
            "style.front": {"blunt_bangs": 7, "swept_bangs": 6, "parted_bangs": 5},
            "style.parting": {"center_part": 8, "side_part": 5},
            "style.arrangement": {"hime_cut": 10, "single_braid": 8, "low_bun": 7, "side_braid": 6, "half_updo": 5},
            "style.extra": {"sidelocks": 9, "temple_locks": 8, "blunt_sidelocks": 6},
            "texture.surface": {"silky_hair": 8, "smooth_hair": 7},
            "color.base": {"black_hair": 12, "dark_brown_hair": 8, "brown_hair": 7, "white_hair": 3},
        },
        "slot_probability": {"style.arrangement": 0.10, "style.extra": 0.08, "color.pattern": -0.06},
    },
    "korean": {
        "base_weight": 7,
        "keywords": ["korean", "k-style", "kbeauty", "韓国", "韓国風"],
        "slot_weights": {
            "style.length": {"medium_hair": 8, "shoulder_length_hair": 7, "long_hair": 5},
            "style.front": {"see_through_bangs": 10, "curtain_bangs": 8, "wispy_bangs": 6},
            "style.parting": {"center_part": 10, "off_center_part": 7, "side_part": 6},
            "style.shape": {"hush_cut": 10, "layer_bob": 8, "layered_hair": 7, "straight_hair": 6},
            "style.extra": {"face_framing_strands": 8, "ear_tucks": 6},
            "texture.surface": {"glass_hair": 10, "soft_texture_hair": 8, "silky_hair": 8},
            "texture.volume": {"airy_hair": 8, "flat_hair": 5},
            "color.base": {"black_hair": 8, "dark_brown_hair": 8, "ash_brown_hair": 8, "ash_blonde_hair": 6},
            "color.pattern": {"money_piece_hair": 5, "dark_roots": 4, "highlighted_hair": 4},
        },
        "slot_probability": {"style.parting": 0.04, "texture.surface": 0.02, "color.pattern": 0.04},
    },
    "chinese": {
        "base_weight": 5,
        "keywords": ["chinese", "china", "中華", "中国風", "仙侠", "漢服", "宮廷"],
        "slot_weights": {
            "style.length": {"long_hair": 9, "very_long_hair": 8, "medium_hair": 3},
            "style.front": {"parted_bangs": 7, "swept_bangs": 7, "long_bangs": 5},
            "style.parting": {"center_part": 9, "side_part": 5},
            "style.arrangement": {"low_bun": 10, "single_braid": 9, "crown_braid": 7, "half_updo": 7, "low_ponytail": 6},
            "style.extra": {"temple_locks": 8, "sidelocks": 7, "face_framing_strands": 5},
            "texture.surface": {"silky_hair": 8, "shiny_hair": 6},
            "color.base": {"black_hair": 12, "dark_brown_hair": 8, "silver_hair": 4, "white_hair": 4},
        },
        "slot_probability": {"style.arrangement": 0.06, "style.extra": 0.06, "color.pattern": -0.08},
    },
    "western": {
        "base_weight": 4,
        "keywords": ["western", "european", "欧風", "西洋風", "europe", "american", "british"],
        "slot_weights": {
            "style.length": {"medium_hair": 6, "long_hair": 6, "short_hair": 5},
            "style.front": {"curtain_bangs": 7, "swept_bangs": 7, "side_bangs": 6},
            "style.parting": {"side_part": 8, "deep_side_part": 7, "center_part": 5},
            "style.arrangement": {"bob_cut": 7, "low_ponytail": 6, "messy_bun": 6, "half_updo": 5},
            "style.shape": {"layered_hair": 8, "feathered_hair": 7, "wavy_hair": 7, "curtain_hair": 6},
            "texture.surface": {"soft_texture_hair": 7, "matte_hair": 6, "smooth_hair": 5},
            "texture.volume": {"voluminous_hair": 7, "bouncy_hair": 6},
            "color.base": {"blonde_hair": 7, "beige_blonde_hair": 6, "light_brown_hair": 6, "brown_hair": 5, "strawberry_blonde_hair": 5},
            "color.pattern": {"balayage_hair": 6, "highlighted_hair": 5, "money_piece_hair": 3},
        },
        "slot_probability": {"texture.volume": 0.06, "color.pattern": 0.06},
    },
    "nordic": {
        "base_weight": 5,
        "keywords": ["nordic", "scandinavian", "北欧", "北欧風", "scandi"],
        "slot_weights": {
            "style.length": {"long_hair": 8, "medium_hair": 7, "shoulder_length_hair": 6},
            "style.front": {"parted_bangs": 7, "swept_bangs": 7, "curtain_bangs": 6, "wispy_bangs": 4},
            "style.parting": {"center_part": 9, "side_part": 7, "off_center_part": 5},
            "style.arrangement": {"single_braid": 7, "side_braid": 7, "low_ponytail": 6, "half_updo": 5},
            "style.shape": {"soft_waves": 9, "wavy_hair": 8, "straight_hair": 6, "layered_hair": 6},
            "style.extra": {"face_framing_strands": 5, "loose_strands": 4},
            "texture.surface": {"silky_hair": 7, "soft_texture_hair": 7, "smooth_hair": 6},
            "texture.volume": {"airy_hair": 8, "fluffy_hair": 4},
            "color.base": {"blonde_hair": 10, "ash_blonde_hair": 10, "platinum_blonde_hair": 8, "light_brown_hair": 7, "silver_hair": 6, "strawberry_blonde_hair": 5},
            "color.pattern": {"balayage_hair": 4, "highlighted_hair": 4},
        },
        "slot_probability": {"texture.volume": 0.08, "color.pattern": 0.04},
    },
    "fantasy": {
        "base_weight": 4,
        "keywords": ["fantasy", "magic", "elf", "mystic", "異世界", "幻想"],
        "slot_weights": {
            "style.length": {"very_long_hair": 7, "long_hair": 6},
            "style.arrangement": {"crown_braid": 6, "side_braid": 5, "half_updo": 5},
            "texture.surface": {"shiny_hair": 5, "velvety_hair": 4},
            "color.base": {"silver_hair": 6, "white_hair": 5, "blue_hair": 4, "lavender_hair": 4},
            "color.pattern": {"gradient_hair": 5, "split_dyed_hair": 4},
        },
        "slot_probability": {"color.pattern": 0.08},
    },
}

GENDER_KEYWORDS: Dict[str, Sequence[str]] = {
    "female": ["female", "woman", "girl", "女性", "女", "彼女", "お姉さん", "少女"],
    "male": ["male", "man", "boy", "男性", "男", "彼", "青年", "少年"],
    "androgynous": ["androgynous", "neutral", "genderless", "中性的", "ジェンダーレス", "両性"],
}

GENDER_BONUS: Dict[str, Dict[str, Dict[str, int]]] = {
    "female": {
        "style.length": {"long_hair": 5, "very_long_hair": 4, "medium_hair": 3},
        "style.front": {"see_through_bangs": 3, "blunt_bangs": 2, "wispy_bangs": 2},
        "style.arrangement": {"twintails": 3, "low_twintails": 2, "half_updo": 2, "high_ponytail": 2, "single_braid": 2},
        "texture.surface": {"silky_hair": 2, "soft_texture_hair": 2},
        "color.pattern": {"inner_colored_hair": 2, "money_piece_hair": 1},
    },
    "male": {
        "style.length": {"very_short_hair": 6, "short_hair": 5, "medium_hair": 2},
        "style.front": {"curtain_bangs": 3, "swept_bangs": 3, "side_bangs": 2},
        "style.parting": {"side_part": 3, "deep_side_part": 3, "no_part": 2},
        "style.shape": {"undercut": 5, "sidecut": 4, "pompadour": 5, "crew_cut": 5, "french_crop": 4, "quiff": 4, "mullet": 3, "curtain_hair": 3},
        "style.extra": {"sideburn_strands": 2, "ear_tucks": 2},
        "texture.surface": {"matte_hair": 2, "dry_texture_hair": 2, "coarse_hair": 2},
        "texture.irregularity": {"tousled_hair": 2, "spiky_hair": 3},
    },
    "androgynous": {
        "style.length": {"medium_hair": 4, "shoulder_length_hair": 4, "short_hair": 2},
        "style.front": {"curtain_bangs": 3, "wispy_bangs": 3, "asymmetrical_bangs": 2, "long_bangs": 2},
        "style.parting": {"off_center_part": 3, "center_part": 2},
        "style.shape": {"wolf_cut": 4, "hush_cut": 4, "bixie_cut": 3, "mullet": 2, "asymmetrical_cut": 2},
        "style.extra": {"ear_tucks": 2, "face_framing_strands": 2},
        "color.base": {"silver_hair": 1, "grey_hair": 1, "ash_blonde_hair": 1},
    },
    "neutral": {},
}

PAIR_BONUS: Dict[str, Dict[str, int]] = {
    "see_through_bangs": {"center_part": 8, "off_center_part": 5, "face_framing_strands": 6, "silky_hair": 6, "glass_hair": 5, "soft_texture_hair": 5},
    "curtain_bangs": {"center_part": 8, "off_center_part": 6, "curtain_hair": 7, "layered_hair": 5, "smooth_hair": 4},
    "wolf_cut": {"tousled_hair": 7, "piecey_hair": 6, "ash_brown_hair": 4, "short_hair": 3, "medium_hair": 4},
    "hime_cut": {"long_hair": 8, "very_long_hair": 6, "black_hair": 6, "silky_hair": 6, "sidelocks": 7},
    "jellyfish_cut": {"very_long_hair": 7, "long_hair": 6, "straight_hair": 5, "silky_hair": 5, "inner_colored_hair": 4},
    "bob_cut": {"short_hair": 8, "medium_hair": 4, "side_part": 4, "smooth_hair": 5},
    "layer_bob": {"shoulder_length_hair": 7, "medium_hair": 4, "center_part": 4, "glass_hair": 4},
    "twintails": {"blunt_bangs": 5, "fluffy_hair": 5, "pink_hair": 4, "short_twintails": 2, "see_through_bangs": 3},
    "single_braid": {"long_hair": 6, "very_long_hair": 4, "sidelocks": 4, "silky_hair": 3},
    "low_ponytail": {"long_hair": 5, "swept_bangs": 4, "side_part": 3, "smooth_hair": 3},
    "soft_waves": {"blonde_hair": 4, "ash_blonde_hair": 4, "airy_hair": 5, "light_brown_hair": 3},
    "dark_roots": {"ash_blonde_hair": 4, "blonde_hair": 3, "silver_hair": 3},
    "money_piece_hair": {"center_part": 5, "dark_roots": 3, "ash_brown_hair": 3, "ash_blonde_hair": 3},
    "glass_hair": {"center_part": 5, "black_hair": 4, "dark_brown_hair": 4, "straight_hair": 4},
}

BUNDLE_PRESETS: List[Dict[str, Any]] = [
    {"name": "korean_clean_medium", "cultures": ["korean"], "moods": ["natural", "korean_soft", "elegant"], "tags": ["medium_hair", "hush_cut", "see_through_bangs", "center_part", "face_framing_strands", "glass_hair", "airy_hair", "black_hair"], "weight": 12},
    {"name": "korean_soft_long", "cultures": ["korean"], "moods": ["korean_soft", "cute", "elegant"], "tags": ["long_hair", "layered_hair", "see_through_bangs", "center_part", "face_framing_strands", "silky_hair", "soft_texture_hair", "ash_brown_hair", "money_piece_hair"], "weight": 10},
    {"name": "japanese_hime", "cultures": ["japanese"], "moods": ["elegant", "cool", "fantasy"], "tags": ["long_hair", "hime_cut", "blunt_bangs", "center_part", "sidelocks", "silky_hair", "black_hair"], "weight": 10},
    {"name": "japanese_soft_braid", "cultures": ["japanese"], "moods": ["natural", "elegant"], "tags": ["long_hair", "single_braid", "parted_bangs", "center_part", "temple_locks", "smooth_hair", "dark_brown_hair"], "weight": 8},
    {"name": "chinese_refined_updo", "cultures": ["chinese"], "moods": ["elegant", "fantasy", "cool"], "tags": ["very_long_hair", "low_bun", "swept_bangs", "center_part", "temple_locks", "silky_hair", "black_hair"], "weight": 9},
    {"name": "chinese_soft_long", "cultures": ["chinese"], "moods": ["natural", "elegant"], "tags": ["long_hair", "half_updo", "parted_bangs", "center_part", "sidelocks", "smooth_hair", "dark_brown_hair"], "weight": 7},
    {"name": "nordic_soft_long", "cultures": ["nordic"], "moods": ["natural", "elegant", "cool"], "tags": ["long_hair", "soft_waves", "parted_bangs", "center_part", "airy_hair", "silky_hair", "ash_blonde_hair", "balayage_hair"], "weight": 10},
    {"name": "nordic_clean_medium", "cultures": ["nordic"], "moods": ["natural", "cool"], "tags": ["medium_hair", "straight_hair", "swept_bangs", "side_part", "soft_texture_hair", "light_brown_hair", "highlighted_hair"], "weight": 8},
    {"name": "western_layered_bob", "cultures": ["western"], "moods": ["natural", "cool", "active"], "tags": ["short_hair", "layer_bob", "curtain_bangs", "side_part", "soft_texture_hair", "voluminous_hair", "light_brown_hair", "balayage_hair"], "weight": 9},
    {"name": "western_cool_short", "cultures": ["western"], "moods": ["cool", "active"], "tags": ["short_hair", "undercut", "swept_bangs", "deep_side_part", "matte_hair", "dark_brown_hair"], "weight": 8},
    {"name": "cute_twinwaves", "cultures": ["neutral", "western", "japanese"], "moods": ["cute", "anime_iconic"], "tags": ["medium_hair", "twintails", "blunt_bangs", "fluffy_hair", "silky_hair", "pink_hair", "inner_colored_hair"], "weight": 9},
    {"name": "active_ponytail", "cultures": ["neutral", "western", "korean"], "moods": ["active", "natural"], "tags": ["medium_hair", "high_ponytail", "swept_bangs", "side_part", "dry_texture_hair", "airy_hair", "brown_hair"], "weight": 9},
    {"name": "cool_long_straight", "cultures": ["neutral", "japanese", "korean"], "moods": ["cool", "elegant"], "tags": ["long_hair", "straight_hair", "long_bangs", "side_part", "glass_hair", "black_hair"], "weight": 8},
    {"name": "fantasy_silver_long", "cultures": ["fantasy", "neutral"], "moods": ["fantasy", "anime_iconic", "elegant"], "tags": ["very_long_hair", "wavy_hair", "single_braid", "long_bangs", "shiny_hair", "silver_hair", "gradient_hair"], "weight": 9},
    {"name": "androgynous_wolf", "cultures": ["neutral", "western", "korean"], "moods": ["cool", "natural", "anime_iconic"], "tags": ["medium_hair", "wolf_cut", "curtain_bangs", "off_center_part", "piecey_hair", "soft_texture_hair", "ash_brown_hair"], "weight": 9, "genders": ["androgynous", "neutral"]},
    {"name": "male_modern_short", "cultures": ["western", "korean", "neutral"], "moods": ["cool", "active", "natural"], "tags": ["short_hair", "curtain_hair", "curtain_bangs", "side_part", "matte_hair", "ash_brown_hair"], "weight": 9, "genders": ["male", "neutral"]},
    {"name": "male_clean_crop", "cultures": ["western", "neutral"], "moods": ["active", "cool"], "tags": ["very_short_hair", "french_crop", "short_bangs", "no_part", "matte_hair", "black_hair"], "weight": 7, "genders": ["male", "neutral"]},
    {"name": "female_soft_wave", "cultures": ["neutral", "nordic", "western"], "moods": ["natural", "elegant", "cute"], "tags": ["long_hair", "soft_waves", "parted_bangs", "center_part", "silky_hair", "airy_hair", "light_brown_hair"], "weight": 8, "genders": ["female", "neutral"]},
]

SLOT_ORDER: List[str] = [
    "style.length",
    "style.shape",
    "style.front",
    "style.parting",
    "style.arrangement",
    "style.extra",
    "texture.surface",
    "texture.volume",
    "texture.irregularity",
    "texture.state",
    "color.base",
    "color.pattern",
]

CORE_SLOTS = {"style.length", "style.shape", "color.base"}
MULTI_SLOTS = {"style.extra", "color.pattern"}
CONSERVATIVE_BASIC_SLOTS = {"style.front", "style.parting", "texture.surface"}

RICHNESS_SLOT_LIMITS: Dict[str, Dict[str, int]] = {
    "minimal": {"style.extra": 0, "color.pattern": 0, "texture.volume": 0, "texture.irregularity": 0, "texture.state": 0, "style.arrangement": 1, "total": 5},
    "balanced": {"style.extra": 1, "color.pattern": 1, "texture.volume": 1, "texture.irregularity": 0, "texture.state": 0, "style.arrangement": 1, "total": 7},
    "detailed": {"style.extra": 2, "color.pattern": 1, "texture.volume": 1, "texture.irregularity": 1, "texture.state": 0, "style.arrangement": 1, "total": 9},
    "stylized": {"style.extra": 2, "color.pattern": 2, "texture.volume": 1, "texture.irregularity": 1, "texture.state": 1, "style.arrangement": 1, "total": 11},
}

RICHNESS_PROB_SCALE = {"minimal": 0.55, "balanced": 0.85, "detailed": 1.0, "stylized": 1.18}

LENGTH_RANK = {
    "bald": 0,
    "very_short_hair": 1,
    "short_hair": 2,
    "medium_hair": 3,
    "shoulder_length_hair": 4,
    "long_hair": 5,
    "very_long_hair": 6,
}

MIN_LENGTH_FOR_TAG = {
    "ponytail": 4,
    "high_ponytail": 4,
    "low_ponytail": 4,
    "side_ponytail": 4,
    "twintails": 4,
    "low_twintails": 4,
    "short_twintails": 2,
    "braid": 4,
    "single_braid": 4,
    "side_braid": 4,
    "twin_braids": 4,
    "french_braid": 4,
    "crown_braid": 4,
    "fishtail_braid": 4,
    "dutch_braid": 4,
    "boxer_braids": 4,
    "braided_ponytail": 4,
    "looped_ponytail": 4,
    "loose_ponytail": 4,
    "loose_braid": 4,
    "braided_twintails": 4,
    "double_bun": 3,
    "low_bun": 3,
    "messy_bun": 3,
    "half_updo": 3,
    "half_ponytail": 3,
    "half_twintails": 3,
    "half_bun": 3,
    "drill_hair": 4,
    "hime_cut": 4,
    "jellyfish_cut": 5,
    "ringlets": 4,
}

LIGHT_BASE_COLORS = {
    "blonde_hair", "beige_blonde_hair", "ash_blonde_hair", "platinum_blonde_hair", "dirty_blonde_hair",
    "strawberry_blonde_hair", "silver_hair", "grey_hair", "white_hair", "pink_hair", "smoky_pink_hair",
    "lavender_hair", "lilac_hair", "blue_hair", "aqua_hair", "mint_hair", "yellow_hair",
}

DARK_BASE_COLORS = {
    "black_hair", "brown_hair", "dark_brown_hair", "ash_brown_hair", "chestnut_hair",
    "chocolate_brown_hair", "navy_blue_hair", "burgundy_hair", "green_hair",
}

SHAPE_TO_NATURAL_LENGTH = {
    "pixie_cut": "very_short_hair",
    "undercut": "short_hair",
    "sidecut": "short_hair",
    "crew_cut": "very_short_hair",
    "french_crop": "very_short_hair",
    "faux_hawk": "short_hair",
    "mohawk": "short_hair",
    "quiff": "short_hair",
    "pompadour": "short_hair",
    "slicked_back_hair": "short_hair",
    "comb_over": "short_hair",
    "bowl_cut": "short_hair",
    "pageboy_cut": "short_hair",
    "layer_bob": "short_hair",
    "inverted_bob": "short_hair",
    "a_line_bob": "short_hair",
    "bixie_cut": "short_hair",
    "curtain_hair": "medium_hair",
    "mullet": "medium_hair",
    "shag_cut": "medium_hair",
    "hush_cut": "medium_hair",
    "jellyfish_cut": "long_hair",
    "drill_hair": "long_hair",
    "ringlets": "long_hair",
}

SHAPE_DISALLOWED_ARRANGEMENTS = {
    "pixie_cut": {"ponytail", "high_ponytail", "low_ponytail", "side_ponytail", "twintails", "low_twintails", "single_braid", "side_braid", "twin_braids"},
    "undercut": {"twintails", "low_twintails", "single_braid", "side_braid", "twin_braids"},
    "sidecut": {"twintails", "low_twintails", "twin_braids"},
    "drill_hair": {"pixie_cut", "undercut", "sidecut"},
    "jellyfish_cut": {"ponytail", "high_ponytail", "low_ponytail", "side_ponytail", "bun_hair", "double_bun", "low_bun", "messy_bun"},
    "bob_cut": {"ponytail", "high_ponytail", "low_ponytail", "twintails", "single_braid", "side_braid", "twin_braids"},
}


def _merge_weight_maps(*maps: Dict[str, int]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for weight_map in maps:
        for tag, value in weight_map.items():
            ivalue = int(value)
            if ivalue <= 0:
                continue
            merged[tag] = merged.get(tag, 0) + ivalue
    return merged


class LLMHairBuilderNode:
    CATEGORY = "text"
    FUNCTION = "build_hair"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("hair_prompt", "hair_summary", "hair_struct_json", "debug_json")
    OUTPUT_NODE = False

    _cache: Optional[Dict[str, Any]] = None

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "character_text": ("STRING", {"default": "", "multiline": True}),
                "hairstyle_hint": ("STRING", {"default": "", "multiline": True}),
                "texture_hint": ("STRING", {"default": "", "multiline": True}),
                "color_hint": ("STRING", {"default": "", "multiline": True}),
                "language": (["Japanese", "English"], {"default": "Japanese"}),
                "use_extended_dictionary": (["true", "false"], {"default": "true"}),
                "gender_mode": (["auto", "female", "male", "androgynous", "neutral"], {"default": "auto"}),
                "gender_strength": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 1.0, "step": 0.05}),
                "culture_mode": (["auto", "neutral", "japanese", "korean", "chinese", "western", "nordic", "fantasy"], {"default": "auto"}),
                "culture_strength": ("FLOAT", {"default": 0.65, "min": 0.0, "max": 1.0, "step": 0.05}),
                "fill_missing": (["off", "basic", "random"], {"default": "random"}),
                "richness": (["minimal", "balanced", "detailed", "stylized"], {"default": "balanced"}),
                "save_dir": ("STRING", {"default": "./llm_story_outputs"}),
                "save_name": ("STRING", {"default": "hair_builder"}),
            },
            "optional": {
                "manual_tags": ("STRING", {"default": "", "multiline": True}),
                "must_tags": ("STRING", {"default": "", "multiline": True}),
                "prefer_tags": ("STRING", {"default": "", "multiline": True}),
                "avoid_tags": ("STRING", {"default": "", "multiline": True}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def _data_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "hair"

    def _normalize_key(self, value: Any) -> str:
        text = str(value or "").strip().lower()
        text = text.replace("-", " ").replace("_", " ")
        text = re.sub(r"[，、/|]+", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _clean_text(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    def _tokenize_csv(self, text: Any) -> List[str]:
        raw = self._clean_text(text)
        if not raw:
            return []
        raw = raw.replace("\n", ",")
        return [self._clean_text(part) for part in raw.split(",") if self._clean_text(part)]

    def _normalize_mode(self, value: Any, allowed: Iterable[str], fallback: str) -> str:
        normalized = self._normalize_key(value).replace(" ", "_")
        return normalized if normalized in set(allowed) else fallback

    def _empty_struct(self) -> Dict[str, Dict[str, List[str]]]:
        return {
            "style": {"length": [], "front": [], "parting": [], "arrangement": [], "shape": [], "extra": []},
            "texture": {"surface": [], "volume": [], "state": [], "irregularity": []},
            "color": {"base": [], "pattern": []},
        }

    def _load_data(self) -> Dict[str, Any]:
        if self.__class__._cache is not None:
            return self.__class__._cache

        data_dir = self._data_dir()
        style = json.loads((data_dir / "hair_style_dictionary.json").read_text(encoding="utf-8"))
        texture = json.loads((data_dir / "hair_texture_dictionary.json").read_text(encoding="utf-8"))
        color = json.loads((data_dir / "hair_color_dictionary.json").read_text(encoding="utf-8"))
        aliases = json.loads((data_dir / "hair_aliases.json").read_text(encoding="utf-8"))
        conflicts = json.loads((data_dir / "hair_conflicts.json").read_text(encoding="utf-8"))
        output_order = json.loads((data_dir / "hair_output_order.json").read_text(encoding="utf-8"))

        entries: Dict[str, Dict[str, Any]] = {}
        by_slot: Dict[str, List[str]] = {}
        blocks = {"style": style, "texture": texture, "color": color}
        for block_name, block in blocks.items():
            for slot, items in block.items():
                dotted = f"{block_name}.{slot}"
                by_slot[dotted] = []
                for item in items:
                    tag = str(item["tag"])
                    entry = dict(item)
                    entry["block"] = block_name
                    entry["slot"] = slot
                    entries[tag] = entry
                    by_slot[dotted].append(tag)

        alias_map: Dict[str, str] = {}
        for raw_alias, tag in aliases.items():
            alias_map[self._normalize_key(raw_alias)] = str(tag)

        self.__class__._cache = {
            "entries": entries,
            "alias_map": alias_map,
            "conflicts": conflicts,
            "output_order": output_order,
            "by_slot": by_slot,
        }
        return self.__class__._cache

    def _score_matches(self, text: str, alias_map: Dict[str, str]) -> Dict[str, int]:
        normalized = self._normalize_key(text)
        if not normalized:
            return {}
        scores: Dict[str, int] = {}
        for alias, tag in alias_map.items():
            if not alias:
                continue
            if all(ord(ch) < 128 for ch in alias):
                matched = bool(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized))
            else:
                matched = alias in normalized
            if matched:
                scores[tag] = scores.get(tag, 0) + max(1, len(alias.split()))
        return scores

    def _merge_scores(self, *score_dicts: Dict[str, int]) -> Dict[str, int]:
        merged: Dict[str, int] = {}
        for score_dict in score_dicts:
            for tag, score in score_dict.items():
                merged[tag] = merged.get(tag, 0) + int(score)
        return merged

    def _canonical_tags_from_text(self, text: str, alias_map: Dict[str, str]) -> List[str]:
        tags: List[str] = []
        for token in self._tokenize_csv(text):
            tag = alias_map.get(self._normalize_key(token))
            if tag and tag not in tags:
                tags.append(tag)
        return tags

    def _resolve_explicit_tag_list(self, alias_map: Dict[str, str], *texts: Any) -> List[str]:
        tags: List[str] = []
        for text in texts:
            for tag in self._canonical_tags_from_text(str(text or ""), alias_map):
                if tag not in tags:
                    tags.append(tag)
        return tags

    def _weighted_choice(self, weighted_map: Dict[str, int], rng: random.Random, deterministic: bool = False) -> Optional[str]:
        clean = {tag: int(weight) for tag, weight in weighted_map.items() if int(weight) > 0}
        if not clean:
            return None
        if deterministic:
            return sorted(clean.items(), key=lambda item: (-item[1], item[0]))[0][0]
        total = float(sum(clean.values()))
        needle = rng.uniform(0.0, total)
        upto = 0.0
        for tag, weight in clean.items():
            upto += float(weight)
            if needle <= upto:
                return tag
        return next(iter(clean))

    def _normalize_gender_mode(self, gender_mode: Any) -> str:
        normalized = self._normalize_key(gender_mode)
        mapping = {
            "": "auto",
            "auto": "auto",
            "female": "female",
            "woman": "female",
            "girl": "female",
            "女性": "female",
            "male": "male",
            "man": "male",
            "boy": "male",
            "男性": "male",
            "androgynous": "androgynous",
            "neutral": "neutral",
            "genderless": "androgynous",
            "中性的": "androgynous",
        }
        return mapping.get(normalized, "auto")

    def _infer_effective_gender(self, context_text: str, gender_mode: Any) -> Tuple[str, Dict[str, int]]:
        mode = self._normalize_gender_mode(gender_mode)
        if mode != "auto":
            return mode, {mode: 100}
        context = self._normalize_key(context_text)
        scores = {"female": 0, "male": 0, "androgynous": 0}
        for gmode, keywords in GENDER_KEYWORDS.items():
            for keyword in keywords:
                key = self._normalize_key(keyword)
                if key and key in context:
                    scores[gmode] += 6 if len(key.split()) > 1 else 4
        if scores["female"] > 0 and scores["male"] > 0 and abs(scores["female"] - scores["male"]) <= 2:
            scores["androgynous"] += 5
        if max(scores.values()) <= 0:
            return "neutral", scores
        effective = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return effective, scores

    def _infer_profile(
        self,
        context_text: str,
        profiles: Dict[str, Dict[str, Any]],
        current_tags: Sequence[str],
        forced_mode: Any,
        fallback: str,
        rng: random.Random,
        deterministic: bool,
    ) -> Tuple[str, Dict[str, int]]:
        normalized_forced = self._normalize_key(forced_mode).replace(" ", "_")
        if normalized_forced and normalized_forced not in {"", "auto"} and normalized_forced in profiles:
            return normalized_forced, {normalized_forced: 100}
        normalized_context = self._normalize_key(context_text)
        scores: Dict[str, int] = {}
        for name, profile in profiles.items():
            score = int(profile.get("base_weight", 1))
            for keyword in profile.get("keywords", []):
                key = self._normalize_key(keyword)
                if key and key in normalized_context:
                    score += 18 if len(key.split()) > 1 else 12
            slot_weights = profile.get("slot_weights", {})
            for tag in current_tags:
                for weighted_tags in slot_weights.values():
                    score += int(weighted_tags.get(tag, 0))
            scores[name] = max(1, score)
        if deterministic:
            return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0], scores
        top_score = max(scores.values()) if scores else 1
        shortlist = {name: value for name, value in scores.items() if value >= top_score * 0.82}
        chosen = self._weighted_choice(shortlist, rng, deterministic=False) or fallback
        return chosen, scores

    def _allowed_tag(self, tag: str, entries: Dict[str, Dict[str, Any]], use_extended: bool, avoid_tags: Sequence[str]) -> bool:
        entry = entries.get(tag)
        if not entry:
            return False
        if tag in avoid_tags:
            return False
        if use_extended:
            return True
        return entry.get("source") == "danbooru"

    def _set_single(self, struct: Dict[str, Dict[str, List[str]]], dotted_slot: str, tag: str) -> None:
        block, slot = dotted_slot.split(".", 1)
        struct[block][slot] = [tag]

    def _append_multi(self, struct: Dict[str, Dict[str, List[str]]], dotted_slot: str, tag: str) -> None:
        block, slot = dotted_slot.split(".", 1)
        if tag not in struct[block][slot]:
            struct[block][slot].append(tag)

    def _slot_values(self, struct: Dict[str, Dict[str, List[str]]], dotted_slot: str) -> List[str]:
        block, slot = dotted_slot.split(".", 1)
        return list(struct.get(block, {}).get(slot, []))

    def _flatten_struct(self, struct: Dict[str, Dict[str, List[str]]]) -> List[str]:
        ordered: List[str] = []
        for block in ("style", "texture", "color"):
            for slot, tags in struct.get(block, {}).items():
                for tag in tags:
                    if tag not in ordered:
                        ordered.append(tag)
        return ordered

    def _rebuild_struct(self, tags: Sequence[str], entries: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        struct = self._empty_struct()
        for tag in tags:
            entry = entries.get(tag)
            if not entry:
                continue
            block = entry["block"]
            slot = entry["slot"]
            if tag not in struct[block][slot]:
                struct[block][slot].append(tag)
        return struct

    def _slot_limit(self, richness: str, dotted_slot: str) -> int:
        limits = RICHNESS_SLOT_LIMITS.get(richness, RICHNESS_SLOT_LIMITS["balanced"])
        if dotted_slot in MULTI_SLOTS:
            return int(limits.get(dotted_slot, 1))
        return 1

    def _merge_slot_weights(
        self,
        dotted_slot: str,
        mood: str,
        culture: str,
        gender: str,
        gender_strength: float,
        culture_strength: float,
    ) -> Dict[str, int]:
        mood_weights = MOOD_PROFILES.get(mood, {}).get("slot_weights", {}).get(dotted_slot, {})
        culture_weights_raw = CULTURE_PROFILES.get(culture, {}).get("slot_weights", {}).get(dotted_slot, {})
        culture_weights = {tag: max(1, int(round(weight * max(0.0, culture_strength)))) for tag, weight in culture_weights_raw.items()}
        gender_weights_raw = GENDER_BONUS.get(gender, {}).get(dotted_slot, {})
        gender_weights = {tag: max(1, int(round(weight * max(0.0, gender_strength)))) for tag, weight in gender_weights_raw.items()}
        return _merge_weight_maps(mood_weights, culture_weights, gender_weights)

    def _slot_probability(self, dotted_slot: str, mood: str, culture: str, richness: str) -> float:
        base = float(MOOD_PROFILES.get(mood, {}).get("slot_probability", {}).get(dotted_slot, 1.0 if dotted_slot in CORE_SLOTS else 0.0))
        culture_delta = float(CULTURE_PROFILES.get(culture, {}).get("slot_probability", {}).get(dotted_slot, 0.0))
        scale = float(RICHNESS_PROB_SCALE.get(richness, 0.85))
        if dotted_slot in CORE_SLOTS:
            return 1.0
        return min(0.98, max(0.0, (base + culture_delta) * scale))

    def _compatibility_bonus(self, candidate: str, current_tags: Sequence[str], mood: str, culture: str) -> int:
        bonus = 0
        for tag in current_tags:
            bonus += PAIR_BONUS.get(tag, {}).get(candidate, 0)
            bonus += PAIR_BONUS.get(candidate, {}).get(tag, 0)
        if culture == "nordic" and candidate in {"blonde_hair", "ash_blonde_hair", "platinum_blonde_hair", "soft_waves", "airy_hair", "single_braid"}:
            bonus += 4
        if culture == "korean" and candidate in {"see_through_bangs", "center_part", "glass_hair", "hush_cut", "face_framing_strands"}:
            bonus += 4
        if culture == "japanese" and candidate in {"hime_cut", "sidelocks", "temple_locks", "single_braid", "black_hair"}:
            bonus += 4
        if culture == "chinese" and candidate in {"low_bun", "crown_braid", "single_braid", "center_part", "silky_hair"}:
            bonus += 4
        if mood == "elegant" and candidate in {"silky_hair", "swept_bangs", "long_hair", "low_bun", "sidelocks"}:
            bonus += 3
        if mood == "cute" and candidate in {"twintails", "blunt_bangs", "fluffy_hair", "pink_hair", "ahoge"}:
            bonus += 3
        if mood == "cool" and candidate in {"side_part", "glass_hair", "straight_hair", "silver_hair", "undercut"}:
            bonus += 3
        return bonus

    def _violates_rules(self, struct: Dict[str, Dict[str, List[str]]], candidate: str) -> bool:
        length = next(iter(struct["style"].get("length", [])), "")
        shape = next(iter(struct["style"].get("shape", [])), "")
        arrangement = next(iter(struct["style"].get("arrangement", [])), "")
        base = next(iter(struct["color"].get("base", [])), "")
        if candidate in MIN_LENGTH_FOR_TAG and length and LENGTH_RANK.get(length, 3) < MIN_LENGTH_FOR_TAG[candidate]:
            return True
        if candidate == "dark_roots" and base in DARK_BASE_COLORS:
            return True
        if candidate in {"bob_cut", "layer_bob", "pixie_cut", "bixie_cut", "pageboy_cut", "inverted_bob", "a_line_bob"} and arrangement in {"ponytail", "high_ponytail", "low_ponytail", "side_ponytail", "twintails", "single_braid", "side_braid", "twin_braids"}:
            return True
        if shape and candidate in SHAPE_DISALLOWED_ARRANGEMENTS.get(shape, set()):
            return True
        if arrangement and candidate in {"pixie_cut", "layer_bob", "jellyfish_cut", "drill_hair"} and arrangement in SHAPE_DISALLOWED_ARRANGEMENTS.get(candidate, set()):
            return True
        return False

    def _weighted_pool(
        self,
        dotted_slot: str,
        data: Dict[str, Any],
        struct: Dict[str, Dict[str, List[str]]],
        matched_scores: Dict[str, int],
        mood: str,
        culture: str,
        gender: str,
        gender_strength: float,
        culture_strength: float,
        use_extended: bool,
        avoid_tags: Sequence[str],
        richness: str,
    ) -> Dict[str, int]:
        entries = data["entries"]
        by_slot = data["by_slot"]
        pool = self._merge_slot_weights(dotted_slot, mood, culture, gender, gender_strength, culture_strength)
        if not pool:
            fallback_weight = 2 if dotted_slot in CORE_SLOTS else 1
            pool = {tag: fallback_weight for tag in by_slot.get(dotted_slot, [])}
        current_tags = self._flatten_struct(struct)
        limit = self._slot_limit(richness, dotted_slot)
        if len(self._slot_values(struct, dotted_slot)) >= limit and dotted_slot in MULTI_SLOTS:
            return {}

        weighted: Dict[str, int] = {}
        for tag, weight in pool.items():
            if tag in current_tags and dotted_slot not in MULTI_SLOTS:
                continue
            if not self._allowed_tag(tag, entries, use_extended, avoid_tags):
                continue
            entry = entries.get(tag)
            if not entry:
                continue
            if f"{entry['block']}.{entry['slot']}" != dotted_slot:
                continue
            if self._violates_rules(struct, tag):
                continue
            score = int(weight)
            score += int(matched_scores.get(tag, 0)) * 3
            score += self._compatibility_bonus(tag, current_tags, mood, culture)
            weighted[tag] = max(1, score)
        return weighted

    def _apply_explicit_tags(
        self,
        struct: Dict[str, Dict[str, List[str]]],
        tags: Sequence[str],
        entries: Dict[str, Dict[str, Any]],
        avoid_tags: Sequence[str],
    ) -> List[str]:
        applied: List[str] = []
        for tag in tags:
            entry = entries.get(tag)
            if not entry or tag in avoid_tags:
                continue
            dotted = f"{entry['block']}.{entry['slot']}"
            if dotted in MULTI_SLOTS:
                self._append_multi(struct, dotted, tag)
            else:
                self._set_single(struct, dotted, tag)
            applied.append(tag)
        return applied

    def _choose_bundle(
        self,
        context_text: str,
        current_tags: Sequence[str],
        mood: str,
        culture: str,
        gender: str,
        richness: str,
        rng: random.Random,
        deterministic: bool,
    ) -> Optional[Dict[str, Any]]:
        normalized_context = self._normalize_key(context_text)
        scored: Dict[str, int] = {}
        bundles_by_name = {bundle["name"]: bundle for bundle in BUNDLE_PRESETS}
        for bundle in BUNDLE_PRESETS:
            score = int(bundle.get("weight", 1))
            if culture in bundle.get("cultures", []):
                score += 12
            if mood in bundle.get("moods", []):
                score += 10
            if gender in bundle.get("genders", [gender, "neutral"]):
                score += 4
            elif bundle.get("genders"):
                score -= 4
            overlap = len(set(bundle.get("tags", [])) & set(current_tags))
            score += overlap * 8
            for keyword in bundle.get("keywords", []):
                key = self._normalize_key(keyword)
                if key and key in normalized_context:
                    score += 10
            if richness == "minimal" and len(bundle.get("tags", [])) > 8:
                score -= 2
            if score > 0:
                scored[bundle["name"]] = score
        if not scored:
            return None
        if deterministic:
            chosen_name = sorted(scored.items(), key=lambda item: (-item[1], item[0]))[0][0]
        else:
            max_score = max(scored.values())
            shortlist = {name: value for name, value in scored.items() if value >= max_score * 0.80}
            chosen_name = self._weighted_choice(shortlist, rng, deterministic=False)
        return bundles_by_name.get(chosen_name) if chosen_name else None

    def _apply_bundle(
        self,
        struct: Dict[str, Dict[str, List[str]]],
        bundle: Optional[Dict[str, Any]],
        data: Dict[str, Any],
        use_extended: bool,
        avoid_tags: Sequence[str],
        richness: str,
    ) -> List[str]:
        if not bundle:
            return []
        entries = data["entries"]
        applied: List[str] = []
        for tag in bundle.get("tags", []):
            entry = entries.get(tag)
            if not entry:
                continue
            dotted = f"{entry['block']}.{entry['slot']}"
            if not self._allowed_tag(tag, entries, use_extended, avoid_tags):
                continue
            if self._violates_rules(struct, tag):
                continue
            if dotted in MULTI_SLOTS:
                if len(self._slot_values(struct, dotted)) >= self._slot_limit(richness, dotted):
                    continue
                if tag not in self._slot_values(struct, dotted):
                    self._append_multi(struct, dotted, tag)
                    applied.append(tag)
            else:
                current = self._slot_values(struct, dotted)
                if not current:
                    self._set_single(struct, dotted, tag)
                    applied.append(tag)
        return applied

    def _fill_missing_slots(
        self,
        struct: Dict[str, Dict[str, List[str]]],
        data: Dict[str, Any],
        matched_scores: Dict[str, int],
        mood: str,
        culture: str,
        gender: str,
        gender_strength: float,
        culture_strength: float,
        fill_mode: str,
        richness: str,
        use_extended: bool,
        avoid_tags: Sequence[str],
        rng: random.Random,
        has_source_tags: bool,
    ) -> Dict[str, List[str]]:
        fills: Dict[str, List[str]] = {}
        deterministic = fill_mode == "basic"
        for dotted_slot in SLOT_ORDER:
            limit = self._slot_limit(richness, dotted_slot)
            current = self._slot_values(struct, dotted_slot)
            if dotted_slot in MULTI_SLOTS:
                while len(current) < limit:
                    probability = self._slot_probability(dotted_slot, mood, culture, richness)
                    if fill_mode == "off":
                        break
                    if fill_mode == "basic":
                        break
                    if has_source_tags and dotted_slot in {"style.extra", "color.pattern", "texture.state"}:
                        probability *= 0.45
                    if rng.random() > probability:
                        break
                    pool = self._weighted_pool(dotted_slot, data, struct, matched_scores, mood, culture, gender, gender_strength, culture_strength, use_extended, avoid_tags, richness)
                    pick = self._weighted_choice(pool, rng, deterministic=False)
                    if not pick:
                        break
                    self._append_multi(struct, dotted_slot, pick)
                    fills.setdefault(dotted_slot, []).append(pick)
                    current = self._slot_values(struct, dotted_slot)
                continue

            if current:
                continue
            if fill_mode == "off":
                continue
            if fill_mode == "basic" and dotted_slot not in CORE_SLOTS | CONSERVATIVE_BASIC_SLOTS:
                continue
            probability = self._slot_probability(dotted_slot, mood, culture, richness)
            if dotted_slot not in CORE_SLOTS:
                if fill_mode == "basic" and probability < 0.55:
                    continue
                if fill_mode == "random":
                    if has_source_tags and dotted_slot in {"style.arrangement", "texture.volume", "texture.irregularity", "color.pattern", "style.extra", "texture.state"}:
                        probability *= 0.55
                    if rng.random() > probability:
                        continue
            pool = self._weighted_pool(dotted_slot, data, struct, matched_scores, mood, culture, gender, gender_strength, culture_strength, use_extended, avoid_tags, richness)
            pick = self._weighted_choice(pool, rng, deterministic=deterministic)
            if pick:
                self._set_single(struct, dotted_slot, pick)
                fills[dotted_slot] = [pick]
        return fills

    def _enforce_consistency(self, struct: Dict[str, Dict[str, List[str]]], mood: str, culture: str, richness: str) -> List[str]:
        changes: List[str] = []
        length = next(iter(struct["style"].get("length", [])), "")
        shape = next(iter(struct["style"].get("shape", [])), "")
        arrangement = next(iter(struct["style"].get("arrangement", [])), "")
        base = next(iter(struct["color"].get("base", [])), "")

        if shape in SHAPE_TO_NATURAL_LENGTH:
            target_length = SHAPE_TO_NATURAL_LENGTH[shape]
            current_rank = LENGTH_RANK.get(length, 3)
            target_rank = LENGTH_RANK.get(target_length, 3)
            if not length or abs(current_rank - target_rank) >= 2:
                struct["style"]["length"] = [target_length]
                changes.append(f"length_adjusted_for_shape:{target_length}")
                length = target_length

        if arrangement in MIN_LENGTH_FOR_TAG and LENGTH_RANK.get(length, 3) < MIN_LENGTH_FOR_TAG[arrangement]:
            needed_length = sorted(LENGTH_RANK.items(), key=lambda item: item[1])
            chosen_length = length
            for tag, rank in needed_length:
                if rank >= MIN_LENGTH_FOR_TAG[arrangement]:
                    chosen_length = tag
                    break
            struct["style"]["length"] = [chosen_length]
            changes.append(f"length_adjusted_for_arrangement:{chosen_length}")
            length = chosen_length

        if arrangement in {"bob_cut", "layer_bob", "bixie_cut", "pageboy_cut", "inverted_bob", "a_line_bob"} and LENGTH_RANK.get(length, 3) > LENGTH_RANK["shoulder_length_hair"]:
            struct["style"]["length"] = ["short_hair"]
            changes.append("length_reduced_for_bob_family:short_hair")
            length = "short_hair"

        if culture == "korean" and not struct["style"]["parting"]:
            struct["style"]["parting"] = ["center_part"]
            changes.append("parting_added_for_korean:center_part")
        if culture == "nordic" and not struct["style"]["shape"]:
            struct["style"]["shape"] = ["soft_waves"]
            changes.append("shape_added_for_nordic:soft_waves")
        if mood == "elegant" and not struct["texture"]["surface"]:
            struct["texture"]["surface"] = ["silky_hair"]
            changes.append("surface_added_for_elegant:silky_hair")

        if base in DARK_BASE_COLORS and "dark_roots" in struct["color"].get("pattern", []):
            struct["color"]["pattern"] = [tag for tag in struct["color"]["pattern"] if tag != "dark_roots"]
            changes.append("pattern_removed_dark_roots")

        if richness == "minimal":
            struct["style"]["extra"] = []
            struct["color"]["pattern"] = []
            struct["texture"]["state"] = []
            struct["texture"]["irregularity"] = []
            changes.append("simplified_for_minimal")
        return changes

    def _apply_soft_conflicts(self, tags: List[str], conflicts: Dict[str, Any]) -> List[str]:
        current = list(tags)
        for rule in conflicts.get("soft_conflicts", []):
            members = [str(tag) for tag in rule.get("tags", [])]
            present = [tag for tag in members if tag in current]
            if len(present) < 2:
                continue
            prefer = str(rule.get("prefer", present[0]))
            current = [tag for tag in current if tag not in members or tag == prefer]
        return current

    def _trim_by_richness(self, struct: Dict[str, Dict[str, List[str]]], data: Dict[str, Any], richness: str) -> List[str]:
        limits = RICHNESS_SLOT_LIMITS.get(richness, RICHNESS_SLOT_LIMITS["balanced"])
        ordered_slots = data["output_order"].get("order", SLOT_ORDER)
        tags = []
        for dotted_slot in ordered_slots:
            block, slot = dotted_slot.split(".", 1)
            slot_tags = list(struct.get(block, {}).get(slot, []))
            if dotted_slot in MULTI_SLOTS:
                slot_tags = slot_tags[: int(limits.get(dotted_slot, 1))]
            for tag in slot_tags:
                if tag not in tags:
                    tags.append(tag)
        for tag in self._flatten_struct(struct):
            if tag not in tags:
                tags.append(tag)
        total_limit = int(limits.get("total", 7))
        return tags[:total_limit]

    def _sort_output_tags(self, struct: Dict[str, Dict[str, List[str]]], data: Dict[str, Any]) -> List[str]:
        ordered: List[str] = []
        for dotted_slot in data["output_order"].get("order", SLOT_ORDER):
            block, slot = dotted_slot.split(".", 1)
            for tag in struct.get(block, {}).get(slot, []):
                if tag not in ordered:
                    ordered.append(tag)
        for tag in self._flatten_struct(struct):
            if tag not in ordered:
                ordered.append(tag)
        return ordered

    def _make_summary(self, tags: Sequence[str], entries: Dict[str, Dict[str, Any]], language: str) -> str:
        lang = normalize_output_language(language)
        labels: List[str] = []
        for tag in tags:
            entry = entries.get(tag, {})
            label = entry.get("label_ja") if lang == "Japanese" else entry.get("label_en")
            labels.append(str(label or tag))
        if not labels:
            return "髪情報なし" if lang == "Japanese" else "No hair information"
        return "、".join(labels) if lang == "Japanese" else ", ".join(labels)

    def build_hair(
        self,
        character_text,
        hairstyle_hint,
        texture_hint,
        color_hint,
        language,
        use_extended_dictionary,
        gender_mode,
        gender_strength,
        culture_mode,
        culture_strength,
        fill_missing,
        richness,
        save_dir,
        save_name,
        manual_tags="",
        must_tags="",
        prefer_tags="",
        avoid_tags="",
        seed=0,
    ):
        data = self._load_data()
        entries = data["entries"]
        alias_map = data["alias_map"]
        conflicts = data["conflicts"]
        use_extended = str(use_extended_dictionary).lower() == "true"
        fill_mode = str(fill_missing).lower()
        richness_mode = self._normalize_mode(richness, RICHNESS_SLOT_LIMITS.keys(), "balanced")
        g_strength = max(0.0, min(1.0, float(gender_strength or 0.0)))
        c_strength = max(0.0, min(1.0, float(culture_strength or 0.0)))

        source_text = " ".join([
            self._clean_text(character_text),
            self._clean_text(hairstyle_hint),
            self._clean_text(texture_hint),
            self._clean_text(color_hint),
            self._clean_text(manual_tags),
            self._clean_text(must_tags),
            self._clean_text(prefer_tags),
        ]).strip()

        actual_seed = int(seed or 0)
        if fill_mode == "random" and actual_seed == 0:
            actual_seed = time.time_ns() % 2147483647 or 1
        rng = random.Random(actual_seed)
        deterministic = fill_mode == "basic"

        explicit_must_tags = self._resolve_explicit_tag_list(alias_map, manual_tags, must_tags)
        explicit_prefer_tags = self._resolve_explicit_tag_list(alias_map, prefer_tags)
        explicit_avoid_tags = self._resolve_explicit_tag_list(alias_map, avoid_tags)

        effective_gender, gender_scores = self._infer_effective_gender(source_text, gender_mode)

        style_scores = self._merge_scores(
            self._score_matches(character_text, alias_map),
            self._score_matches(hairstyle_hint, alias_map),
        )
        texture_scores = self._merge_scores(
            self._score_matches(character_text, alias_map),
            self._score_matches(texture_hint, alias_map),
        )
        color_scores = self._merge_scores(
            self._score_matches(character_text, alias_map),
            self._score_matches(color_hint, alias_map),
        )
        all_scores = self._merge_scores(style_scores, texture_scores, color_scores)
        for tag in explicit_prefer_tags:
            all_scores[tag] = all_scores.get(tag, 0) + 28
        for tag in explicit_must_tags:
            all_scores[tag] = all_scores.get(tag, 0) + 120
        for tag in explicit_avoid_tags:
            all_scores.pop(tag, None)

        struct = self._empty_struct()
        explicit_applied = self._apply_explicit_tags(struct, explicit_must_tags, entries, explicit_avoid_tags)

        current_tags = self._flatten_struct(struct)
        mood, mood_scores = self._infer_profile(source_text, MOOD_PROFILES, current_tags, "auto", "natural", rng, deterministic)
        culture, culture_scores = self._infer_profile(source_text, CULTURE_PROFILES, current_tags, culture_mode, "neutral", rng, deterministic)

        bundle = self._choose_bundle(source_text, current_tags, mood, culture, effective_gender, richness_mode, rng, deterministic)
        bundle_applied = self._apply_bundle(struct, bundle, data, use_extended, explicit_avoid_tags, richness_mode)

        current_tags = self._flatten_struct(struct)
        mood, mood_scores = self._infer_profile(source_text, MOOD_PROFILES, current_tags, "auto", mood, rng, deterministic)
        culture, culture_scores = self._infer_profile(source_text, CULTURE_PROFILES, current_tags, culture_mode, culture, rng, deterministic)

        explicit_prefer_applied = self._apply_explicit_tags(struct, explicit_prefer_tags, entries, explicit_avoid_tags)

        profile_fills = self._fill_missing_slots(
            struct=struct,
            data=data,
            matched_scores=all_scores,
            mood=mood,
            culture=culture,
            gender=effective_gender,
            gender_strength=g_strength,
            culture_strength=c_strength,
            fill_mode=fill_mode,
            richness=richness_mode,
            use_extended=use_extended,
            avoid_tags=explicit_avoid_tags,
            rng=rng,
            has_source_tags=bool(self._clean_text(source_text)),
        )

        consistency_changes = self._enforce_consistency(struct, mood, culture, richness_mode)
        ordered_tags = self._sort_output_tags(struct, data)
        ordered_tags = [tag for tag in ordered_tags if tag not in explicit_avoid_tags]
        ordered_tags = self._apply_soft_conflicts(ordered_tags, conflicts)
        struct = self._rebuild_struct(ordered_tags, entries)
        trimmed_tags = self._trim_by_richness(struct, data, richness_mode)
        trimmed_tags = [tag for tag in trimmed_tags if tag not in explicit_avoid_tags]
        struct = self._rebuild_struct(trimmed_tags, entries)
        output_tags = self._sort_output_tags(struct, data)

        hair_prompt = ", ".join(output_tags)
        hair_summary = self._make_summary(output_tags, entries, language)
        hair_struct_json = json.dumps(struct, ensure_ascii=False, indent=2)

        base_dir_str, save_name_out, base_dir = ensure_save_context(save_dir, save_name, "hair_builder")
        txt_path = base_dir / f"{save_name_out}_hair_prompt.txt"
        json_path = base_dir / f"{save_name_out}_hair.json"

        debug_payload = {
            "save_name": save_name_out,
            "settings": {
                "language": language,
                "use_extended_dictionary": use_extended,
                "gender_mode": str(gender_mode),
                "effective_gender_mode": effective_gender,
                "gender_strength": g_strength,
                "culture_mode": str(culture_mode),
                "effective_culture_mode": culture,
                "culture_strength": c_strength,
                "fill_missing": fill_mode,
                "richness": richness_mode,
                "seed": actual_seed,
                "save_dir": base_dir_str,
            },
            "inputs": {
                "character_text": character_text,
                "hairstyle_hint": hairstyle_hint,
                "texture_hint": texture_hint,
                "color_hint": color_hint,
                "manual_tags": manual_tags,
                "must_tags": must_tags,
                "prefer_tags": prefer_tags,
                "avoid_tags": avoid_tags,
                "resolved_must_tags": explicit_must_tags,
                "resolved_prefer_tags": explicit_prefer_tags,
                "resolved_avoid_tags": explicit_avoid_tags,
            },
            "profile_debug": {
                "gender_scores": gender_scores,
                "mood_scores": dict(sorted(mood_scores.items(), key=lambda item: (-item[1], item[0]))),
                "culture_scores": dict(sorted(culture_scores.items(), key=lambda item: (-item[1], item[0]))),
                "bundle": bundle["name"] if bundle else None,
                "bundle_tags": list(bundle.get("tags", [])) if bundle else [],
            },
            "generation_debug": {
                "matched_scores": dict(sorted(all_scores.items(), key=lambda item: (-item[1], item[0]))),
                "explicit_applied": explicit_applied,
                "bundle_applied": bundle_applied,
                "prefer_applied": explicit_prefer_applied,
                "profile_fills": profile_fills,
                "consistency_changes": consistency_changes,
                "ordered_tags": output_tags,
            },
            "outputs": {
                "hair_prompt": hair_prompt,
                "hair_summary": hair_summary,
                "hair_struct": struct,
            },
            "paths": {
                "txt_path": str(txt_path),
                "json_path": str(json_path),
            },
        }

        write_text(txt_path, hair_prompt)
        write_json(json_path, debug_payload)
        debug_json = json.dumps(debug_payload, ensure_ascii=False, indent=2)
        return hair_prompt, hair_summary, hair_struct_json, debug_json
