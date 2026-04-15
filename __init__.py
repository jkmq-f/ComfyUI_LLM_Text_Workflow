from .nodes.story_node import LLMStoryNode
from .nodes.story_tags_node import LLMStoryTagsNode
from .nodes.cut_tags_node import LLMCutTagsNode
from .nodes.story_cuts_node import LLMStoryCutsNode
from .nodes.video_prompt_node import LLMVideoPromptNode
from .nodes.text_view_node import LLMTextViewNode
from .nodes.model_prompt_converter_node import LLMPromptConverterNode, LLMPromptConverter8Node
from .nodes.save_text_node import LLMSaveTextNode, LLMSaveText8Node

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
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
