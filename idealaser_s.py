"""
IDEALaser (Simultaneous Evaluation) Version 1.2

IMPORTANT: coordinates are (x, y), and since x changes column and y changes row, they are (col, row) not (row, col)

Order of evaluation:
1. For redirectors and splitters, if they detect any pulse at the coordinates they are going to fire, and
that pulse is facing the block, it will not fire. This is to prevent them from firing back at lasers currently firing at
them. Once the pulses stop, the block will release a single pulse.

2. Pulses which have collided into each other or into any non-bridge block are deleted. They will only be deleted while
in a bridge block if they are in a head-on collision.

3. Remaining pulses advance.

4. Blocks which spawn pulses (including those activated in Step 1) do so.

5. Check if blocks which are activated by pulses (redirectors, splitters, output), are active. Activate/deactivate
correspondingly.

6. Display tiles for the player.
"""
from os import mkdir, path, listdir
from pickle import dump, load
from random import random
from math import e
from idealaser_globals import facing_dict, opposite_face_dict, cost_dict
try:
    mkdir('IDEALaser Saves')
except FileExistsError:
    pass
try:
    mkdir('IDEALaser Saves/Simultaneous Saves')
except FileExistsError:
    pass
block_coordinates = {}
pulse_list = []
pulse_coordinates = {}
cycle_count = 0


class SPulse:
    def __init__(self, x, y, direction):  # direction = wasd
        self.coordinates = x, y
        self.facing = direction
        pulse_list.append(self)
        try:
            pulse_coordinates[self.coordinates].append(self.facing)
        except KeyError:
            pulse_coordinates[self.coordinates] = [self.facing]
    
    def __repr__(self):
        return f'Pulse{*self.coordinates, self.facing}'
    
    def step(self):
        # Remove old entry in coordinates dict
        pulse_coordinates[self.coordinates].remove(self.facing)
        if not pulse_coordinates[self.coordinates]:
            del pulse_coordinates[self.coordinates]  # remove key if it has no values, i.e. coordinate has no pulses
        # Update coordinates
        if self.facing == 'w':
            self.coordinates = self.coordinates[0], self.coordinates[1] + 1
        elif self.facing == 'a':
            self.coordinates = self.coordinates[0] - 1, self.coordinates[1]
        elif self.facing == 's':
            self.coordinates = self.coordinates[0], self.coordinates[1] - 1
        else:  # self.facing == 'd'
            self.coordinates = self.coordinates[0] + 1, self.coordinates[1]
        # Add new entry in coordinates dict
        try:
            pulse_coordinates[self.coordinates].append(self.facing)
        except KeyError:
            pulse_coordinates[self.coordinates] = [self.facing]


class SBlock:
    def __init__(self, x, y):
        self.coordinates = x, y
        block_coordinates[self.coordinates] = self
    
    def prestep(self):
        pass
    
    def step(self):
        pass
    
    def poststep(self):
        pass


class SGenerator(SBlock):
    def __init__(self, x, y, direction):
        super().__init__(x, y)
        self.facing = direction
        self.cost = cost_dict['g']
    
    def __repr__(self):
        return f'Generator{*self.coordinates, self.facing}'
    
    def step(self):
        if self.facing == 'w':
            SPulse(self.coordinates[0], self.coordinates[1] + 1, self.facing)
        elif self.facing == 'a':
            SPulse(self.coordinates[0] - 1, self.coordinates[1], self.facing)
        elif self.facing == 's':
            SPulse(self.coordinates[0], self.coordinates[1] - 1, self.facing)
        else:
            SPulse(self.coordinates[0] + 1, self.coordinates[1], self.facing)


