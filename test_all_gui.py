import os
import time
import queue
import signal
import threading
import multiprocessing as mp
import tkinter as tk
from tkinter import ttk

TIMEOUT = 500
N_WORKERS = max(1, os.cpu_count() - 2)
WAREHOUSE_FOLDER = './warehouses'


# ─────────────────────────────────────────────────────────────
def solve_one(path):
    """Runs inside a worker process."""
    import time, os, search
    from sokoban import Warehouse
    from mySokobanSolver import SokobanPuzzle

    filename = os.path.basename(path)
    wh = Warehouse()

    try:
        wh.load_warehouse(path)
    except Exception:
        return filename, 'INVALID', None, None, 0, 0.0

    t0 = time.time()
    problem = SokobanPuzzle(wh)
    node = search.astar_graph_search(problem, problem.h)
    elapsed = time.time() - t0

    if node is None:
        return filename, 'Impossible', None, None, problem.h_calls, elapsed

    return filename, 'Solved', node.solution(), node.path_cost, problem.h_calls, elapsed


def solve_one_process(path, out_queue):
    """Wrapper so we can kill the process safely."""
    try:
        out_queue.put(solve_one(path))
    except Exception as e:
        out_queue.put((os.path.basename(path), 'ERROR', None, str(e), 0, 0.0))


