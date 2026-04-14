import time
import os
import threading
import search
from sokoban import Warehouse
from mySokobanSolver import SokobanPuzzle

TIMEOUT = 500  # seconds

warehouse_folder = './warehouses'
files = sorted(os.listdir(warehouse_folder))

try:
    for filename in files:
        if not filename.endswith('.txt'):
            continue

        path = os.path.join(warehouse_folder, filename)
        wh = Warehouse()
        try:
            wh.load_warehouse(path)
        except Exception:
            print(f"{filename:30} | INVALID WAREHOUSE FILE")
            continue

        result = [None]
        problem_ref = [None]

        def run():
            problem = SokobanPuzzle(wh)
            problem_ref[0] = problem
            node = search.astar_graph_search(problem, problem.h)
            if node is None:
                result[0] = ('Impossible', None)
            else:
                result[0] = (node.solution(), node.path_cost)

        t0 = time.time()
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        showed_progress = False
        while thread.is_alive():
            thread.join(timeout=1)
            elapsed = time.time() - t0
            if elapsed > 1 and thread.is_alive():
                h_calls = getattr(problem_ref[0], 'h_calls', 0)
                print(f"  {filename:30} | h_calls: {h_calls:8} | elapsed: {elapsed:.1f}s",
                      end='\r', flush=True)
                showed_progress = True
            if elapsed >= TIMEOUT:
                break

        t1 = time.time()
        h_calls = getattr(problem_ref[0], 'h_calls', 0)

        if showed_progress:
            print()

        if thread.is_alive():
            print(f"{filename:30} | TIMED OUT   | h_calls: {h_calls:8} | {t1-t0:.3f}s")
        elif result[0] is None or result[0][0] == 'Impossible':
            print(f"{filename:30} | Impossible  | h_calls: {h_calls:8} | {t1-t0:.3f}s")
        else:
            solution, cost = result[0]
            print(f"{filename:30} | Cost: {cost:6} | Steps: {len(solution):4} | h_calls: {h_calls:8} | {t1-t0:.3f}s")

except KeyboardInterrupt:
    print("\n\nStopped by user.")
