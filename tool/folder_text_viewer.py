#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

TEXT_EXTENSIONS = {".txt", ".json", ".md", ".log", ".csv", ".yaml", ".yml"}


class FolderTextViewer(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Folder Text Viewer")
        self.geometry("1320x840")
        self.minsize(1000, 680)

        self.current_dir = tk.StringVar()
        self.filter_var1 = tk.StringVar()
        self.filter_var2 = tk.StringVar()
        self.status_var = tk.StringVar(value="フォルダを選んでください。")
        self.preview_mode_var = tk.StringVar(value="pretty")
        self.file_count_var = tk.StringVar(value="0 files")
        self.filter_mode_var = tk.StringVar(value="and")

        self.file_paths: list[Path] = []
        self.filtered_paths: list[Path] = []

        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Folder").pack(side=tk.LEFT, padx=(0, 6))
        self.dir_entry = ttk.Entry(top, textvariable=self.current_dir)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(top, text="参照", command=self.choose_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="再読込", command=self.reload_folder).pack(side=tk.LEFT, padx=4)

        mid = ttk.Frame(self, padding=(8, 0, 8, 8))
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        left = ttk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.Y)

        filter_row = ttk.Frame(left)
        filter_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

        ttk.Label(filter_row, text="Filter 1").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.filter_entry1 = ttk.Entry(filter_row, textvariable=self.filter_var1, width=18)
        self.filter_entry1.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        ttk.Label(filter_row, text="Filter 2").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
        self.filter_entry2 = ttk.Entry(filter_row, textvariable=self.filter_var2, width=18)
        self.filter_entry2.grid(row=1, column=1, sticky="ew", padx=(0, 6), pady=(4, 0))

        mode_frame = ttk.Frame(filter_row)
        mode_frame.grid(row=0, column=2, rowspan=2, sticky="ns", padx=(0, 6))
        ttk.Label(mode_frame, text="Mode").pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="AND", value="and", variable=self.filter_mode_var, command=self.apply_filter).pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="OR", value="or", variable=self.filter_mode_var, command=self.apply_filter).pack(anchor="w")

        btn_frame = ttk.Frame(filter_row)
        btn_frame.grid(row=0, column=3, rowspan=2, sticky="ns")
        ttk.Button(btn_frame, text="絞込", command=self.apply_filter).pack(fill="x")
        ttk.Button(btn_frame, text="クリア", command=self.clear_filter).pack(fill="x", pady=(4, 0))

        filter_row.columnconfigure(1, weight=1)

        list_info = ttk.Frame(left)
        list_info.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        ttk.Label(list_info, textvariable=self.file_count_var).pack(side=tk.LEFT)

        self.listbox = tk.Listbox(left, width=48, activestyle="dotbox", exportselection=False)
        self.listbox.pack(side=tk.LEFT, fill=tk.Y, expand=False)

        list_scroll = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.listbox.yview)
        list_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=list_scroll.set)

        right = ttk.Frame(mid)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        header = ttk.Frame(right)
        header.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

        self.file_label = ttk.Label(header, text="ファイル未選択", font=("", 10, "bold"))
        self.file_label.pack(side=tk.LEFT, anchor="w")

        mode_box = ttk.Frame(header)
        mode_box.pack(side=tk.RIGHT)

        ttk.Label(mode_box, text="JSON表示").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Radiobutton(mode_box, text="整形", value="pretty", variable=self.preview_mode_var, command=self.refresh_current_preview).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_box, text="生", value="raw", variable=self.preview_mode_var, command=self.refresh_current_preview).pack(side=tk.LEFT)

        btn_row = ttk.Frame(right)
        btn_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 6))

        ttk.Button(btn_row, text="本文コピー", command=self.copy_text).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(btn_row, text="パスコピー", command=self.copy_path).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="全選択", command=self.select_all_text).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="テキスト保存", command=self.save_current_text_as).pack(side=tk.LEFT, padx=4)

        self.text = tk.Text(
            right,
            wrap="word",
            undo=True,
            font=("TkDefaultFont", 10),
            padx=10,
            pady=10,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.text.yview)
        text_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.text.configure(yscrollcommand=text_scroll.set)

        bottom = ttk.Frame(self, padding=(8, 0, 8, 8))
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        self.status = ttk.Label(bottom, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status.pack(side=tk.TOP, fill=tk.X)

    def _bind_events(self) -> None:
        self.listbox.bind("<<ListboxSelect>>", self.on_select_file)
        self.filter_entry1.bind("<Return>", lambda e: self.apply_filter())
        self.filter_entry2.bind("<Return>", lambda e: self.apply_filter())
        self.dir_entry.bind("<Return>", lambda e: self.reload_folder())
        self.bind("<Control-f>", self._focus_filter1)
        self.bind("<Control-o>", lambda e: self.choose_folder())
        self.bind("<Control-r>", lambda e: self.reload_folder())
        self.bind("<Control-a>", self._select_all_hotkey)
        self.bind("<Control-c>", self._copy_hotkey)

    def _focus_filter1(self, _event=None):
        self.filter_entry1.focus_set()
        self.filter_entry1.select_range(0, tk.END)
        return "break"

    def _select_all_hotkey(self, _event=None):
        widget = self.focus_get()
        if widget is self.text:
            self.select_all_text()
            return "break"
        return None

    def _copy_hotkey(self, _event=None):
        widget = self.focus_get()
        if widget is self.text:
            try:
                selected = self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                selected = ""
            if selected:
                self._copy_to_clipboard(selected)
                self.status_var.set("選択テキストをコピーしました。")
                return "break"
        return None

    def choose_folder(self) -> None:
        path = filedialog.askdirectory(
            title="フォルダを選択",
            initialdir=self.current_dir.get() if self.current_dir.get() else os.getcwd(),
        )
        if not path:
            return
        self.current_dir.set(path)
        self.reload_folder()

    def reload_folder(self) -> None:
        raw_dir = self.current_dir.get().strip()
        if not raw_dir:
            self.status_var.set("フォルダパスを入力してください。")
            return

        folder = Path(raw_dir).expanduser()
        if not folder.exists():
            messagebox.showerror("エラー", f"フォルダが見つかりません。\n{folder}")
            return
        if not folder.is_dir():
            messagebox.showerror("エラー", f"フォルダではありません。\n{folder}")
            return

        try:
            files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            self.file_paths = files
            self.apply_filter()
            self.status_var.set(f"読込完了: {folder}")
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダの読込に失敗しました。\n\n{e}")

    def _matches_filters(self, name: str) -> bool:
        lower_name = name.lower()
        kw1 = self.filter_var1.get().strip().lower()
        kw2 = self.filter_var2.get().strip().lower()

        if not kw1 and not kw2:
            return True

        hit1 = (not kw1) or (kw1 in lower_name)
        hit2 = (not kw2) or (kw2 in lower_name)

        mode = self.filter_mode_var.get()
        if mode == "or":
            active1 = bool(kw1)
            active2 = bool(kw2)
            if active1 and active2:
                return (kw1 in lower_name) or (kw2 in lower_name)
            return hit1 and hit2
        return hit1 and hit2

    def apply_filter(self) -> None:
        self.filtered_paths = [p for p in self.file_paths if self._matches_filters(p.name)]

        self.listbox.delete(0, tk.END)
        for p in self.filtered_paths:
            self.listbox.insert(tk.END, p.name)

        self.file_count_var.set(f"{len(self.filtered_paths)} files")

        if self.filtered_paths:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self.show_file(self.filtered_paths[0])
        else:
            self.file_label.config(text="ファイル未選択")
            self.text.delete("1.0", tk.END)
            self.status_var.set("該当ファイルがありません。")

    def clear_filter(self) -> None:
        self.filter_var1.set("")
        self.filter_var2.set("")
        self.filter_mode_var.set("and")
        self.apply_filter()

    def on_select_file(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.filtered_paths):
            self.show_file(self.filtered_paths[idx])

    def refresh_current_preview(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.filtered_paths):
            self.show_file(self.filtered_paths[idx])

    def show_file(self, path: Path) -> None:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                raw = path.read_text(encoding="utf-8-sig")
            except Exception as e:
                raw = f"[読込失敗]\n{e}\n\n{traceback.format_exc()}"
        except Exception as e:
            raw = f"[読込失敗]\n{e}\n\n{traceback.format_exc()}"

        content = raw
        if path.suffix.lower() == ".json" and self.preview_mode_var.get() == "pretty":
            try:
                obj = json.loads(raw)
                content = json.dumps(obj, ensure_ascii=False, indent=2)
            except Exception:
                content = raw

        self.file_label.config(text=str(path))
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")

        try:
            size_kb = path.stat().st_size / 1024.0
            self.status_var.set(f"{path.name}  |  {size_kb:.1f} KB")
        except Exception:
            self.status_var.set(path.name)

    def get_current_path(self) -> Path | None:
        sel = self.listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if 0 <= idx < len(self.filtered_paths):
            return self.filtered_paths[idx]
        return None

    def copy_text(self) -> None:
        content = self.text.get("1.0", tk.END).rstrip("\n")
        self._copy_to_clipboard(content)
        self.status_var.set("本文をコピーしました。")

    def copy_path(self) -> None:
        path = self.get_current_path()
        if not path:
            return
        self._copy_to_clipboard(str(path))
        self.status_var.set("ファイルパスをコピーしました。")

    def select_all_text(self) -> None:
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        self.text.mark_set(tk.INSERT, "1.0")
        self.text.see(tk.INSERT)
        self.text.focus_set()

    def save_current_text_as(self) -> None:
        path = self.get_current_path()
        if not path:
            return

        save_path = filedialog.asksaveasfilename(
            title="テキスト保存",
            initialfile=path.name,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not save_path:
            return

        try:
            Path(save_path).write_text(self.text.get("1.0", tk.END), encoding="utf-8")
            self.status_var.set(f"保存しました: {save_path}")
        except Exception as e:
            messagebox.showerror("保存エラー", str(e))

    def _copy_to_clipboard(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()


if __name__ == "__main__":
    app = FolderTextViewer()
    app.mainloop()