# ─────────────────────────────────────────────────────────────
class TestAllGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sokoban Solver — Batch Test")
        self.root.geometry("900x600")

        self.result_queue = queue.Queue()
        self.running = False
        self.start_time = None

        self.done_count = 0
        self.solved_count = 0
        self.impossible_count = 0
        self.timed_out_count = 0

        self._build_ui()
        self._load_puzzle_list()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─────────────────────────────────────────────────────────
    def _build_ui(self):
        toolbar = tk.Frame(self.root)
        toolbar.pack(fill=tk.X)

        self.run_btn = tk.Button(toolbar, text="▶ Run All",
                                 command=self.start_solving,
                                 bg="#28a745", fg="white")
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(toolbar, text="■ Stop",
                                  command=self.stop_solving,
                                  state=tk.DISABLED,
                                  bg="#dc3545", fg="white")
        self.stop_btn.pack(side=tk.LEFT)

        tk.Label(toolbar, text=" Workers:").pack(side=tk.LEFT, padx=8)
        self.workers_var = tk.IntVar(value=N_WORKERS)
        tk.Spinbox(toolbar, from_=1, to=os.cpu_count(),
                   textvariable=self.workers_var,
                   width=4).pack(side=tk.LEFT)

        tk.Label(toolbar, text=" Timeout (s):").pack(side=tk.LEFT, padx=8)
        self.timeout_var = tk.IntVar(value=TIMEOUT)
        self.timeout_spin = tk.Spinbox(toolbar, from_=5, to=3600,
                                       textvariable=self.timeout_var,
                                       width=6)
        self.timeout_spin.pack(side=tk.LEFT)

        self.no_timeout_var = tk.BooleanVar()
        tk.Checkbutton(toolbar, text="No timeout",
                       variable=self.no_timeout_var,
                       command=self._toggle_timeout).pack(side=tk.LEFT, padx=6)

        stats = tk.Frame(self.root)
        stats.pack(fill=tk.X)

        def stat(label):
            v = tk.StringVar(value="0")
            tk.Label(stats, text=label).pack(side=tk.LEFT)
            tk.Label(stats, textvariable=v,
                     font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=4)
            return v

        self.stat_done = stat("Done:")
        self.stat_solved = stat("Solved:")
        self.stat_imposs = stat("Impossible:")
        self.stat_timeout = stat("Timed out:")
        self.stat_elapsed = stat("Time:")

        self.progress = tk.DoubleVar()
        ttk.Progressbar(stats, variable=self.progress,
                        maximum=100, length=200).pack(side=tk.RIGHT, padx=10)

        cols = ('file', 'status', 'cost', 'steps', 'h', 'time')
        self.tree = ttk.Treeview(self.root, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, anchor='center')
        self.tree.column('file', width=240, anchor='w')
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.tag_configure('pending', foreground='#888')
        self.tree.tag_configure('running', background='#fff3cd')
        self.tree.tag_configure('solved', background='#d4edda')
        self.tree.tag_configure('impossible', background='#cce5ff')
        self.tree.tag_configure('timed_out', background='#f8d7da')
        self.tree.tag_configure('invalid', background='#e2e3e5')
        self.tree.tag_configure('error', background='#f8d7da')

    # ─────────────────────────────────────────────────────────
    def _load_puzzle_list(self):
        self.files = sorted(f for f in os.listdir(WAREHOUSE_FOLDER)
                            if f.endswith('.txt'))
        self.iid = {}
        for f in self.files:
            self.iid[f] = self.tree.insert(
                '', 'end',
                values=(f, 'Pending', '', '', '', ''),
                tags=('pending',)
            )

    def _toggle_timeout(self):
        self.timeout_spin.config(
            state=tk.DISABLED if self.no_timeout_var.get() else tk.NORMAL
        )

    # ─────────────────────────────────────────────────────────
    def start_solving(self):
        if self.running:
            return

        self.running = True
        self.start_time = time.time()
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        self.done_count = self.solved_count = \
            self.impossible_count = self.timed_out_count = 0

        t = threading.Thread(target=self._solver_thread, daemon=True)
        t.start()
        self.root.after(150, self._poll)

    # ─────────────────────────────────────────────────────────
    def _solver_thread(self):
        timeout = None if self.no_timeout_var.get() else self.timeout_var.get()
        max_workers = self.workers_var.get()

        jobs = [(f, os.path.join(WAREHOUSE_FOLDER, f)) for f in self.files]
        self.active_workers = []  # shared reference
        active =self.active_workers

        while (jobs or active) and self.running:

            # Launch new workers
            while jobs and len(active) < max_workers:
                fname, path = jobs.pop(0)
                q = mp.Queue()
                p = mp.Process(target=solve_one_process, args=(path, q))
                p.start()
                active.append((fname, p, q, time.time()))
                self.result_queue.put(('RUNNING', fname))

            # Check running workers
            for item in active[:]:
                fname, proc, q, start = item

                if not proc.is_alive():
                    proc.join()
                    if not q.empty():
                        self.result_queue.put(('RESULT', *q.get()))
                    else:
                        self.result_queue.put(('RESULT',
                                               fname, 'ERROR', None, '', 0, 0.0))
                    active.remove(item)

                elif timeout and time.time() - start >= timeout:
                    proc.terminate()
                    proc.join()
                    self.result_queue.put(('RESULT',
                                           fname, 'TIMED OUT',
                                           None, None, 0, timeout))
                    active.remove(item)

            time.sleep(0.1)

        self.result_queue.put(('DONE',))

    # ─────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                msg = self.result_queue.get_nowait()

                if msg[0] == 'DONE':
                    self.running = False
                    self.run_btn.config(state=tk.NORMAL)
                    self.stop_btn.config(state=tk.DISABLED)
                    return

                elif msg[0] == 'RUNNING':
                    f = msg[1]
                    self.tree.item(self.iid[f],
                                   values=(f, 'Running', '', '', '', ''),
                                   tags=('running',))

                elif msg[0] == 'RESULT':
                    _, f, status, sol, cost, h, t = msg
                    self.done_count += 1

                    if status == 'Solved':
                        self.solved_count += 1
                        vals = (f, 'Solved', cost, len(sol), h, f"{t:.2f}")
                        tag = 'solved'
                    elif status == 'Impossible':
                        self.impossible_count += 1
                        vals = (f, 'Impossible', '', '', h, f"{t:.2f}")
                        tag = 'impossible'
                    elif status == 'TIMED OUT':
                        self.timed_out_count += 1
                        vals = (f, 'Timed out', '', '', '', f">{t:.0f}")
                        tag = 'timed_out'
                    elif status == 'INVALID':
                        self.done_count -= 1
                        vals = (f, 'Invalid', '', '', '', '')
                        tag = 'invalid'
                    else:
                        vals = (f, 'Error', '', '', '', '')
                        tag = 'error'

                    self.tree.item(self.iid[f], values=vals, tags=(tag,))

        except queue.Empty:
            pass

        total = len(self.files)
        self.stat_done.set(f"{self.done_count}/{total}")
        self.stat_solved.set(str(self.solved_count))
        self.stat_imposs.set(str(self.impossible_count))
        self.stat_timeout.set(str(self.timed_out_count))
        self.progress.set(self.done_count / total * 100 if total else 0)
        self.stat_elapsed.set(f"{time.time() - self.start_time:.1f}s")

        if self.running:
            self.root.after(150, self._poll)

    # ─────────────────────────────────────────────────────────
    def stop_solving(self):
        self.running = False

        # HARD KILL all active workers
        if hasattr(self, 'active_workers'):
            for fname, proc, q, start in self.active_workers:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.2)

            self.active_workers.clear()

        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def _on_close(self):
        self.running = False

        if hasattr(self, 'active_workers'):
            for fname, proc, q, start in self.active_workers:
                if proc.is_alive():
                    proc.terminate()
                    proc.join(timeout=0.2)

            self.active_workers.clear()

        self.root.destroy()


# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    mp.freeze_support()
    mp.set_start_method('spawn', force=True)

    root = tk.Tk()
    app = TestAllGUI(root)

    signal.signal(signal.SIGINT,
                  lambda *_: root.after(0, app._on_close))

    root.mainloop()