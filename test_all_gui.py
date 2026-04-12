"""
Sokoban Warehouse Test GUI
Each warehouse runs in its own process so the UI stays responsive.
"""
import tkinter as tk
from tkinter import ttk
import multiprocessing as mp
import threading
import time
import os

BG       = "#0f1117"
PANEL    = "#1a1d27"
ACCENT   = "#00d4aa"
DIM      = "#3a3f55"
TEXT     = "#e8eaf0"
TEXT_DIM = "#6b7080"

WAREHOUSE_FOLDER = './warehouses'
DEFAULT_TIMEOUT  = 500
DEFAULT_WORKERS  = 2


# ── worker (runs in child process) ────────────────────────────────────────────

def solve_warehouse(filename, timeout, result_queue):
    import search, time, os, threading
    from sokoban import Warehouse
    from mySokobanSolver import SokobanPuzzle

    path = os.path.join(WAREHOUSE_FOLDER, filename)
    wh   = Warehouse()
    try:
        wh.load_warehouse(path)
    except Exception:
        result_queue.put({"file": filename, "status": "invalid"})
        return

    result      = [None]
    problem_ref = [None]

    def run():
        p = SokobanPuzzle(wh)
        problem_ref[0] = p
        node = search.astar_graph_search(p, p.h)
        result[0] = ('Impossible', None) if node is None else (node.solution(), node.path_cost)

    t0     = time.time()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    last_update = 0
    while thread.is_alive():
        thread.join(timeout=0.5)
        elapsed = time.time() - t0
        if elapsed - last_update >= 2:
            h = getattr(problem_ref[0], 'h_calls', 0)
            result_queue.put({"file": filename, "status": "running",
                               "elapsed": elapsed, "h_calls": h})
            last_update = elapsed
        if elapsed >= timeout:
            break

    elapsed = time.time() - t0
    h       = getattr(problem_ref[0], 'h_calls', 0)

    if thread.is_alive():
        result_queue.put({"file": filename, "status": "timeout",
                           "elapsed": elapsed, "h_calls": h})
    elif result[0] is None or result[0][0] == 'Impossible':
        result_queue.put({"file": filename, "status": "impossible",
                           "elapsed": elapsed, "h_calls": h})
    else:
        sol, cost = result[0]
        result_queue.put({"file": filename, "status": "solved", "cost": cost,
                           "steps": len(sol), "elapsed": elapsed, "h_calls": h})


# ── GUI ───────────────────────────────────────────────────────────────────────

