'''
Tests for taboo_cells in mySokobanSolver.

Two kinds of checks:
  1. Hand-crafted warehouses with a known expected taboo layout.
  2. Invariants that must hold for every warehouse in ./warehouses
     (no taboo on walls/targets, no taboo outside interior, shape matches, etc.).

Run directly:  python test_taboo_cells.py
Or with pytest: pytest test_taboo_cells.py -v
'''
import os
import unittest
from collections import deque

from sokoban import Warehouse
from mySokobanSolver import taboo_cells


WAREHOUSE_DIR = "./warehouses"


def wh_from_string(s):
    wh = Warehouse()
    wh.from_string(s)
    return wh


def parse_taboo(output):
    '''Return (taboo_set, wall_set, rows, cols) from the taboo_cells string.'''
    lines = output.split('\n')
    taboo, walls = set(), set()
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch == 'X':
                taboo.add((x, y))
            elif ch == '#':
                walls.add((x, y))
    cols = max((len(r) for r in lines), default=0)
    return taboo, walls, len(lines), cols


def interior_cells(wh):
    '''Inside = non-wall cells not reachable from the bounding-box border.
    Matches the definition used inside taboo_cells (any enclosed region counts).'''
    walls = set(wh.walls)
    ncols, nrows = wh.ncols, wh.nrows
    outside = set()
    q = deque()
    for x in range(ncols):
        for y in range(nrows):
            if (x == 0 or x == ncols - 1 or y == 0 or y == nrows - 1) and (x, y) not in walls:
                outside.add((x, y))
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < ncols and 0 <= n[1] < nrows and n not in walls and n not in outside:
                outside.add(n)
                q.append(n)
    return {(x, y) for x in range(ncols) for y in range(nrows)
            if (x, y) not in walls and (x, y) not in outside}


class TestHandCrafted(unittest.TestCase):
    '''Small warehouses where the expected taboo cells are easy to reason about.'''

    def test_empty_room_all_inside_taboo(self):
        # 3x2 interior, no targets -> every inside cell is taboo.
        s = (
            "#####\n"
            "#@  #\n"
            "#   #\n"
            "#####"
        )
        out = taboo_cells(wh_from_string(s))
        taboo, _, _, _ = parse_taboo(out)
        expected = {(1, 1), (2, 1), (3, 1), (1, 2), (2, 2), (3, 2)}
        self.assertEqual(taboo, expected)

    def test_target_in_middle_breaks_rule2(self):
        # Target at (2,2) -> Rule 2 segment through (2,2) is not taboo.
        # Add a $ to satisfy boxes==targets; box position is ignored by taboo_cells.
        s = (
            "#####\n"
            "#@$ #\n"
            "# . #\n"
            "#####"
        )
        out = taboo_cells(wh_from_string(s))
        taboo, _, _, _ = parse_taboo(out)
        # (2,2) is on a target, so not taboo. (2,1) still taboo by Rule 2.
        self.assertNotIn((2, 2), taboo)
        self.assertIn((2, 1), taboo)
        # Four corners remain taboo.
        for c in [(1, 1), (3, 1), (1, 2), (3, 2)]:
            self.assertIn(c, taboo)

    def test_corner_on_target_is_not_taboo(self):
        # Put a target on a corner cell; Rule 1 must skip it.
        s = (
            "#####\n"
            "#@$ #\n"
            "#  .#\n"
            "#####"
        )
        out = taboo_cells(wh_from_string(s))
        taboo, _, _, _ = parse_taboo(out)
        self.assertNotIn((3, 2), taboo)  # target corner

    def test_no_taboo_on_walls_or_targets(self):
        s = (
            "#######\n"
            "#@ .$ #\n"
            "#  $. #\n"
            "#######"
        )
        wh = wh_from_string(s)
        out = taboo_cells(wh)
        taboo, walls, _, _ = parse_taboo(out)
        self.assertTrue(taboo.isdisjoint(walls))
        self.assertTrue(taboo.isdisjoint(set(wh.targets)))


class TestInvariantsOverAllWarehouses(unittest.TestCase):
    '''Run taboo_cells on every warehouse file and check properties that must always hold.'''

    @classmethod
    def setUpClass(cls):
        cls.cases = []
        if not os.path.isdir(WAREHOUSE_DIR):
            return
        for name in sorted(os.listdir(WAREHOUSE_DIR)):
            if not name.endswith('.txt'):
                continue
            wh = Warehouse()
            try:
                wh.load_warehouse(os.path.join(WAREHOUSE_DIR, name))
            except Exception:
                continue
            cls.cases.append((name, wh))

    def test_walls_preserved(self):
        for name, wh in self.cases:
            with self.subTest(name=name):
                _, walls_out, _, _ = parse_taboo(taboo_cells(wh))
                self.assertEqual(walls_out, set(wh.walls),
                                 f"{name}: walls in output don't match input")

    def test_no_taboo_on_targets(self):
        for name, wh in self.cases:
            with self.subTest(name=name):
                taboo, _, _, _ = parse_taboo(taboo_cells(wh))
                overlap = taboo & set(wh.targets)
                self.assertFalse(overlap, f"{name}: taboo overlaps targets {overlap}")

    def test_taboo_is_inside_warehouse(self):
        for name, wh in self.cases:
            with self.subTest(name=name):
                taboo, _, _, _ = parse_taboo(taboo_cells(wh))
                inside = interior_cells(wh)
                outside = taboo - inside
                self.assertFalse(outside, f"{name}: taboo cells outside interior: {outside}")

    def test_rule1_corners_are_taboo(self):
        # Every non-target interior cell with a wall on one H neighbour and one V
        # neighbour must be flagged taboo.
        for name, wh in self.cases:
            with self.subTest(name=name):
                taboo, _, _, _ = parse_taboo(taboo_cells(wh))
                walls = set(wh.walls)
                targets = set(wh.targets)
                inside = interior_cells(wh)
                missed = []
                for (x, y) in inside:
                    if (x, y) in targets:
                        continue
                    wall_h = (x - 1, y) in walls or (x + 1, y) in walls
                    wall_v = (x, y - 1) in walls or (x, y + 1) in walls
                    if wall_h and wall_v and (x, y) not in taboo:
                        missed.append((x, y))
                self.assertFalse(missed, f"{name}: Rule-1 corners not flagged: {missed}")

    def test_output_only_expected_chars(self):
        for name, wh in self.cases:
            with self.subTest(name=name):
                for ch in taboo_cells(wh):
                    self.assertIn(ch, {'#', 'X', ' ', '\n'},
                                  f"{name}: unexpected char {ch!r} in output")


if __name__ == '__main__':
    unittest.main(verbosity=2)
