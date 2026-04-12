import time
import os
import threading
from sokoban import Warehouse
from mySokobanSolver import solve_weighted_sokoban

TIMEOUT = 60  # seconds

warehouse_folder = './warehouses'
files = sorted(os.listdir(warehouse_folder))

for filename in files:
    if not filename.endswith('.txt'):
        continue
    
    path = os.path.join(warehouse_folder, filename)
    wh = Warehouse()
    
    try:
        wh.load_warehouse(path)
    except AssertionError:
        print(f"{filename:30} | INVALID WAREHOUSE FILE")
        continue
    
    result = [None]
    
    def run():
        result[0] = solve_weighted_sokoban(wh)
    
    t0 = time.time()
    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=TIMEOUT)
    t1 = time.time()
    
    if thread.is_alive():
        print(f"{filename:30} | TIMED OUT after {TIMEOUT}s")
    elif result[0] is None or result[0][0] == 'Impossible':
        print(f"{filename:30} | Impossible  | {t1-t0:.3f}s")
    else:
        solution, cost = result[0]
        print(f"{filename:30} | Cost: {cost:6} | Steps: {len(solution):4} | {t1-t0:.3f}s")