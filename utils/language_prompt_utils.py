from __future__ import annotations


def normalize_output_language(language: str) -> str:
    lang = (language or '').strip().lower()
    if lang.startswith('ja') or 'japanese' in lang or lang == '日本語':
        return 'Japanese'
    return 'English'


def output_language_instruction(language: str, *, json_mode: bool = False, tag_mode: bool = False) -> str:
    lang = normalize_output_language(language)
    if json_mode:
        if lang == 'Japanese':
            return (
                'The final output language is Japanese. Keep the JSON schema keys in English exactly as requested, '
                'but write every user-facing string value in Japanese only. Do not write English in the JSON values unless '
                'the input explicitly requires quoted English text.'
            )
        return (
            'The final output language is English. Keep the JSON schema keys in English exactly as requested, '
            'and write every user-facing string value in English only.'
        )
    if tag_mode:
        if lang == 'Japanese':
            return (
                'The final output language is Japanese. Return Japanese tags only. '
                'Do not switch to English tags unless the input explicitly requires quoted English text.'
            )
        return 'The final output language is English. Return English tags only.'
    if lang == 'Japanese':
        return 'The final output language is Japanese. Return Japanese only. Do not switch to English unless the input explicitly requires quoted English text.'
    return 'The final output language is English. Return English only.'
