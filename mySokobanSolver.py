
'''

    Sokoban assignment


The functions and classes defined in this module will be called by a marker script. 
You should complete the functions and classes according to their specified interfaces.

No partial marks will be awarded for functions that do not meet the specifications
of the interfaces.

You are NOT allowed to change the defined interfaces.
In other words, you must fully adhere to the specifications of the 
functions, their arguments and returned values.
Changing the interfacce of a function will likely result in a fail 
for the test of your code. This is not negotiable! 

You have to make sure that your code works with the files provided 
(search.py and sokoban.py) as your code will be tested 
with the original copies of these files. 

Last modified by 2021-08-17  by f.maire@qut.edu.au
- clarifiy some comments, rename some functions
  (and hopefully didn't introduce any bug!)

'''

# You have to make sure that your code works with 
# the files provided (search.py and sokoban.py) as your code will be tested 
# with these files
import search 
import sokoban


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def my_team():

    return [ (11806427, 'Aathmika', 'Gokula Krishna'), (11539658, 'Jack', 'Hillman'), (12425605, 'Sultan', 'Sajid') ]

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def taboo_cells(warehouse):
    '''
    Identify the taboo cells of a warehouse. A "taboo cell" is by definition
    a cell inside a warehouse such that whenever a box get pushed on such
    a cell then the puzzle becomes unsolvable.

    Cells outside the warehouse are not taboo. It is a fail to tag one as taboo.

    When determining the taboo cells, you must ignore all the existing boxes,
    only consider the walls and the target  cells.
    Use only the following rules to determine the taboo cells;
     Rule 1: if a cell is a corner and not a target, then it is a taboo cell.
     Rule 2: all the cells between two corners along a wall are taboo if none of
             these cells is a target.

    @param warehouse:
        a Warehouse object with a worker inside the warehouse

    @return
       A string representing the warehouse with only the wall cells marked with
       a '#' and the taboo cells marked with a 'X'.
       The returned string should NOT have marks for the worker, the targets,
       and the boxes.
    '''
    from collections import deque

    ncols, nrows = warehouse.ncols, warehouse.nrows
    walls = set(warehouse.walls)
    targets = set(warehouse.targets)

    # Step 1: BFS from boundary to find all "outside" cells (reachable from the border without crossing walls)
    outside = set()
    queue = deque()
    for x in range(ncols):
        for y in range(nrows):
            if (x == 0 or x == ncols - 1 or y == 0 or y == nrows - 1) and (x, y) not in walls:
                outside.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < ncols and 0 <= ny < nrows and (nx, ny) not in walls and (nx, ny) not in outside:
                outside.add((nx, ny))
                queue.append((nx, ny))

    # Inside cells = non-wall cells not reachable from outside
    inside = set()
    for x in range(ncols):
        for y in range(nrows):
            if (x, y) not in walls and (x, y) not in outside:
                inside.add((x, y))

    # Step 2: Find ALL geometric corners (wall on at least one horizontal
    # AND at least one vertical neighbour). These are used as anchors for Rule 2.
    all_corners = set()
    for (x, y) in inside:
        wall_h = (x - 1, y) in walls or (x + 1, y) in walls
        wall_v = (x, y - 1) in walls or (x, y + 1) in walls
        if wall_h and wall_v:
            all_corners.add((x, y))

    # Rule 1: corner and not a target → taboo
    taboo = set(c for c in all_corners if c not in targets)

    # Step 3: Rule 2 - cells between two corners along a wall with no target.
    # Use ALL geometric corners as anchors (including corners on targets),
    # because a target on a corner still forms a wall-line boundary.
    # Horizontal: same row, wall consistently above or below the whole segment
    for y in range(nrows):
        row_corners = sorted(x for (x, ry) in all_corners if ry == y)
        for i in range(len(row_corners)):
            for j in range(i + 1, len(row_corners)):
                x1, x2 = row_corners[i], row_corners[j]
                between = [(x, y) for x in range(x1 + 1, x2)]
                if not between:
                    continue
                if not all(c in inside for c in between):
                    continue
                if any(c in targets for c in between):
                    continue
                xs = range(x1, x2 + 1)
                wall_above = all((x, y - 1) in walls for x in xs)
                wall_below = all((x, y + 1) in walls for x in xs)
                if wall_above or wall_below:
                    taboo.update(between)

    # Vertical: same column, wall consistently left or right of the whole segment
    for x in range(ncols):
        col_corners = sorted(y for (cx, y) in all_corners if cx == x)
        for i in range(len(col_corners)):
            for j in range(i + 1, len(col_corners)):
                y1, y2 = col_corners[i], col_corners[j]
                between = [(x, y) for y in range(y1 + 1, y2)]
                if not between:
                    continue
                if not all(c in inside for c in between):
                    continue
                if any(c in targets for c in between):
                    continue
                ys = range(y1, y2 + 1)
                wall_left = all((x - 1, y) in walls for y in ys)
                wall_right = all((x + 1, y) in walls for y in ys)
                if wall_left or wall_right:
                    taboo.update(between)

    # Build output string: walls as '#', taboo as 'X', everything else as ' '
    X, Y = zip(*walls)
    x_size, y_size = 1 + max(X), 1 + max(Y)
    vis = [[' '] * x_size for _ in range(y_size)]
    for (x, y) in walls:
        vis[y][x] = '#'
    for (x, y) in taboo:
        vis[y][x] = 'X'
    return '\n'.join(''.join(row) for row in vis)
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class SokobanPuzzle(search.Problem):
    '''
    An instance of the class 'SokobanPuzzle' represents a Sokoban puzzle.
    An instance contains information about the walls, the targets, the boxes
    and the worker.

    Your implementation should be fully compatible with the search functions of 
    the provided module 'search.py'. 
    
    '''
    def __init__(self, warehouse): #initial values
        self.walls = set(warehouse.walls) #get the walls

        self.targets = set(warehouse.targets) #get the target

        self.weights = list(warehouse.weights)  #get the weights of the boxes

        self.direction_map = {
            'Left':  (-1,  0),
            'Right': ( 1,  0),
            'Up':    ( 0, -1),
            'Down':  ( 0,  1),
        }

        taboo_string = taboo_cells(warehouse) #convert taboo cells to a tuple from the string
        self.taboo = set()
        for y, row in enumerate(taboo_string.split('\n')):
            for x, char in enumerate(row):
                if char == 'X':
                    self.taboo.add((x, y))

        initial_state = (warehouse.worker, tuple(warehouse.boxes))
        super().__init__(initial_state)
        self._h_cache = {}
        self.h_calls = 0


    def actions(self, state): #checks each direction; left right up down. returns a list of valid actions that avoid taboo cells or walls or moving boxes into places that are bad
        worker, boxes = state
        boxes_set = set(boxes)
        valid_actions = []
        
        for direction, (dx, dy) in self.direction_map.items():
            new_worker = (worker[0]+dx, worker[1]+dy)
            
            if new_worker in self.walls:
                continue
            if new_worker in boxes_set:
                new_box = (new_worker[0]+dx, new_worker[1]+dy)
                if new_box in self.walls or new_box in boxes_set:
                    continue
                if new_box in self.taboo:
                    continue
            valid_actions.append(direction)
        return valid_actions
    

    def result(self, state, action): #applies all valid actions against the current worker, and returns the results
        worker, boxes = state
        boxes = list(boxes)
        dx, dy = self.direction_map[action]
        new_worker = (worker[0] + dx, worker[1] + dy)

        if new_worker in boxes:
            idx = boxes.index(new_worker)  
            new_box = (new_worker[0] + dx, new_worker[1] + dy)
            boxes[idx] = new_box  

        return (new_worker, tuple(boxes)) 

    def goal_test(self, state): #checks to see if game is won
        worker, boxes = state
        return all(box in self.targets for box in boxes)
    
    def path_cost(self, c, state1, action, state2): #calculate the current cost of each box
        boxes1 = state1[1]  
        boxes2 = state2[1]  
        
        for i, (b1, b2) in enumerate(zip(boxes1, boxes2)):
            if b1 != b2: 
                weight = self.weights[i]  
                return c + 1 + weight
        
        return c + 1
    
    def h(self, node):
        self.h_calls += 1

        # Cache results: astar may evaluate the same state from different paths
        state = node.state
        if state in self._h_cache:
            return self._h_cache[state]

        worker, boxes = state
        targets = list(self.targets)

        unplaced = [(i, box) for i, box in enumerate(boxes) if box not in self.targets]

        if not unplaced:
            self._h_cache[state] = 0
            return 0

        # For each unplaced box, take the minimum push cost to any target.
        min_box_cost = sum(
            min(
                (abs(bpos[0] - t[0]) + abs(bpos[1] - t[1])) * (1 + self.weights[bi])
                for t in targets
            )
            for bi, bpos in unplaced
        )

        # Worker must walk to at least one unplaced box before pushing starts.
        # This repositioning cost is independent of (and additive to) push costs.
        worker_dist = min(
            abs(worker[0] - bpos[0]) + abs(worker[1] - bpos[1])
            for _, bpos in unplaced
        )

        result = min_box_cost + worker_dist
        self._h_cache[state] = result
        return result
    


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def check_elem_action_seq(warehouse, action_seq):
    '''

    Determine if the sequence of actions listed in 'action_seq' is legal or not.

    Important notes:
      - a legal sequence of actions does not necessarily solve the puzzle.
      - an action is legal even if it pushes a box onto a taboo cell.

    @param warehouse: a valid Warehouse object

    @param action_seq: a sequence of legal actions.
           For example, ['Left', 'Down', 'Down', 'Right', 'Up', 'Down']

    @return
        The string 'Impossible', if one of the action was not valid.
           For example, if the agent tries to push two boxes at the same time,
                        or push a box into a wall.
        Otherwise, if all actions were successful, return
               A string representing the state of the puzzle after applying
               the sequence of actions.  This must be the same string as the
               string returned by the method  Warehouse.__str__()
    '''
    direction_map = {
        'Left':  (-1,  0),
        'Right': ( 1,  0),
        'Up':    ( 0, -1),
        'Down':  ( 0,  1),
    }

    walls = set(warehouse.walls)
    boxes = list(warehouse.boxes)  # mutable copy; preserves order for weights
    worker = warehouse.worker

    for action in action_seq:
        dx, dy = direction_map[action]
        new_worker = (worker[0] + dx, worker[1] + dy)

        # Hard constraint: worker cannot walk into a wall
        if new_worker in walls:
            return 'Impossible'

        # Hard constraint: if a box is pushed it must not hit a wall or another box
        if new_worker in boxes:
            new_box = (new_worker[0] + dx, new_worker[1] + dy)
            if new_box in walls or new_box in boxes:
                return 'Impossible'
            boxes[boxes.index(new_worker)] = new_box

        worker = new_worker

    return warehouse.copy(worker=worker, boxes=boxes).__str__()


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

def solve_weighted_sokoban(warehouse):
    '''
    This function analyses the given warehouse.
    It returns the two items. The first item is an action sequence solution. 
    The second item is the total cost of this action sequence.
    
    @param 
     warehouse: a valid Warehouse object

    @return 
    
        If puzzle cannot be solved 
            return 'Impossible', None
        
        If a solution was found, 
            return S, C 
            where S is a list of actions that solves
            the given puzzle coded with 'Left', 'Right', 'Up', 'Down'
            For example, ['Left', 'Down', Down','Right', 'Up', 'Down']
            If the puzzle is already in a goal state, simply return []
            C is the total cost of the action sequence C

    '''
    problem = SokobanPuzzle(warehouse)
    node = search.astar_graph_search(problem, problem.h)
    
    if node is None:
        return 'Impossible', None
    
    return node.solution(), node.path_cost

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

