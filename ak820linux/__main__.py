"""AK820 Linux Studio - native GUI and terminal commands."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
import threading

from .protocol import Keyboard, find_device, scan_interfaces


def do_probe():
    entries = scan_interfaces()
    if not entries:
        print('No matching AJAZZ USB device found. Set wired mode and connect with a USB data cable.')
        return 1
    for entry in entries:
        print(f"{entry['path']}  VID:PID={entry['vendor']:04x}:{entry['product']:04x}  usage={entry['usage']:#06x}" if entry['usage'] is not None else f"{entry['path']}  usage=unknown")
    try:
        pair = find_device()
        print(f'Compatible screen interfaces found: control {pair.control} / data {pair.data}')
        return 0
    except RuntimeError as exc:
        print(f'Not compatible with this classic protocol: {exc}')
        return 2


def do_upload(path, fit='cover', max_frames=60):
    from .images import from_path
    frames, delays, _preview = from_path(path, fit, max_frames)
    print(f'Prepared {len(frames)} frame(s) from {path}')
    pair = find_device()
    with Keyboard(pair) as dev:
        dev.upload(frames, delays, lambda pos, total: print(f'\rSending {pos}/{total} reports', end='', flush=True))
    print('\nTransfer completed; check the keyboard screen.')


def gui():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        from PIL import ImageTk
    except ImportError as exc:
        raise RuntimeError('GUI dependencies missing. Run ./setup.sh (python3-tk, Pillow).') from exc
    from .images import from_path, rgb565, text_card

    root = tk.Tk()
    root.title('AK820 Linux Studio')
    root.geometry('720x560')
    root.minsize(640, 520)
    root.configure(bg='#111827')
    fg, muted, accent, panel = '#f8fafc', '#9ca3af', '#22d3ee', '#1f2937'
    font = ('DejaVu Sans', 10)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('App.TFrame', background='#111827')
    style.configure('Panel.TFrame', background=panel)
    style.configure('App.TLabel', background='#111827', foreground=fg, font=font)
    style.configure('Muted.TLabel', background='#111827', foreground=muted, font=font)
    style.configure('Panel.TLabel', background=panel, foreground=fg, font=font)
    style.configure('App.TButton', background='#374151', foreground=fg, padding=(15, 9), font=font)
    style.map('App.TButton', background=[('active', '#4b5563'), ('disabled', '#374151')])
    style.configure('TProgressbar', troughcolor='#374151', background=accent)

    outer = ttk.Frame(root, style='App.TFrame', padding=24)
    outer.pack(fill='both', expand=True)
    ttk.Label(outer, text='AK820 LINUX STUDIO', foreground=accent,
              background='#111827', font=('DejaVu Sans', 18, 'bold')).pack(anchor='w')
    ttk.Label(outer, text='AJAZZ AK820 Pro · USB · 128 × 128 TFT · no Windows driver required',
              style='Muted.TLabel').pack(anchor='w', pady=(4, 18))

    status_var = tk.StringVar(value='Connect via USB data cable and switch the keyboard to wired mode.')
    status = tk.Label(outer, textvariable=status_var, bg=panel, fg=fg,
                      font=font, anchor='w', padx=13, pady=12, wraplength=610)
    status.pack(fill='x', pady=(0, 15))

    body = ttk.Frame(outer, style='App.TFrame')
    body.pack(fill='both', expand=True)
    left = ttk.Frame(body, style='App.TFrame')
    left.pack(side='left', fill='both', expand=True)
    right = ttk.Frame(body, style='App.TFrame')
    right.pack(side='right', anchor='n', padx=(26, 0))

    ttk.Label(left, text='1. Prepare screen content', style='App.TLabel',
              font=('DejaVu Sans', 11, 'bold')).pack(anchor='w', pady=(0, 8))
    fit_var = tk.StringVar(value='cover')
    fit_row = ttk.Frame(left, style='App.TFrame')
    fit_row.pack(fill='x')
    ttk.Label(fit_row, text='Fit:', style='App.TLabel').pack(side='left')
    fit_combo = ttk.Combobox(fit_row, textvariable=fit_var,
                             values=['cover', 'contain', 'stretch'], width=12, state='readonly')
    fit_combo.pack(side='left', padx=10)
    ttk.Label(left, text='GIFs use up to 60 frames (default). Images are cropped to 128 × 128.',
              style='Muted.TLabel', wraplength=325).pack(anchor='w', pady=9)

    preview = tk.Label(right, bg='#000000', width=256, height=256, relief='flat')
    preview.pack()
    ttk.Label(right, text='Screen preview (2×)', style='Muted.TLabel').pack(pady=8)

    selected = {'frames': None, 'delays': None, 'preview': None, 'label': None}
    buttons = []
    busy = {'value': False}

    def show_preview(image):
        img = image.resize((256, 256))
        photo = ImageTk.PhotoImage(img)
        preview.configure(image=photo, width=256, height=256)
        preview.image = photo

    show_preview(text_card('AK820 Linux'))

    def set_content(frames, delays, image, label):
        selected.update(frames=frames, delays=delays, preview=image, label=label)
        show_preview(image)
        status_var.set(f'Ready: {label}. Click Upload to send it to the keyboard.')

    def choose_file():
        path = filedialog.askopenfilename(title='Choose a screen image or GIF', filetypes=[
            ('Images & animations', '*.png *.jpg *.jpeg *.gif *.bmp *.webp'), ('All files', '*.*')])
        if not path:
            return
        try:
            frames, delays, image = from_path(path, fit_var.get())
            set_content(frames, delays, image, f'{Path(path).name} ({len(frames)} frame(s))')
        except Exception as exc:
            messagebox.showerror('Image error', str(exc))

    ttk.Button(left, text='Choose PNG / JPG / GIF…', command=choose_file,
               style='App.TButton').pack(fill='x', pady=(5, 14))

    ttk.Label(left, text='Or put your own text on the screen', style='App.TLabel').pack(anchor='w')
    message = tk.StringVar(value='Hello Linux!')
    edit = tk.Entry(left, textvariable=message, bg=panel, fg=fg, insertbackground=fg,
                    relief='flat', font=font)
    edit.pack(fill='x', ipady=9, pady=(6, 7))

    def preview_text():
        image = text_card(message.get())
        set_content([rgb565(image)], None, image, 'Custom text')

    ttk.Button(left, text='Use this text', command=preview_text,
               style='App.TButton').pack(fill='x', pady=(0, 20))

    ttk.Label(left, text='2. Send to the keyboard', style='App.TLabel',
              font=('DejaVu Sans', 11, 'bold')).pack(anchor='w', pady=(0, 8))

    progress_var = tk.DoubleVar(value=0)
    ttk.Progressbar(left, maximum=100, variable=progress_var).pack(fill='x', pady=(0, 10))

    def background(fn, success):
        if busy['value']:
            return
        busy['value'] = True
        for button in buttons:
            button.configure(state='disabled')
        progress_var.set(0)

        def worker():
            try:
                result = fn()
                root.after(0, lambda: status_var.set(result or success))
            except Exception as exc:
                msg = str(exc)
                root.after(0, lambda: (status_var.set('Error: ' + msg), messagebox.showerror('AJAZZ error', msg)))
            finally:
                def end():
                    busy['value'] = False
                    for button in buttons:
                        button.configure(state='normal')
                root.after(0, end)

        threading.Thread(target=worker, daemon=True).start()

    def detect():
        def task():
            pair = find_device()
            return f'Found {pair.vendor:04x}:{pair.product:04x}  Control: {pair.control}, Data: {pair.data}'
        background(task, 'USB interfaces detected. You can now send content.')

    def upload():
        if selected['frames'] is None:
            messagebox.showinfo('Choose content', 'Choose an image/GIF or click Use this text first.')
            return
        frames = selected['frames']
        delays = selected['delays']
        def task():
            pair = find_device()
            with Keyboard(pair) as dev:
                def update(done, total):
                    root.after(0, lambda d=done, t=total: (
                        progress_var.set(100 * d / t), status_var.set(f'Uploading {d}/{t} reports…')))
                dev.upload(frames, delays, update)
        background(task, 'Transfer finished. Check the keyboard screen!')

    def sync_time():
        def task():
            pair = find_device()
            with Keyboard(pair) as dev:
                dev.sync_clock(datetime.now())
        background(task, 'Clock synchronized with your Linux computer.')

    row = ttk.Frame(left, style='App.TFrame')
    row.pack(fill='x')
    for title, action in [('Detect USB', detect), ('Upload screen', upload), ('Sync clock', sync_time)]:
        btn = ttk.Button(row, text=title, command=action, style='App.TButton')
        btn.pack(side='left', padx=(0, 6))
        buttons.append(btn)

    ttk.Label(outer, text='Stock AK820 Pro protocol only · For wrong PID or firmware, no commands are sent. '
              'Do not run uploads during a firmware update.',
              style='Muted.TLabel', wraplength=660).pack(anchor='w', pady=(20, 0))
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='AJAZZ AK820 Pro Linux display control')
    sub = parser.add_subparsers(dest='action')
    sub.add_parser('probe', help='Read-only USB device detection')
    sub.add_parser('clock', help='Send local system time to keyboard')
    p = sub.add_parser('upload', help='Upload PNG, JPG, BMP, WebP or animated GIF')
    p.add_argument('path')
    p.add_argument('--fit', choices=['cover', 'contain', 'stretch'], default='cover')
    p.add_argument('--max-frames', type=int, default=60)
    sub.add_parser('gui', help='Open graphical application')
    args = parser.parse_args()
    try:
        if args.action == 'probe':
            return do_probe()
        if args.action == 'clock':
            pair = find_device()
            with Keyboard(pair) as dev:
                dev.sync_clock()
            print('Clock command sent.')
        elif args.action == 'upload':
            do_upload(args.path, args.fit, args.max_frames)
        else:
            gui()
        return 0
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
