"""
IDEALaser (Blocktime Evaluation) Version 0.1

(Unlike in Simultaneous Evaluation, firing a laser at a redirector's firing direction, or at a splitter, will not cause
a laser to be returned in the opposite direction when it is turned off. Lasers firing at a redirector's firing direction
will not activate it. Splitters' faces have 3 modes: open, connected and closed. the splitter's faces all start open,
and the first time 1 or more sides receive lasers, those sides become connected while the other sides become closed,
which fire lasers, and do not consider lasers firing back at it to activate it; when the splitter stops receiving lasers
from one side, that side becomes closed and starts firing lasers; when all sides become closed, all sides become open
instead (i.e. it stopped receiving any laser which activates it))

Lasers are classified into 2 groups: stable (those which are already hitting a block, another laser or going to
infinity) and unstable (unformed lasers, i.e. going to be emitted this cycle, or half-formed lasers)

0. First, for all laser-emitting blocks, if they were activated last step, add unstable lasers. If they were deactivated
last step, remove all associated lasers.

1. For all unstable lasers, draw their potential path to infinity or until it hits a block. (For the purposes of memory,
infinity is defined as the furthest coordinate where no other block placed by the player is further; e.g.
if a laser path is travelling right and the rightmost blocks have x-coordinate 5, laser will be drawn until x-coordinate
6.) For the purpose of efficient search, other than the default block list, there will be a dictionary listing all
blocks by x-column (e.g. {1: [y_col_1, y_col_2], 3: [y_col_2, y_col_4]}, y_col lists are sorted), and another for y-row,
to look up the first block it will hit in the direction it is facing.

2. Draw unstable lasers until they hit another unstable laser’s potential path, a stable laser, a block, or infinity.
Lasers pointing each other directly will ignore each other (internally, two instances of lasers will be stored, both
having the same coordinates, but different sources/directions).

3. Check if unstable lasers stopping at another unstable laser’s potential path are also hitting the other unstable
laser itself. If yes (or if lasers are pointing each other directly), both become stable. If no, that laser remains
half-formed and unstable. Lasers stopping at a block or infinity will become stable. If an unstable laser hits a stable
laser, check if this unblocks another laser; if yes, that other laser becomes unstable, and the stable laser is
shortened.

4. For all remaining unstable lasers, check if the laser whose potential path was blocking it became stable. If there
are still lasers to which the answer is yes, repeat the whole process from step 1. If not, this is the end of
evaluation, and all remaining unstable lasers will remain half-formed.

How everything is stored:
1. There exists a 2D array called 'world'. The world depends on the blocks placed, just like in the other version, and
is 2 wider on all sides of the smallest rectangle containing all blocks. E.g. if there is only a single block, the world
is a 5x5 with the block in the center. It is rendered once when first running the solution for blocks, then rendered
every step for lasers.
2. Where a block is placed, a "b" is placed at the coordinates of the block. The edges of the world are also lined with
"b" in order to simulate "infinity blocks".
3. Add "sw", "sa", "ss" and/or "sd" for blocks which emit lasers if they are active in a certain step (generators are
always on, input which is set to true is always on (and vice versa), and redirectors/splitters are conditionally on).
4. Add "0w", "0a", "0s", "0d" for lasers that are going a certain direction and unstable. Change 0 to 1 when stable,
and 1 to 2 when directly above a block/perpendicular laser (see above for laser rules). They do not exist on their own
source blocks.
"""
from os import mkdir, path, listdir
from pickle import dump, load
from idealaser_globals import facing_dict, opposite_face_dict, cost_dict
try:
    mkdir('IDEALaser Saves')
except FileExistsError:
    pass
try:
    mkdir('IDEALaser Saves/Blocktime Saves')
except FileExistsError:
    pass
block_coordinates = {}
block_x = {}  # TODO use this and block_y
block_y = {}
laser_list = []
laser_coordinates = {}
cycle_count = 0
world = None