class SInput(SBlock):
    def __init__(self, x, y, direction, level, sequence):
        super().__init__(x, y)
        self.facing = direction
        if level == 't':
            self.state = True
        else:
            self.state = False
        self.cost = cost_dict['i']
        self.seq = sequence
        self.seq_index = 0
        self.seq_count = 0
    
    def __repr__(self):
        return f'Input{*self.coordinates, self.facing, self.state, self.seq}'
    
    def step(self):
        if self.state:
            if self.facing == 'w':
                SPulse(self.coordinates[0], self.coordinates[1] + 1, self.facing)
            elif self.facing == 'a':
                SPulse(self.coordinates[0] - 1, self.coordinates[1], self.facing)
            elif self.facing == 's':
                SPulse(self.coordinates[0], self.coordinates[1] - 1, self.facing)
            else:  # 'd'
                SPulse(self.coordinates[0] + 1, self.coordinates[1], self.facing)
        if self.seq:
            self.seq_count += 1
            if (self.seq[self.seq_index] == 0 and random() < 1 / e) or self.seq_count == self.seq[self.seq_index]:
                self.state = not self.state
                self.seq_count = 0
                self.seq_index += 1
                if self.seq_index == len(self.seq):
                    self.seq_index = 0


class SRedirector(SBlock):
    def __init__(self, x, y, direction):
        super().__init__(x, y)
        self.facing = direction
        self.state = False
        self.fire = False
        if direction == 'w':
            self.next_coordinates = x, y + 1
        elif direction == 'a':
            self.next_coordinates = x - 1, y
        elif direction == 's':
            self.next_coordinates = x, y - 1
        else:  # direction == 'd'
            self.next_coordinates = x + 1, y
        self.cost = cost_dict['r']
    
    def __repr__(self):
        return f'Redirector{*self.coordinates, self.facing}'
    
    def prestep(self):
        self.fire = False
        if self.state:
            try:
                if type(block_coordinates[self.next_coordinates]) != SBridge:
                    self.fire = True
            except KeyError:
                try:
                    if opposite_face_dict[self.facing] not in pulse_coordinates[self.next_coordinates]:
                        self.fire = True
                except KeyError:
                    self.fire = True
    
    def step(self):
        if self.fire:
            SPulse(*self.next_coordinates, self.facing)
    
    def poststep(self):
        if self.coordinates in pulse_coordinates:
            self.state = True
        else:
            self.state = False


