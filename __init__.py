from .nodes.story_node import LLMStoryNode
from .nodes.story_tags_node import LLMStoryTagsNode
from .nodes.cut_tags_node import LLMCutTagsNode
from .nodes.story_cuts_node import LLMStoryCutsNode
from .nodes.video_prompt_node import LLMVideoPromptNode
from .nodes.text_view_node import LLMTextViewNode
from .nodes.model_prompt_converter_node import LLMPromptConverterNode, LLMPromptConverter8Node
from .nodes.save_text_node import LLMSaveTextNode, LLMSaveText8Node
from .nodes.character_generator_node import LLMCharacterGeneratorNode
from .nodes.random_persona_speech_node import LLMRandomPersonaSpeechNode
from .nodes.outfit_generator_node import LLMOutfitGeneratorNode
from .nodes.outfit_texture_node import LLMOutfitTextureNode
from .nodes.outfit_color_node import LLMOutfitColorNode
from .nodes.story_to_lyrics_node import LLMStoryToLyricsNode
from .nodes.translate_simple_node import LLMSimpleTranslateNode
from .nodes.hair_builder_node import LLMHairBuilderNode

WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "LLMStoryGenerator": LLMStoryNode,
    "LLMStoryTags": LLMStoryTagsNode,
    "LLMCutTags": LLMCutTagsNode,
    "LLMStoryCuts": LLMStoryCutsNode,
    "LLMVideoPrompt": LLMVideoPromptNode,
    "LLMTextView": LLMTextViewNode,
    "LLMPromptConverter": LLMPromptConverterNode,
    "LLMPromptConverter8": LLMPromptConverter8Node,
    "LLMSaveText": LLMSaveTextNode,
    "LLMSaveText8": LLMSaveText8Node,
    "LLMCharacterGenerator": LLMCharacterGeneratorNode,
    "LLMRandomPersonaSpeech": LLMRandomPersonaSpeechNode,
    "LLMOutfitGenerator": LLMOutfitGeneratorNode,
    "LLMOutfitTexture": LLMOutfitTextureNode,
    "LLMOutfitColor": LLMOutfitColorNode,
    "LLMStoryToLyrics": LLMStoryToLyricsNode,
    "LLMSimpleTranslate": LLMSimpleTranslateNode,
    "LLMHairBuilder": LLMHairBuilderNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LLMStoryGenerator": "LLM Story Generator",
    "LLMStoryTags": "LLM Story Tags",
    "LLMCutTags": "LLM Cut Tags",
    "LLMStoryCuts": "LLM Story Cuts",
    "LLMVideoPrompt": "LLM Video Prompt",
    "LLMTextView": "LLM Text View",
    "LLMPromptConverter": "LLM Prompt Converter",
    "LLMPromptConverter8": "LLM Prompt Converter 8",
    "LLMSaveText": "LLM Save Text",
    "LLMSaveText8": "LLM Save Text 8",
    "LLMCharacterGenerator": "LLM Character Generator",
    "LLMRandomPersonaSpeech": "LLM Random Persona Speech",
    "LLMOutfitGenerator": "LLM Outfit Generator",
    "LLMOutfitTexture": "LLM Outfit Texture",
    "LLMOutfitColor": "LLM Outfit Color",
    "LLMStoryToLyrics": "LLM Story To Lyrics",
    "LLMSimpleTranslate": "LLM Simple Translate",
    "LLMHairBuilder": "LLM Hair Builder",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
