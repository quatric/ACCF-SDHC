#!/usr/bin/env python3
"""Small GUI front end for the SDHC patch: pick a disc image, click Patch.

Unlike dist.py (which patches pre-dumped reference DOLs for every supported
revision at once, for building the release) this works on one disc the user
actually has: extract it, read its own id/version out of sys/boot.bin, apply
dist.py's site map for that exact revision to its own main.dol, and rebuild
the WBFS. No dumps/ layout or paths.py setup required.
"""
import os
import queue
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dist
from dol import Dol
from patch_tmd_ios import locate as tmd_ios_offset


def find_file(root, name):
    for r, _, files in os.walk(root):
        if name in files:
            return os.path.join(r, name)
    return None


def read_disc_id(fst):
    boot = find_file(fst, 'boot.bin')
    if not boot:
        return None
    with open(boot, 'rb') as f:
        header = f.read(8)
    return header[0:6].decode('ascii', 'replace'), header[7]


def key_for(disc_id, disc_ver):
    for key, (label, _src, delta, tid, tver) in dist.TARGETS.items():
        if tid == disc_id and tver == disc_ver:
            return key, label, delta
    return None, None, None


def patch_tmd(tmd_path, ios, log):
    data = bytearray(open(tmd_path, 'rb').read())
    off = tmd_ios_offset(data)
    old = struct.unpack_from('>Q', data, off)[0]
    struct.pack_into('>Q', data, off, (1 << 32) | ios)
    open(tmd_path, 'wb').write(data)
    log('  tmd: IOS %d -> IOS %d (signature invalidated)' % (old & 0xFF, ios))


def run_patch(image_path, out_dir, ios58, log, done):
    try:
        if shutil.which('wit') is None:
            raise RuntimeError('wit (Wiimms ISO Tool) is not on PATH')

        with tempfile.TemporaryDirectory(prefix='sdhc_patch_') as fst:
            log('extracting %s...' % os.path.basename(image_path))
            r = subprocess.run(['wit', 'extract', image_path, '--dest', fst,
                                 '--psel', 'data', '-q'],
                                capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError('extract failed:\n' + (r.stderr or r.stdout))

            got = read_disc_id(fst)
            if not got:
                raise RuntimeError('could not read sys/boot.bin from the extracted disc')
            disc_id, disc_ver = got
            key, label, delta = key_for(disc_id, disc_ver)
            if not key:
                raise RuntimeError(
                    '%s v%d is not a supported target.\n\n'
                    'Supported: %s' % (disc_id, disc_ver,
                                        ', '.join(sorted(t[3] + ' v' + str(t[4])
                                                          for t in dist.TARGETS.values()))))
            log('disc: %s v%d -> %s' % (disc_id, disc_ver, label))

            dol_path = find_file(fst, 'main.dol')
            if not dol_path or os.path.basename(os.path.dirname(dol_path)) != 'sys':
                raise RuntimeError('could not find sys/main.dol in the extracted disc')

            d = Dol(dol_path)
            bad = dist.verify_target(d, delta)
            if bad:
                raise RuntimeError(
                    'disc does not match the expected site map: %s\n'
                    'This usually means an unexpected build of the game -- do not patch it.'
                    % ', '.join(bad))

            patches, _cave_end = dist.rebased_patches(delta)
            data = bytearray(d.data)
            for va, blob in patches:
                fo = d.v2f(va)
                data[fo:fo + len(blob)] = blob
            open(dol_path, 'wb').write(bytes(data))
            log('  patched main.dol (%d writes)' % len(patches))

            if ios58:
                tmd_path = find_file(fst, 'tmd.bin')
                if tmd_path:
                    patch_tmd(tmd_path, 58, log)
                else:
                    log('  no tmd.bin found, skipping IOS 58 patch')

            os.makedirs(out_dir, exist_ok=True)
            out = os.path.join(out_dir, '%s_SDHC.wbfs' % key)
            log('rebuilding wbfs...')
            r = subprocess.run(['wit', 'copy', fst, '--dest', out, '--wbfs', '-q'],
                                capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError('rebuild failed:\n' + (r.stderr or r.stdout))
            log('done: %s' % out)
            done(True, out)
    except Exception as e:
        log('ERROR: %s' % e)
        done(False, str(e))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ACCF SDHC Patcher')
        self.geometry('640x420')
        self.resizable(True, True)

        self.image_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.ios58_var = tk.BooleanVar(value=False)
        self.msgq = queue.Queue()

        pad = {'padx': 8, 'pady': 6}

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        ttk.Label(row, text='Disc image (.wbfs / .iso):').pack(anchor='w')
        r2 = ttk.Frame(row); r2.pack(fill='x')
        ttk.Entry(r2, textvariable=self.image_var).pack(side='left', fill='x', expand=True)
        ttk.Button(r2, text='Browse...', command=self.pick_image).pack(side='left', padx=(6, 0))

        row = ttk.Frame(self); row.pack(fill='x', **pad)
        ttk.Label(row, text='Output folder:').pack(anchor='w')
        r2 = ttk.Frame(row); r2.pack(fill='x')
        ttk.Entry(r2, textvariable=self.out_var).pack(side='left', fill='x', expand=True)
        ttk.Button(r2, text='Browse...', command=self.pick_out).pack(side='left', padx=(6, 0))

        ttk.Checkbutton(self, text='Also require IOS 58 (Dolphin / fakesigned only)',
                         variable=self.ios58_var).pack(anchor='w', **pad)

        self.patch_btn = ttk.Button(self, text='Patch', command=self.start_patch)
        self.patch_btn.pack(**pad)

        self.log = tk.Text(self, height=14, state='disabled', wrap='word')
        self.log.pack(fill='both', expand=True, **pad)

        self.after(100, self.poll_queue)

    def pick_image(self):
        p = filedialog.askopenfilename(
            title='Select disc image',
            filetypes=[('Wii disc image', '*.wbfs *.iso'), ('All files', '*')])
        if p:
            self.image_var.set(p)
            if not self.out_var.get():
                self.out_var.set(os.path.dirname(p))

    def pick_out(self):
        p = filedialog.askdirectory(title='Select output folder')
        if p:
            self.out_var.set(p)

    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == 'log':
                    self.append_log(payload)
                elif kind == 'done':
                    ok, msg = payload
                    self.patch_btn.configure(state='normal')
                    if ok:
                        messagebox.showinfo('Done', 'Built:\n%s' % msg)
                    else:
                        messagebox.showerror('Patch failed', msg)
        except queue.Empty:
            pass
        self.after(100, self.poll_queue)

    def start_patch(self):
        image_path = self.image_var.get().strip()
        out_dir = self.out_var.get().strip()
        if not image_path or not os.path.isfile(image_path):
            messagebox.showerror('Missing image', 'Pick a .wbfs or .iso disc image first.')
            return
        if not out_dir:
            messagebox.showerror('Missing output folder', 'Pick an output folder first.')
            return

        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')
        self.patch_btn.configure(state='disabled')

        def log(text):
            self.msgq.put(('log', text))

        def done(ok, msg):
            self.msgq.put(('done', (ok, msg)))

        threading.Thread(
            target=run_patch,
            args=(image_path, out_dir, self.ios58_var.get(), log, done),
            daemon=True,
        ).start()


if __name__ == '__main__':
    App().mainloop()
