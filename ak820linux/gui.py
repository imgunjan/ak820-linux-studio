"""Screen editor and animated preview for the native Tk application."""

from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .images import PreparedImage, prepare_image, rgb565, text_card
from .preview import PreviewPlayer
from .protocol import Keyboard, find_device


class StudioApp:
    def __init__(self, root):
        self.root = root
        self.events = Queue()
        self.busy = False
        self.dirty = False
        self.content = None
        self.content_kind = None
        self.current_preview = None
        self.source_path = None
        self.controls = []
        self.status = tk.StringVar(
            value="Choose an image or write some text to prepare your screen."
        )
        self.source_label = tk.StringVar(value="No image selected")
        self.preview_label = tk.StringVar(
            value="Preview only — choose content to upload"
        )
        self.frame_label = tk.StringVar()
        self.details = tk.StringVar(value="128 × 128 pixels")
        self.progress = tk.DoubleVar(value=0)
        self.fit = tk.StringVar(value="cover")
        self.rotation = tk.StringVar(value="0")
        self.brightness = tk.StringVar(value="100")
        self.max_frames = tk.StringVar(value="60")
        self.speed = tk.StringVar(value="1")
        self.font_size = tk.StringVar(value="16")
        self.alignment = tk.StringVar(value="center")
        self.text_color = tk.StringVar(value="#ffffff")
        self.background_color = tk.StringVar(value="#101827")
        self._build()
        self.player = PreviewPlayer(root, self._show_frame)
        self.player.load([text_card("AK820 Linux")])
        for variable in (
            self.fit,
            self.rotation,
            self.brightness,
            self.max_frames,
            self.speed,
        ):
            variable.trace_add("write", lambda *_: self._mark_dirty("image"))
        for variable in (
            self.font_size,
            self.alignment,
            self.text_color,
            self.background_color,
        ):
            variable.trace_add("write", lambda *_: self._mark_dirty("text"))
        self.poll_timer = root.after(50, self._poll_events)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def _button(self, parent, text, command):
        button = ttk.Button(parent, text=text, command=command, style="App.TButton")
        self.controls.append((button, "normal"))
        return button

    def _option(self, parent, row, label, variable, values=None, limits=None):
        ttk.Label(parent, text=label, style="App.TLabel").grid(
            row=row, column=0, sticky="w", pady=4
        )
        if values is not None:
            widget = ttk.Combobox(
                parent, textvariable=variable, values=values, state="readonly", width=16
            )
            state = "readonly"
        else:
            widget = ttk.Spinbox(
                parent, textvariable=variable, from_=limits[0], to=limits[1], width=16
            )
            state = "normal"
        widget.grid(row=row, column=1, sticky="ew", padx=(16, 0), pady=4)
        self.controls.append((widget, state))

    def _build(self):
        root = self.root
        root.title("AK820 Linux Studio")
        root.geometry("900x690")
        root.minsize(840, 660)
        root.configure(bg="#111827")
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#111827")
        style.configure(
            "App.TLabel",
            background="#111827",
            foreground="#f8fafc",
            font=("DejaVu Sans", 10),
        )
        style.configure(
            "Muted.TLabel",
            background="#111827",
            foreground="#9ca3af",
            font=("DejaVu Sans", 9),
        )
        style.configure(
            "App.TButton", background="#374151", foreground="#f8fafc", padding=(12, 8)
        )
        style.map(
            "App.TButton", background=[("active", "#4b5563"), ("disabled", "#374151")]
        )
        style.configure("TNotebook", background="#111827", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 8))
        style.configure("TProgressbar", troughcolor="#374151", background="#22d3ee")

        outer = ttk.Frame(root, style="App.TFrame", padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(
            outer,
            text="AK820 LINUX STUDIO",
            foreground="#22d3ee",
            background="#111827",
            font=("DejaVu Sans", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Prepare your screen · Preview it here · Upload over wired USB",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 12))
        tk.Label(
            outer,
            textvariable=self.status,
            bg="#1f2937",
            fg="#f8fafc",
            anchor="w",
            justify="left",
            padx=12,
            pady=10,
            height=2,
            wraplength=770,
        ).pack(fill="x", pady=(0, 16))

        body = ttk.Frame(outer, style="App.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        tabs = ttk.Notebook(body)
        tabs.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        image_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        text_tab = ttk.Frame(tabs, style="App.TFrame", padding=12)
        tabs.add(image_tab, text="Image / GIF")
        tabs.add(text_tab, text="Text")
        self._build_image_tab(image_tab)
        self._build_text_tab(text_tab)

        right = ttk.Frame(body, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="SCREEN PREVIEW", style="App.TLabel").grid(
            row=0, column=0, pady=(0, 8)
        )
        self.preview = tk.Canvas(
            right,
            width=256,
            height=256,
            bg="#111827",
            borderwidth=0,
            highlightthickness=0,
        )
        self.preview.grid(row=1, column=0, sticky="nsew")
        self.preview_item = self.preview.create_image(0, 0)
        self.preview.bind("<Configure>", lambda _event: self._render_preview())
        ttk.Label(right, textvariable=self.frame_label, style="Muted.TLabel").grid(
            row=2, column=0, pady=6
        )
        self.play_button = ttk.Button(
            right,
            text="Play preview",
            command=self.toggle_preview,
            style="App.TButton",
            state="disabled",
        )
        self.play_button.grid(row=3, column=0, sticky="ew")
        ttk.Label(
            right,
            textvariable=self.preview_label,
            style="App.TLabel",
            wraplength=256,
            justify="center",
        ).grid(row=4, column=0, pady=(10, 6))
        self.detail_label = ttk.Label(
            right,
            textvariable=self.details,
            style="Muted.TLabel",
            wraplength=256,
            justify="center",
        )
        self.detail_label.grid(row=5, column=0)

        footer = ttk.Frame(outer, style="App.TFrame")
        # Reserve the action bar before allocating the remaining space to the editor.
        footer.pack(side="bottom", fill="x", before=body)
        ttk.Progressbar(footer, maximum=100, variable=self.progress).pack(
            fill="x", pady=(12, 8)
        )
        actions = ttk.Frame(footer, style="App.TFrame")
        actions.pack(fill="x")
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        self._button(actions, "Detect USB", self.detect).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        self.upload_button = self._button(actions, "Upload screen", self.upload)
        self.upload_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.upload_button.configure(state="disabled")
        self._button(actions, "Sync clock", self.sync_clock).grid(
            row=0, column=2, sticky="ew", padx=(8, 0)
        )
        ttk.Label(
            footer,
            text="AJAZZ AK820 Pro · Wired USB mode required · Preview edits stay local until you upload",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(12, 0))

    def _build_image_tab(self, parent):
        self._button(parent, "Choose image or GIF...", self.choose_file).pack(fill="x")
        ttk.Label(
            parent, textvariable=self.source_label, style="Muted.TLabel", wraplength=390
        ).pack(anchor="w", pady=8)
        options = ttk.Frame(parent, style="App.TFrame")
        options.pack(fill="x")
        options.columnconfigure(1, weight=1)
        self._option(options, 0, "Fit", self.fit, ["cover", "contain", "stretch"])
        self._option(
            options, 1, "Rotate clockwise", self.rotation, ["0", "90", "180", "270"]
        )
        self._option(options, 2, "Brightness (%)", self.brightness, limits=(0, 200))
        self._option(options, 3, "GIF frame limit", self.max_frames, limits=(1, 255))
        self._option(
            options,
            4,
            "GIF speed (×)",
            self.speed,
            ["0.25", "0.5", "1", "1.5", "2", "4"],
        )
        self.apply_button = self._button(parent, "Apply changes", self.apply_image)
        self.apply_button.pack(fill="x", pady=(10, 6))
        self.apply_button.configure(state="disabled")
        ttk.Label(
            parent,
            text="Cover crops edges; contain adds black bars.\nApply your settings to update the preview and upload.",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w")

    def _build_text_tab(self, parent):
        ttk.Label(
            parent, text="Your message (line breaks supported)", style="App.TLabel"
        ).pack(anchor="w", pady=(0, 8))
        self.message = tk.Text(
            parent,
            height=4,
            width=30,
            wrap="word",
            bg="#1f2937",
            fg="#f8fafc",
            insertbackground="#f8fafc",
            relief="flat",
            padx=8,
            pady=8,
            font=("DejaVu Sans", 11),
        )
        self.message.insert("1.0", "Hello Linux!")
        self.message.edit_modified(False)
        self.message.bind("<<Modified>>", self._text_modified)
        self.message.pack(fill="x", pady=(0, 8))
        self.controls.append((self.message, "normal"))
        options = ttk.Frame(parent, style="App.TFrame")
        options.pack(fill="x")
        options.columnconfigure(1, weight=1)
        self._option(
            options, 0, "Font size", self.font_size, [8, 12, 16, 20, 24, 28, 32]
        )
        self._option(
            options, 1, "Alignment", self.alignment, ["left", "center", "right"]
        )
        colors = ttk.Frame(parent, style="App.TFrame")
        colors.pack(fill="x", pady=8)
        fg_button = self._button(
            colors,
            "Text color",
            lambda: self.choose_color(self.text_color, "Text color"),
        )
        fg_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        bg_button = self._button(
            colors,
            "Background",
            lambda: self.choose_color(self.background_color, "Background color"),
        )
        bg_button.pack(side="left", fill="x", expand=True)
        self._button(parent, "Use this text", self.use_text).pack(fill="x", pady=(4, 8))
        ttk.Label(
            parent,
            text="Long messages wrap to fit. Text beyond the screen ends with an ellipsis.",
            style="Muted.TLabel",
            wraplength=390,
        ).pack(anchor="w")

    def _mark_dirty(self, kind):
        if self.content_kind == kind:
            self.dirty = True
            self._update_controls()
            action = "Apply changes" if kind == "image" else "Use this text"
            self.status.set(
                f"Settings changed. Click {action} to update your preview before uploading."
            )

    def _text_modified(self, _event):
        if self.message.edit_modified():
            self.message.edit_modified(False)
            self._mark_dirty("text")

    def _update_controls(self):
        for widget, state in self.controls:
            widget.configure(state="disabled" if self.busy else state)
        self.apply_button.configure(
            state="normal" if self.source_path and not self.busy else "disabled"
        )
        self.upload_button.configure(
            state=(
                "normal"
                if self.content and not self.dirty and not self.busy
                else "disabled"
            )
        )

    def _show_frame(self, image, index, total):
        self.current_preview = image
        self._render_preview()
        self.frame_label.set(f"Frame {index + 1} / {total}")

    def _render_preview(self):
        if self.current_preview is None:
            return
        width, height = self.preview.winfo_width(), self.preview.winfo_height()
        size = min(256, width, height)
        if size <= 1:
            return
        photo = ImageTk.PhotoImage(
            self.current_preview.resize((size, size), Image.Resampling.NEAREST),
            master=self.root,
        )
        self.preview.itemconfigure(self.preview_item, image=photo)
        self.preview.coords(self.preview_item, width / 2, height / 2)
        self.preview.image = photo

    def toggle_preview(self):
        if self.player.playing:
            self.player.pause()
        else:
            self.player.play()
        self.play_button.configure(
            text="Pause preview" if self.player.playing else "Play preview"
        )

    def _set_content(self, prepared, label, kind):
        self.content = prepared
        self.content_kind = kind
        self.dirty = False
        self.player.load(prepared.previews, prepared.delays)
        self.play_button.configure(
            state="normal" if prepared.delays else "disabled",
            text="Pause preview" if self.player.playing else "Play preview",
        )
        self.preview_label.set(label)
        detail = f"128 × 128 · {len(prepared.frames)} frame(s)"
        if prepared.delays:
            detail += f" · {sum(prepared.delays) / 1000:.2f} s per loop"
        if prepared.truncated:
            detail += "\nFrame limit reached; remaining frames were omitted."
        if prepared.timing_limited:
            detail += (
                "\nSome frame delays were limited to the keyboard's supported range."
            )
        self.details.set(detail)
        self.progress.set(0)
        self.status.set(f"Ready: {label}. Click Upload screen to send this preview.")
        self._update_controls()

    def choose_file(self):
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a screen image or GIF",
            filetypes=[
                ("Images & animations", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._load_image(path)

    def apply_image(self):
        if self.source_path:
            self._load_image(self.source_path)

    def _load_image(self, path):
        try:
            options = dict(
                fit=self.fit.get(),
                rotation=int(self.rotation.get()),
                brightness=float(self.brightness.get()) / 100,
                max_frames=int(self.max_frames.get()),
                speed=float(self.speed.get()),
            )
        except ValueError:
            messagebox.showerror(
                "Invalid setting",
                "Brightness and GIF frame limit must be numbers.",
                parent=self.root,
            )
            return

        def ready(prepared):
            self.source_path = path
            self.source_label.set(Path(path).name)
            self._set_content(prepared, Path(path).name, "image")

        self._run_task(
            lambda: prepare_image(path, **options),
            ready,
            "Preparing image and preview…",
        )

    def choose_color(self, variable, title):
        _rgb, color = colorchooser.askcolor(
            color=variable.get(), parent=self.root, title=title
        )
        if color:
            variable.set(color)

    def use_text(self):
        try:
            image = text_card(
                self.message.get("1.0", "end-1c"),
                fg=self.text_color.get(),
                bg=self.background_color.get(),
                font_size=int(self.font_size.get()),
                alignment=self.alignment.get(),
            )
            # Pending <<Modified>> events already belong to the text just rendered.
            self.message.edit_modified(False)
            self._set_content(
                PreparedImage([rgb565(image)], None, [image]), "Custom text", "text"
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("Text error", str(exc), parent=self.root)

    def _run_task(self, operation, on_success, status):
        if self.busy:
            return
        self.busy = True
        self.status.set(status)
        self.progress.set(0)
        self._update_controls()

        def worker():
            try:
                self.events.put(("success", (on_success, operation())))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self):
        # All Tk calls stay on the main thread, including progress and errors.
        try:
            while True:
                event, value = self.events.get_nowait()
                if event == "progress":
                    done, total = value
                    self.progress.set(100 * done / total)
                    self.status.set(f"Uploading {done}/{total} reports…")
                else:
                    self.busy = False
                    self._update_controls()
                    if event == "success":
                        callback, result = value
                        callback(result)
                    else:
                        self.status.set("Error: " + value)
                        messagebox.showerror("AK820 error", value, parent=self.root)
        except Empty:
            pass
        self.poll_timer = self.root.after(50, self._poll_events)

    def detect(self):
        def ready(pair):
            self.status.set(
                f"Connected: {pair.vendor:04x}:{pair.product:04x} · Control {pair.control} · Screen {pair.data}"
            )

        self._run_task(find_device, ready, "Detecting wired USB keyboard…")

    def upload(self):
        if self.content is None or self.dirty or self.busy:
            return
        prepared = self.content

        def transfer():
            with Keyboard(find_device()) as keyboard:
                keyboard.upload(
                    prepared.frames,
                    prepared.delays,
                    lambda done, total: self.events.put(("progress", (done, total))),
                )

        self._run_task(
            transfer,
            lambda _: self.status.set("Transfer finished. Check the keyboard screen!"),
            "Connecting to keyboard…",
        )

    def sync_clock(self):
        def sync():
            with Keyboard(find_device()) as keyboard:
                keyboard.sync_clock()

        self._run_task(
            sync,
            lambda _: self.status.set("Clock synchronized with your Linux computer."),
            "Synchronizing clock…",
        )

    def close(self):
        if self.busy:
            self.status.set(
                "Please wait for the current operation to finish before closing."
            )
            return
        self.player.pause()
        self.root.after_cancel(self.poll_timer)
        self.root.destroy()


def run_gui():
    root = tk.Tk()
    StudioApp(root)
    root.mainloop()
