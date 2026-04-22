# Hair Dictionary

This package includes a directly bundled, knowledge-based maximal hair dictionary.

- No external CSV build step is required.
- The node reads the JSON files in this folder directly.
- This is **not** an official Danbooru mirror.
- It is a bundled knowledge-base vocabulary designed for the hair builder node.

## Counts

- Canonical tags: 1357
- Aliases: 3118

### Style
- length: 18
- front: 107
- parting: 36
- arrangement: 289
- shape: 274
- extra: 117

### Texture
- surface: 83
- volume: 56
- state: 48
- irregularity: 57

### Color
- base: 168
- pattern: 104

## Files

- `hair_style_dictionary.json`
- `hair_texture_dictionary.json`
- `hair_color_dictionary.json`
- `hair_aliases.json`
- `hair_conflicts.json`
- `hair_output_order.json`
- `hair_all_tags_flat.txt`
- `HAIR_KNOWLEDGE_BASE_MANIFEST.json`

## Note

`character_text` in the node is keyword-guided, not LLM semantic understanding.
For stronger control, prefer:
- `hairstyle_hint`
- `texture_hint`
- `color_hint`
- `must_tags`
- `prefer_tags`
- `avoid_tags`
