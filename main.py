import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter.messagebox import showerror
from concurrent.futures import ThreadPoolExecutor

def format_size(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def get_dir_size(path):
    total = 0
    for root, dirs, files in os.walk(path, topdown=True):
        for name in files:
            try:
                fp = os.path.join(root, name)
                total += os.path.getsize(fp)
            except:
                continue
    return total

def list_dir_with_skipped(path, min_size_mb):
    visible_items = []
    skipped_total_size = 0
    entries = []
    try:
        with os.scandir(path) as scan:
            entries = [entry for entry in scan]
    except Exception as e:
        showerror("读取失败", str(e))
        return [], 0

    lock = threading.Lock()

    def process_entry(entry):
        nonlocal skipped_total_size
        try:
            size = get_dir_size(entry.path) if entry.is_dir(follow_symlinks=False) else entry.stat().st_size
            if size >= min_size_mb * 1024 * 1024:
                with lock:
                    visible_items.append((entry.name, size, entry.is_dir()))
            else:
                with lock:
                    skipped_total_size += size
        except:
            pass

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(process_entry, entries)

    return sorted(visible_items, key=lambda x: x[1], reverse=True), skipped_total_size

class DiskBrowserGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📁 文件夹大小查看工具")
        self.geometry("800x650")
        self.configure(bg="#f5f5f5")
        self.current_path = os.path.abspath(".")
        self.min_size_mb = tk.IntVar(value=0)

        # 顶部路径显示 + 跳过提示 + 进度条
        self.top_frame = tk.Frame(self, bg="#f5f5f5")
        self.top_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.path_label = tk.Label(self.top_frame, text=self.current_path, font=("Segoe UI", 10), anchor='w', bg="#f5f5f5")
        self.path_label.pack(fill=tk.X)

        self.skip_label = tk.Label(self.top_frame, text="", anchor="w", font=("Segoe UI", 9), bg="#f5f5f5", fg="#888888")
        self.skip_label.pack(fill=tk.X, pady=(5, 2))

        self.progress = ttk.Progressbar(self.top_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X)
        self.progress.pack_forget()

        # 控制栏
        control_frame = tk.Frame(self, bg="#f5f5f5")
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(control_frame, text="最小显示大小(MB):", font=("Segoe UI", 10), bg="#f5f5f5").pack(side=tk.LEFT)
        self.size_slider = tk.Scale(control_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.min_size_mb,
                            bg="#f5f5f5")
        self.size_slider.pack(side=tk.LEFT, padx=(5, 10))

        self.btn_choose = ttk.Button(control_frame, text="选择目录", command=self.choose_directory)
        self.btn_choose.pack(side=tk.LEFT, padx=5)
        self.btn_up = ttk.Button(control_frame, text="返回上一级", command=self.go_up)
        self.btn_up.pack(side=tk.LEFT, padx=5)
        self.btn_refresh = ttk.Button(control_frame, text="刷新", command=self.refresh)
        self.btn_refresh.pack(side=tk.LEFT, padx=5)

        # 文件列表
        self.tree = ttk.Treeview(self, columns=('Name', 'Size'), show='headings')
        self.tree.heading('Name', text='名称')
        self.tree.heading('Size', text='大小')
        self.tree.column('Name', width=500)
        self.tree.column('Size', width=120, anchor='e')
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.tree.bind("<Double-1>", self.on_double_click)

        self.refresh()

    def choose_directory(self):
        new_path = filedialog.askdirectory(initialdir=self.current_path)
        if new_path:
            self.current_path = new_path
            self.refresh()

    def go_up(self):
        parent = os.path.dirname(self.current_path)
        if os.path.exists(parent):
            self.current_path = parent
            self.refresh()

    def refresh(self):
        self.set_controls_state("disabled")
        self.path_label.config(text=self.current_path)
        self.tree.delete(*self.tree.get_children())
        self.progress.pack(fill=tk.X)
        self.progress.start()
        self.skip_label.config(text="")

        thread = threading.Thread(target=self._load_data)
        thread.start()

    def _load_data(self):
        data, skipped_size = list_dir_with_skipped(self.current_path, self.min_size_mb.get())

        def update_ui():
            self.progress.stop()
            self.progress.pack_forget()
            for name, size, is_dir in data:
                display_name = f"📁 {name}" if is_dir else name
                self.tree.insert('', 'end', values=(display_name, format_size(size)))
            if skipped_size > 0 and self.min_size_mb.get() > 0:
                self.skip_label.config(
                    text=f"⚠️ 有部分文件未显示（小于 {self.min_size_mb.get()} MB），共占用：{format_size(skipped_size)}")
            self.set_controls_state("normal")

        self.after(100, update_ui)

    def on_double_click(self, event):
        selected = self.tree.focus()
        if selected:
            name = self.tree.item(selected)['values'][0]
            if name.startswith("📁 "):
                name = name[2:]
            next_path = os.path.join(self.current_path, name)
            if os.path.isdir(next_path):
                self.current_path = next_path
                self.refresh()

    def set_controls_state(self, state):
        for widget in [self.btn_choose, self.btn_up, self.btn_refresh, self.size_slider]:
            widget.config(state=state)

if __name__ == "__main__":
    app = DiskBrowserGUI()
    app.mainloop()
