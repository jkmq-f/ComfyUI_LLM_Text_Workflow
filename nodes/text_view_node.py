from __future__ import annotations


class LLMTextViewNode:
    CATEGORY = "text"
    FUNCTION = "show_text"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_out",)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text_in": ("STRING", {"forceInput": True}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def show_text(self, text_in):
        text = str(text_in or "")
        return {
            "ui": {
                "text": [text],
            },
            "result": (text,),
        }