class SokobanGUI:
    def __init__(self, root):
        self.root    = root
        self.root.title("Sokoban Solver — Warehouse Test Suite")
        self.root.configure(bg=BG)
        self.root.geometry("1100x680")
        self.rows    = {}
        self.running = False
        self.passed  = self.failed = self.timeouts = 0
        self.manager = None
        self.q       = None
        self._build_ui()
        self._load_warehouses()
        self._poll()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(20, 0))
        tk.Label(hdr, text="SOKOBAN", font=("Courier", 22, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(hdr, text=" Warehouse Test Suite", font=("Courier", 14),
                 fg=TEXT_DIM, bg=BG).pack(side="left", pady=4)

        ctrl = tk.Frame(self.root, bg=BG)
        ctrl.pack(fill="x", padx=24, pady=12)

        self.btn_run = tk.Button(ctrl, text="▶  RUN ALL", font=("Courier", 11, "bold"),
                                  bg=ACCENT, fg=BG, relief="flat", padx=18, pady=8,
                                  cursor="hand2", command=self._start)
        self.btn_run.pack(side="left", padx=(0, 10))

        self.btn_stop = tk.Button(ctrl, text="■  STOP", font=("Courier", 11, "bold"),
                                   bg=DIM, fg=TEXT, relief="flat", padx=18, pady=8,
                                   cursor="hand2", state="disabled", command=self._stop)
        self.btn_stop.pack(side="left", padx=(0, 20))

        tk.Label(ctrl, text="Timeout:", font=("Courier", 10),
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        self.timeout_var = tk.IntVar(value=DEFAULT_TIMEOUT)
        tk.Scale(ctrl, from_=5, to=3600, orient="horizontal",
                 variable=self.timeout_var, bg=BG, fg=TEXT, troughcolor=DIM,
                 highlightthickness=0, font=("Courier", 9), length=160).pack(side="left", padx=6)

        tk.Label(ctrl, text="s  Workers:", font=("Courier", 10),
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        self.workers_var = tk.IntVar(value=DEFAULT_WORKERS)
        tk.Scale(ctrl, from_=1, to=mp.cpu_count(), orient="horizontal",
                 variable=self.workers_var, bg=BG, fg=TEXT, troughcolor=DIM,
                 highlightthickness=0, font=("Courier", 9), length=100).pack(side="left", padx=6)

        self.summary = tk.Label(self.root,
                                 text="Ready — press RUN ALL to start",
                                 font=("Courier", 10), fg=TEXT_DIM, bg=PANEL,
                                 anchor="w", padx=16, pady=6)
        self.summary.pack(fill="x", padx=24, pady=(0, 8))

        tf = tk.Frame(self.root, bg=BG)
        tf.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        cols = ("warehouse", "status", "cost", "steps", "h_calls", "time")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="none")
        for col, label, width, anchor in [
            ("warehouse", "Warehouse", 280, "w"),
            ("status",    "Status",    120, "center"),
            ("cost",      "Cost",       90, "center"),
            ("steps",     "Steps",      80, "center"),
            ("h_calls",   "h() calls", 120, "center"),
            ("time",      "Time",       90, "center"),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT,
                         fieldbackground=PANEL, rowheight=28, font=("Courier", 10))
        style.configure("Treeview.Heading", background=DIM, foreground=ACCENT,
                         font=("Courier", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", DIM)])

        for tag, color in [("pass", "#00d4aa"), ("fail", "#ff4f6d"),
                            ("timeout", "#f5a623"), ("running", "#7eb8ff"),
                            ("idle", TEXT_DIM), ("invalid", DIM)]:
            self.tree.tag_configure(tag, foreground=color)

        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _load_warehouses(self):
        if not os.path.isdir(WAREHOUSE_FOLDER):
            self.summary.config(text=f"Folder not found: {WAREHOUSE_FOLDER}")
            return
        files = sorted(f for f in os.listdir(WAREHOUSE_FOLDER) if f.endswith('.txt'))
        for fn in files:
            iid = self.tree.insert("", "end",
                                    values=(fn, "waiting", "—", "—", "—", "—"),
                                    tags=("idle",))
            self.rows[fn] = iid
        self.summary.config(text=f"{len(files)} warehouses loaded — press RUN ALL")

    # poll every 300ms — only place UI is updated
    def _poll(self):
        if self.q is not None:
            try:
                while True:
                    msg = self.q.get_nowait()
                    self._handle(msg)
            except Exception:
                pass
        self.root.after(300, self._poll)

    def _handle(self, msg):
        fn  = msg.get("file")
        iid = self.rows.get(fn)
        st  = msg["status"]

        if st == "running" and iid:
            self.tree.item(iid, tags=("running",),
                values=(fn, f"running {msg['elapsed']:.0f}s",
                        "—", "—", f"{msg['h_calls']:,}", f"{msg['elapsed']:.1f}s"))

        elif st == "solved" and iid:
            self.tree.item(iid, tags=("pass",),
                values=(fn, "Solved ✓", f"{msg['cost']:,}",
                        str(msg['steps']), f"{msg['h_calls']:,}", f"{msg['elapsed']:.2f}s"))
            self.passed += 1
            self._update_summary()

        elif st == "impossible" and iid:
            self.tree.item(iid, tags=("fail",),
                values=(fn, "Impossible", "—", "—",
                        f"{msg['h_calls']:,}", f"{msg['elapsed']:.2f}s"))
            self.failed += 1
            self._update_summary()

        elif st == "timeout" and iid:
            self.tree.item(iid, tags=("timeout",),
                values=(fn, "TIMEOUT ⏱", "—", "—",
                        f"{msg['h_calls']:,}", f"{msg['elapsed']:.1f}s"))
            self.timeouts += 1
            self._update_summary()

        elif st == "invalid" and iid:
            self.tree.item(iid, tags=("invalid",),
                values=(fn, "invalid file", "—", "—", "—", "—"))

        elif st == "all_done":
            self.running = False
            self.btn_run.config(state="normal", bg=ACCENT, fg=BG)
            self.btn_stop.config(state="disabled", bg=DIM, fg=TEXT)
            if self.manager:
                self.manager.shutdown()
                self.manager = None

    def _start(self):
        if self.running:
            return
        self.running = True
        self.passed  = self.failed = self.timeouts = 0
        self.btn_run.config(state="disabled", bg=DIM)
        self.btn_stop.config(state="normal", bg="#ff4f6d", fg="white")

        for fn, iid in self.rows.items():
            self.tree.item(iid, values=(fn, "waiting", "—", "—", "—", "—"),
                           tags=("idle",))
        self._update_summary()

        # create a Manager queue — safe to pass to child processes on Windows
        self.manager = mp.Manager()
        self.q       = self.manager.Queue()

        timeout = self.timeout_var.get()
        workers = self.workers_var.get()
        files   = list(self.rows.keys())

        threading.Thread(target=self._dispatch,
                          args=(files, timeout, workers), daemon=True).start()

    def _dispatch(self, files, timeout, workers):
        self.pool = mp.Pool(processes=workers)
        for fn in files:
            if not self.running:
                break
            self.pool.apply_async(solve_warehouse, args=(fn, timeout, self.q))
        self.pool.close()
        self.pool.join()
        if self.q:
            self.q.put({"file": None, "status": "all_done"})

    def _stop(self):
        self.running = False
        try:
            self.pool.terminate()
        except Exception:
            pass
        self.btn_run.config(state="normal", bg=ACCENT, fg=BG)
        self.btn_stop.config(state="disabled", bg=DIM, fg=TEXT)
        self.summary.config(text="Stopped by user.")

    def _update_summary(self):
        total = len(self.rows)
        done  = self.passed + self.failed + self.timeouts
        self.summary.config(
            text=f"  {done}/{total} done   |   ✓ {self.passed} solved"
                 f"   |   ✗ {self.failed} impossible   |   ⏱ {self.timeouts} timeout")


if __name__ == "__main__":
    mp.freeze_support()  # required on Windows
    root = tk.Tk()
    SokobanGUI(root)
    root.mainloop()