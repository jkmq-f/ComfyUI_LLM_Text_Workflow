# ComfyUI-LLM-Text-Workflow

ComfyUI 用のローカル LLM テキストワークフローです。  
ローカルの `.gguf` モデルを直接読み込み、物語生成、カット分割、タグ化、動画プロンプト化、モデル別プロンプト変換を ComfyUI 上でまとめて扱えます。

![](ui1.png)

## インストール

1. `ComfyUI/custom_nodes` に移動します。

2. このリポジトリを `git clone` します。

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/jkmq-f/ComfyUI-LLM-Text-Workflow.git
cd ComfyUI-LLM-Text-Workflow
python -m pip install -r requirements.txt
```

3. ComfyUI を再起動します。

## 必要環境

- ComfyUI
- Python 環境
- `llama-cpp-python`
- ローカルの `.gguf` モデル

## モデルパス

`model_path` には、ローカルの `.gguf` モデルファイルのフルパスを指定してください。

例:

```text
/home/yourname/models/your-model.gguf
```

## クイックスタート

基本的な流れは以下です。

1. **LLM Story Generator** を追加
2. `story_text` を生成
3. `story_text` を **LLM Story Cuts** へ接続
4. `cut_count` を設定して `cut_1` ～ `cut_8` を生成
5. 必要に応じて **LLM Story Tags** で物語全体のタグを生成
6. 必要に応じて **LLM Cut Tags** でカットごとのタグを生成
7. **LLM Video Prompt** でカットごとの動画プロンプトを生成

推奨の接続例:

```text
Story -> Story Cuts -> Video Prompt
     \-> Story Tags
     \-> Cut Tags
```

## ノード一覧

### 1. LLM Story Generator

シンプルな入力項目から物語を書くノードです。

**入力**
- `idea`
- `genre`
- `setting`
- `protagonist`
- `tone`
- `length`
- `language`
- `extra_requirements`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `story_text`

不足している情報があっても、自然に補いながら直接物語を書きます。

---

### 2. LLM Story Cuts

物語を複数の連続カットに分割するノードです。

**入力**
- `story_text`
- `cut_count`
- `language`
- `style`
- `extra_requirements`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `cut_1`
- `cut_2`
- `cut_3`
- `cut_4`
- `cut_5`
- `cut_6`
- `cut_7`
- `cut_8`

`cut_count` で生成するカット数を決めます。未使用の出力は空のままになります。

**`style` の選択肢**
- `scene_description`
- `video_prompt`
- `cinematic_video_prompt`
- `shot_prompt_dense`
- `simple_beat_sheet`

---

### 3. LLM Story Tags

物語全体を 1 行のタグ列へ変換するノードです。

**入力**
- `story_text`
- `tag_mode`
- `language`
- `max_tags`
- `extra_requirements`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `tags_text`

**`tag_mode` の選択肢**
- `general_keywords`
- `image_prompt_tags`
- `video_prompt_tags`
- `character_tags`

---

### 3a. LLM Cut Tags

各カットを個別のタグ列に変換するノードです。

**入力**
- `cut_1` ～ `cut_8`
- `cut_count`
- `tag_mode`
- `language`
- `max_tags_per_cut`
- `extra_requirements`
- `save_dir`
- `save_name`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `tag_1` ～ `tag_8`
- `all_cut_tags`
- `save_name_out`
- `cut_count_out`
- `cut_tags_json_path`

物語全体ではなく、カットごとのタグが欲しい時に使います。

---

### 4. LLM Video Prompt

各カットを動画用プロンプトへ変換するノードです。

**入力**
- `cut_1`
- `cut_2`
- `cut_3`
- `cut_4`
- `cut_5`
- `cut_6`
- `cut_7`
- `cut_8`
- `language`
- `prompt_style`
- `extra_requirements`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `prompt_1`
- `prompt_2`
- `prompt_3`
- `prompt_4`
- `prompt_5`
- `prompt_6`
- `prompt_7`
- `prompt_8`
- `all_prompts`

**`prompt_style` の選択肢**
- `cinematic_video_prompt`
- `shot_prompt_dense`
- `simple_visual_prompt`
- `sora_like`
- `ltx_like`

---

### 5. LLM Prompt Converter

物語やカットを、特定モデル向けのプロンプトに変換するノードです。

**入力**
- `input_text`
- `input_type`
- `mode`
- `language`
- `extra_requirements`
- `include_debug_text`
- `model_path`
- `load_strategy`
- `max_tokens`
- `temperature`
- `top_p`

**出力**
- `selected_output`
- `optional_debug_text`

**`mode` の選択肢**
- `Illustrious`
- `Z-Image`
- `Anima`

モデル別のプロンプト変換を 1 ノードで行いたい時に使います。

## 保存機能

すべての主要ノードは `save_dir` と `save_name` に対応しています。

- `save_dir`: `.json` や `.txt` を保存するフォルダ
- `save_name`: 共通のプロジェクト名。空欄の場合は自動生成

**主な出力**
- `LLM Story Generator` → `save_name_out`, `story_json_path`
- `LLM Story Cuts` → `save_name_out`, `cut_count_out`, `cuts_json_path`
- `LLM Story Tags` → `save_name_out`, `tags_json_path`
- `LLM Video Prompt` → `save_name_out`, `cut_count_out`, `video_prompts_json_path`

**推奨のつなぎ方**
- Story の `save_name_out` → Cuts の `save_name`
- Story の `save_name_out` → Tags の `save_name`
- Story の `save_name_out` → Video Prompt の `save_name`
- Cuts の `cut_count_out` → Video Prompt の `cut_count`

## 表示ノード

### LLM Text View
1 つのテキストを表示する確認用ノードです。  
物語本文、1 カット、タグ 1 行、単体プロンプトの確認に向いています。

### LLM Text View 8
8 個のテキストをまとめて表示する確認用ノードです。  
`cut_1` ～ `cut_8` や `tag_1` ～ `tag_8` の確認に向いています。

### 表示ノードの注意
- `LLM Text View` と `LLM Text View 8` は `js/text_view.js` のフロントエンド拡張を使います。
- カスタムノードを入れた後は、ComfyUI の再起動とブラウザの再読み込みを行ってください。
- 実行後、表示テキストはノード内に出ます。

## 保存ノード

### LLM Save Text
1 本のテキストを `txt` / `md` / `json` で保存するノードです。

### LLM Save Text 8
最大 8 本のテキストをまとめて保存するノードです。  
複数カットや複数タグの一括保存に向いています。

## メモ

- このワークフローは `llama-cpp-python` を使用します。
- `reload_every_run` を使うと、実行ごとにメモリを解放します。
- `<end_of_turn>` のような停止マーカーは出力から取り除かれます。