class BBlock:
    def __init__(self, x, y):
        self.coordinates = x, y
        block_coordinates[self.coordinates] = self
    
    def prestep(self):
        pass
    
    def step(self):
        pass
    
    def poststep(self):
        pass


class BGenerator(BBlock):
    def __init__(self, x, y, direction):
        super().__init__(x, y)
        self.facing = direction
        self.cost = cost_dict['g']
    
    def __repr__(self):
        return f'Generator{*self.coordinates, self.facing}'


class BInput(BBlock):
    def __init__(self, x, y, direction, level):
        super().__init__(x, y)
        self.facing = direction
        if level == 't':
            self.state = True
        else:
            self.state = False
        self.cost = cost_dict['i']
    
    def __repr__(self):
        return f'Input{*self.coordinates, self.facing, self.state}'


class BRedirector(BBlock):
    def __init__(self, x, y, direction):
        super().__init__(x, y)
        self.facing = direction
        self.state = False
        self.cost = cost_dict['r']
    
    def __repr__(self):
        return f'Redirector{*self.coordinates, self.facing}'


class BSplitter(BBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = False
        self.cost = cost_dict['p']
    
    def __repr__(self):
        return f'Splitter{self.coordinates}'


class BOutput(BBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = False
        self.cost = cost_dict['o']
    
    def __repr__(self):
        return f'Output{self.coordinates}'


class BBlocker(BBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.cost = cost_dict['l']
    
    def __repr__(self):
        return f'Blocker{self.coordinates}'


class BBridge(BBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.cost = cost_dict['b']
    
    def __repr__(self):
        return f'Bridge{self.coordinates}'


def main_menu():
    global block_coordinates
    global block_x
    global block_y
    global laser_coordinates
    while True:
        try:
            user_input = input('''\n'run': run solution (does not begin stepping, just displays initial state)
'help1': full list of block IDs (with examples on how to add to solution) and commands
Enter a block ID with required arguments to add it to solution (see help1), or enter a command: ''').split()
            try:
                user_coordinates = (int(user_input[1]), int(user_input[2]))
                try:  # Commands for existing blocks
                    this_block = block_coordinates[user_coordinates]
                    if user_input[0] == 'del':
                        del block_coordinates[user_coordinates]
                    elif user_input[0] == 'toggle':
                        if type(this_block) == BInput:
                            this_block.state = not this_block.state
                        else:
                            print("Block is not an input block.")
                    else:
                        print("Coordinates already occupied by block.")
                except KeyError:  # no existing block found at coordinates
                    # Commands for adding new blocks
                    if user_input[0] == 'g':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            BGenerator(*user_coordinates, user_input[3])
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'r':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            BRedirector(*user_coordinates, user_input[3])
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'p':
                        BSplitter(*user_coordinates)
                    elif user_input[0] == 'l':
                        BBlocker(*user_coordinates)
                    elif user_input[0] == 'b':
                        BBridge(*user_coordinates)
                    elif user_input[0] == 'i':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            BInput(*user_coordinates, user_input[3], user_input[4])
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'o':
                        BOutput(*user_coordinates)
                    else:
                        print("Unrecognised command.")
            except IndexError:
                # Commands not concerning individual blocks
                if user_input[0] == 'run':
                    if block_coordinates:  # if there exists at least 1 block
                        return
                    else:
                        print("Must put down at least 1 block before running.")
                elif user_input[0] == 'clear':
                    block_coordinates.clear()
                elif user_input[0] == 'show_block':
                    print(block_coordinates)
                elif user_input[0] == 'save':
                    save_name = input("Enter file name (enter nothing to escape): ").strip()
                    if save_name != '':
                        for char in save_name:
                            if not char.isalnum() and char not in ('-', ' '):
                                print("Invalid filename. Allowed: a-z, A-Z, 0-9, '-', space")
                                break
                        else:
                            flag = False
                            if path.exists(file_path := f'IDEALaser Saves\\Blocktime Saves\\{save_name}.txt'):
                                if input("File already exists. Overwrite? (y: yes, anything: back): ") == 'y':
                                    flag = True
                            else:
                                flag = True
                            if flag:
                                dump(block_coordinates, open(file_path, 'wb'))
                elif user_input[0] == 'load':
                    load_list = listdir('IDEALaser Saves\\Blocktime Saves')
                    print()
                    for file in load_list:
                        print(file)
                    print()
                    filename = input("Enter file name (without .txt), or an invalid name to escape: ") + '.txt'
                    if filename in load_list:
                        try:
                            temp = load(open(f'IDEALaser Saves\\Blocktime Saves\\{filename}', 'rb'))
                            if type(temp) == list:
                                print("Old save format detected. Converting to new save format.")
                                temp2 = {}
                                for block in temp:
                                    temp2[block.coordinates] = block
                                temp = temp2
                            block_coordinates = temp
                        except:  # TODO specify error(s)?
                            print("Error loading save. (Did you edit the file?)")
                elif user_input[0] == 'q':
                    return 'q'
                elif user_input[0] == 'help1':
                    print(f'''\nBlockID: name (cost), requirements (assume x=1, y=2, direction(wasd)=right, state=true):
'g': Generator ({cost_dict['g']}), coordinates and direction, e.g. 'g 1 2 d'
'r': Redirector ({cost_dict['r']}), coordinates and direction, e.g. 'r 1 2 d'
'p': Splitter ({cost_dict['p']}), coordinates, e.g. 'p 1 2'
'l': Blocker ({cost_dict['l']}), coordinates, e.g. 'l 1 2'
'b': Bridge ({cost_dict['b']}), coordinates, e.g. 'b 1 2'
'i': Input ({cost_dict['i']}), coordinates and direction and state (firing or not), e.g. 'i 1 2 d t'
'o': Output ({cost_dict['o']}), coordinates, e.g. 'o 1 2'

Other Commands:
'toggle x y': Change the state of an existing input at coordinates (x, y) from on to off, or from off to on
'del x y': Delete block at coordinates (x, y)
'clear': Clear all blocks
'show_block': Show block list
'save': Save current setup (only saves blocks, does not save lasers)
'load': Load block setup from a save (unsaved setups will be lost)
'q': Quit (usable when running solution) (unsaved setups will be lost)''')
                else:
                    print("Unrecognised command.")
        except (ValueError, IndexError):
            print("\nPlease enter valid values.")


def edge():
    global block_coordinates
    temp_block_x = []
    temp_block_y = []
    for block in block_coordinates.keys():
        temp_block_x.append(block[0])
        temp_block_y.append(block[1])
    max_x = max(temp_block_x) + 1
    min_x = min(temp_block_x) - 1
    max_y = max(temp_block_y) + 1
    min_y = min(temp_block_y) - 1
    return max_x, min_x, max_y, min_y


def laser_eval():
    global world
    if world is None:
        max_x, min_x, max_y, min_y = edge()
        world = [[[] for _ in range(max_y - min_y + 3)] for _ in range(max_x - min_x + 3)]
        for i, col in enumerate(world):
            if i == 0 or i == len(world) - 1:
                for cell in col:
                    cell.append('b')
            else:
                col[0].append('b')
                col[-1].append('b')
        for key in block_coordinates:
            # world[key]
            pass
        print(world)  # TODO del
    for block in block_coordinates.values():
        if type(block) == BGenerator:  # TODO include other types later
            pass


def tile_print():  # TODO
    pass


def run_solution():  # TODO
    laser_eval()
    pass


print("WARNING: WORK IN PROGRESS. Play with idealaser_s.py first, sorry.")  # TODO remove
print('''Welcome to IdeaLaser (blocktime evaluation version).
Challenge: create logical gates using the tools provided.''')
while True:
    if main_menu() == 'q':
        break
    else:
        tile_print()
        if run_solution() == 'q':
            break