class SSplitter(SBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.w = x, y + 1
        self.a = x - 1, y
        self.s = x, y - 1
        self.d = x + 1, y
        self.next_coordinates = (self.w, self.a, self.s, self.d)
        self.reference = ('w', self.w), ('a', self.a), ('s', self.s), ('d', self.d)
        self.state = False
        self.fire_list = [False, False, False, False]  # wasd
        self.cost = cost_dict['p']
    
    def __repr__(self):
        return f'Splitter{self.coordinates}'
    
    def prestep(self):
        self.fire_list = [False, False, False, False]
        if self.state:
            for i in 0, 1, 2, 3:
                try:
                    if block_coordinates[self.next_coordinates[i]] != SBridge:
                        self.fire_list[i] = True
                except KeyError:
                    pass
            for i in 0, 1, 2, 3:
                if not self.fire_list[i]:
                    try:
                        if opposite_face_dict[self.reference[i][0]] not in pulse_coordinates[self.reference[i][1]]:
                            self.fire_list[i] = True
                    except KeyError:
                        self.fire_list[i] = True
    
    def step(self):
        for i in 0, 1, 2, 3:
            if self.fire_list[i]:
                SPulse(*self.reference[i][1], self.reference[i][0])
    
    def poststep(self):
        if self.coordinates in pulse_coordinates:
            self.state = True
        else:
            self.state = False


class SOutput(SBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.state = False
        self.cost = cost_dict['o']
    
    def __repr__(self):
        return f'Output{self.coordinates}'
    
    def poststep(self):
        if self.coordinates in pulse_coordinates:
            self.state = True
        else:
            self.state = False


class SBlocker(SBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.cost = cost_dict['l']
    
    def __repr__(self):
        return f'Blocker{self.coordinates}'


class SBridge(SBlock):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.cost = cost_dict['b']
    
    def __repr__(self):
        return f'Bridge{self.coordinates}'


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


def tile_print():
    global pulse_list
    global pulse_coordinates
    global cycle_count
    cost_sum = 0
    for block in block_coordinates.values():
        cost_sum += block.cost
    print(f"Cost: {cost_sum}")
    print(f"Cycles: {cycle_count}")
    output_dict = {}
    for block in block_coordinates.values():
        if type(block) == SOutput:
            output_dict[block.coordinates] = block.state
    cycle_count += 1
    max_x, min_x, max_y, min_y = edge()
    area_int = (max_x - min_x - 1) * (max_y - min_y - 1)
    print(f"Area: {area_int}")
    if output_dict:
        print(f"Outputs: ", end="")
        for k, v in output_dict.items():
            print(f"{k}: {str(v)[0].lower()}; ", end="")
        print()
    for row in range(max_y + 1, min_y - 1, -1):
        for col in range(min_x - 1, max_x + 1):
            if row == max_y + 1:
                if col != min_x - 1:
                    if -1 < col < 10:  # 1-digit column numbers
                        print(f"{col} ", end='')
                    elif col > -10 or col < 100:  # 2-digit column numbers
                        print(f"{col}", end='')
                    else:  # 3-digit column numbers
                        print(col, end='')
                else:
                    print("  ", end='')
            elif col == min_x - 1:
                if -1 < row < 10:  # 1-digit row numbers
                    print(f"{row} ", end='')
                elif row > -10 or row < 100:  # 3-digit row numbers
                    print(f"{row}", end='')
                else:  # 3-digit row numbers
                    print(row, end='')
            else:
                try:
                    block = block_coordinates[(col, row)]
                    block_type = type(block)
                    if block_type == SGenerator:
                        print(f"G{facing_dict[block.facing]}", end='')
                    elif block_type == SInput:
                        if block.state:
                            print(f"I{facing_dict[block.facing]}", end='')
                        else:
                            print("If", end='')
                    elif block_type == SRedirector:
                        if block.state:
                            print(f"{block.facing.upper()}t", end='')
                        else:
                            print(f"{block.facing.upper()}f", end='')
                    elif block_type == SSplitter:
                        if block.state:
                            print("Pt", end='')
                        else:
                            print("Pf", end='')
                    elif block_type == SOutput:
                        try:
                            if len(pulse_coordinates[(col, row)]) == 1:
                                print("Ot", end='')
                            else:
                                print("O#", end='')
                        except KeyError:
                            print("Of", end='')
                    elif block_type == SBlocker:
                        try:
                            if len(pulse_coordinates[(col, row)]) == 1:
                                print("Lt", end='')
                            else:
                                print("L#", end='')
                        except KeyError:
                            print("Lf", end='')
                    elif block_type == SBridge:
                        try:
                            direction_list = pulse_coordinates[(col, row)]
                            vertical = 0  # 0: no pulse, 1: no collision, 2: collision
                            horizontal = 0  # same
                            if 'w' in direction_list:
                                if 's' in direction_list:
                                    vertical = 2
                                else:
                                    vertical = 1
                            elif 's' in direction_list:
                                vertical = 1
                            if 'a' in direction_list:
                                if 'd' in direction_list:
                                    horizontal = 2
                                else:
                                    horizontal = 1
                            elif 'd' in direction_list:
                                horizontal = 1
                            if vertical == 0:
                                # This case will be caught above; included for consistency
                                # if horizontal == 0:
                                #     print("Bf", end='')
                                if horizontal == 1:
                                    print("B-", end='')
                                elif horizontal == 2:
                                    print("B~", end='')
                            elif vertical == 1:
                                if horizontal == 0:
                                    print("Bl", end='')
                                elif horizontal == 1:
                                    print("Bt", end='')
                                elif horizontal == 2:
                                    print("B+", end='')
                            elif vertical == 2:
                                if horizontal == 0:
                                    print("Bz", end='')
                                elif horizontal == 1:
                                    print("Bx", end='')
                                elif horizontal == 2:
                                    print("B#", end='')
                        except KeyError:
                            print("Bf", end='')
                except KeyError:  # no block at coordinates, find pulses at coordinates
                    try:
                        if len(pulse_coordinates[(col, row)]) == 1:
                            print(f"{facing_dict[pulse_coordinates[(col, row)][0]]} ", end='')
                        else:
                            print("# ", end='')
                    except KeyError:
                        print("  ", end='')
            if col != max_x:
                print("|", end='')
        if row != min_y:
            print(f"\n{'-- ' * (max_x - min_x + 2)}")


def main_menu():
    global block_coordinates
    global pulse_list
    global pulse_coordinates
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
                        if type(this_block) == SInput:
                            this_block.state = not this_block.state
                        else:
                            print("Block is not an input block.")
                    else:
                        print("Coordinates already occupied by block.")
                except KeyError:  # no existing block found at coordinates, thus user wants to add a block
                    # Commands for adding new blocks
                    if user_input[0] == 'g':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            SGenerator(*user_coordinates, user_input[3])
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'r':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            SRedirector(*user_coordinates, user_input[3])
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'p':
                        SSplitter(*user_coordinates)
                    elif user_input[0] == 'l':
                        SBlocker(*user_coordinates)
                    elif user_input[0] == 'b':
                        SBridge(*user_coordinates)
                    elif user_input[0] == 'i':
                        if user_input[3] in ('w', 'a', 's', 'd'):
                            seq_temp = [int(i) for i in user_input[5:] if int(i) >= 0]
                            SInput(*user_coordinates, user_input[3], user_input[4], seq_temp)
                        else:
                            print("Invalid direction provided.")
                    elif user_input[0] == 'o':
                        SOutput(*user_coordinates)
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
                    print(block_coordinates.values())
                elif user_input[0] == 'save':
                    save_name = input("Enter file name (enter nothing to escape): ").strip()
                    if save_name != '':
                        for char in save_name:
                            if not char.isalnum() and char not in ('-', '_'):
                                print("Invalid filename. Allowed: a-z, A-Z, 0-9, '-', '_'")
                                break
                        else:
                            flag = False
                            if path.exists(file_path := f'IDEALaser Saves\\Simultaneous Saves\\{save_name}.txt'):
                                if input("File already exists. Overwrite? (y: yes, anything: back): ") == 'y':
                                    flag = True
                            else:
                                flag = True
                            if flag:
                                dump(block_coordinates, open(file_path, 'wb'))
                elif user_input[0] == 'load':
                    load_list = listdir('IDEALaser Saves\\Simultaneous Saves')
                    print()
                    for file in load_list:
                        print(file)
                    print()
                    filename = input("Enter file name (without .txt), or an invalid name to escape: ") + '.txt'
                    if filename in load_list:
                        try:
                            block_coordinates = load(open(f'IDEALaser Saves\\Simultaneous Saves\\{filename}', 'rb'))
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
'i': Input ({cost_dict['i']}), coordinates and direction and state (firing or not), optional numbers for oscillation,
    e.g. 'i 1 2 d t 1'
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


def run_solution():
    global block_coordinates
    global pulse_list
    global pulse_coordinates
    global cycle_count
    while True:
        option = input('''\n\n'r': Step
'help2': Show symbol meanings in solution
'show_laser': Show laser list (not usable in main menu)
'esc': Go back to main menu (clears lasers but does not clear blocks; use 'clear' later): ''')
        if option == 'r':
            # Step 1
            for block in block_coordinates.values():
                block.prestep()  # only Redirectors and Splitters
            # Step 2
            new_pulses = []
            new_pulse_coordinates = {}
            # Append to new lists pulses that are not colliding
            max_x, min_x, max_y, min_y = edge()
            for k, v in pulse_coordinates.items():
                try:  # if no error, means block at coordinate, check if bridge (and related criteria)
                    block = block_coordinates[k]
                    if type(block) == SBridge:
                        if ('w' in v) ^ ('s' in v):  # alternative for XOR is bool() != bool()
                            for pulse in pulse_list:
                                if pulse.coordinates == k and pulse.facing in ('w', 's'):
                                    new_pulses.append(pulse)
                                    break
                            try:
                                if 'w' in v:
                                    new_pulse_coordinates[k].append('w')
                                else:
                                    new_pulse_coordinates[k].append('s')
                            except KeyError:
                                if 'w' in v:
                                    new_pulse_coordinates[k] = ['w']
                                else:
                                    new_pulse_coordinates[k] = ['s']
                        if ('a' in v) ^ ('d' in v):
                            for pulse in pulse_list:
                                if pulse.coordinates == k and pulse.facing in ('a', 'd'):
                                    new_pulses.append(pulse)
                                    break
                            try:
                                if 'a' in v:
                                    new_pulse_coordinates[k].append('a')
                                else:
                                    new_pulse_coordinates[k].append('d')
                            except KeyError:
                                if 'a' in v:
                                    new_pulse_coordinates[k] = ['a']
                                else:
                                    new_pulse_coordinates[k] = ['d']
                except KeyError:  # no block found at coordinates, check if only one pulse and not out of board range
                    if len(v) == 1 and k[0] in range(min_x + 1, max_x) and k[1] in range(min_y + 1, max_y):
                        for pulse in pulse_list:
                            if pulse.coordinates == k:
                                new_pulses.append(pulse)
                                break
                        new_pulse_coordinates[k] = v
            pulse_list = new_pulses
            pulse_coordinates = new_pulse_coordinates
            # Step 3
            for pulse in pulse_list:
                pulse.step()
            # Step 4
            for block in block_coordinates.values():
                block.step()  # only redirectors, splitters, generators and inputs
            # Step 5
            for block in block_coordinates.values():
                block.poststep()  # only redirectors, splitters and outputs
            # Step 6
            tile_print()
        elif option == 'show_laser':
            print(pulse_list)
        elif option == 'help2':
            print('''
Each cell is represented by 2 characters. The first character is either a letter representing a block (key under
'help1', except the redirector, which is represented by 'WASD' showing its direction), or one of these: (^ > v < #), the
first 4 representing lasers and their direction, the last representing where 2+ lasers collided. The second character is
used by all blocks, and shows the different states they can be in.

Redirector/Splitter: 't' when hit by laser, 'f' when not.
Blocker/Output: 't' when hit by a single laser, '#' when hit by multiple lasers (output still considered to be in 'on'
state), 'f' when not hit by any laser.

Generator: '^ > v <', showing which direction it is facing.

Input: '^ > v < f', first 4 same as generator if it is active, last one indicates that it is inactive.

Bridge: '- l t', if lasers within it are non-colliding and in horizontal, vertical or both tubes respectively; '~ z #'
if lasers are colliding in horizontal, vertical or both tubes respectively; 'x' when the vertical is colliding and the
horizontal is non-colliding; '+' when the horizontal is colliding and the vertical is non-colliding; 'f' if no lasers
within.

''')
        elif option == 'esc':
            cycle_count = 0
            pulse_list.clear()
            pulse_coordinates.clear()
            for block in block_coordinates.values():
                if type(block) == SInput:
                    block.seq_index = 0
                    block.seq_count = 0
            return
        elif option == 'q':
            return 'q'
        else:
            print("Unrecognised command.")


print('''Welcome to IdeaLaser (simultaneous evaluation version).
Challenge: create logical gates using the tools provided.''')
while True:
    if main_menu() == 'q':
        break
    else:
        tile_print()
        if run_solution() == 'q':
            break
