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
# todo add bridge output? allow laser to pass through it instead of consuming. also OR logic of being true. cost 20?
#  because they can be used as splitter alternatives (reuse incoming laser)
from collections import deque
from copy import deepcopy
from math import lcm
from os import mkdir, path, listdir
from pickle import dump, load
from idealaser_globals import facing_dict, opposite_face_dict, cost_dict


def init_globals():
    # block_coordinates = {}
    # pulse_list = []
    # pulse_coordinates = {}
    # cycle_count = 0
    return {}, [], {}, 0  # must be assigned to variable names as above


def make_folders():
    try:
        mkdir('IDEALaser Saves')
    except FileExistsError:
        pass
    try:
        mkdir('IDEALaser Saves/Simultaneous Saves')
    except FileExistsError:
        pass
    try:
        mkdir('commands')
    except FileExistsError:
        pass


class SPulse:
    def __init__(self, x, y, direction):  # direction = wasd
        self.coordinates = x, y
        self.facing = direction
        pulse_list.append(self)
        if self.coordinates in pulse_coordinates:
            pulse_coordinates[self.coordinates].append(self.facing)
        else:
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
        if self.coordinates in pulse_coordinates:
            pulse_coordinates[self.coordinates].append(self.facing)
        else:
            pulse_coordinates[self.coordinates] = [self.facing]


class SBlock:
    def __init__(self, x, y):
        self.coordinates = x, y
        self.set_coordinates(x, y, block_coordinates, False)
    
    def set_coordinates(self, a, b, block_dict, offset_bool):
        new_coordinates = (self.coordinates[0]+a, self.coordinates[1]+b) if offset_bool else (a, b)
        if new_coordinates not in block_dict:
            if self.coordinates in block_dict and block_dict[self.coordinates] is self:
                del block_dict[self.coordinates]
            block_dict[new_coordinates] = self
            self.coordinates = new_coordinates
            return True
        else:
            return False
    
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
    def __init__(self, x, y, direction, level, input_id, sequence):
        super().__init__(x, y)
        self.facing = direction
        if level == 't':
            self.original_state = True
        else:
            self.original_state = False
        self.state = self.original_state
        self.cost = cost_dict['i']
        self.input_id = input_id
        self.seq = sequence
        self.seq_index = 0
        self.seq_count = 0
    
    def __repr__(self):
        return f'Input{*self.coordinates, self.facing, self.original_state, self.input_id, self.seq}'
    
    def update_outputs(self):
        for block in block_coordinates.values():
            if type(block) is SOutput and self.input_id in block.buffer:
                block.buffer[self.input_id].append(self.state)
        
    def step(self):
        self.update_outputs()
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
            if self.seq_count == self.seq[self.seq_index]:
                self.state = not self.state
                self.seq_count = 0
                self.seq_index += 1
                if self.seq_index == len(self.seq):
                    self.seq_index = 0


class SEmitter(SBlock):  # superclass of redirectors and splitters
    def __init__(self, x, y, facing=None, next_coordinates=None, fire_list=None):
        self.state = False
        self.facing = facing if facing is not None else tuple()
        self.next_coordinates = next_coordinates if next_coordinates is not None else tuple()
        self.fire_list = fire_list if fire_list is not None else []
        super().__init__(x, y)
    
    def set_coordinates(self, a, b, block_dict, offset_bool):
        if super().set_coordinates(a, b, block_dict, offset_bool):
            x_d = a if offset_bool else a - self.coordinates[0]
            y_d = b if offset_bool else b - self.coordinates[1]
            new_next_coordinates = []
            for next_coordinate in self.next_coordinates:
                new_next_coordinates.append((next_coordinate[0]+x_d, next_coordinate[1]+y_d))
            self.next_coordinates = tuple(new_next_coordinates)
            return True
        else:
            return False
    
    def prestep(self):
        self.fire_list = [False for _ in range(len(self.facing))]
        if self.state:
            for i in range(len(self.facing)):
                if self.next_coordinates[i] in block_coordinates and type(block_coordinates[self.next_coordinates[i]]) is not SBridge:
                    self.fire_list[i] = True
                else:
                    if self.next_coordinates[i] in pulse_coordinates:
                        if opposite_face_dict[self.facing[i]] not in pulse_coordinates[self.next_coordinates[i]]:
                            self.fire_list[i] = True
                    else:
                        self.fire_list[i] = True

    def step(self):
        for i in range(len(self.facing)):
            if self.fire_list[i]:
                SPulse(*self.next_coordinates[i], self.facing[i])

    def poststep(self):
        if self.coordinates in pulse_coordinates:
            self.state = True
        else:
            self.state = False


class SRedirector(SEmitter):
    def __init__(self, x, y, direction):
        if direction == 'w':
            temp_next_coordinates = ((x, y + 1),)
        elif direction == 'a':
            temp_next_coordinates = ((x - 1, y),)
        elif direction == 's':
            temp_next_coordinates = ((x, y - 1),)
        else:  # direction == 'd'
            temp_next_coordinates = ((x + 1, y),)
        super().__init__(x, y, facing=(direction,), next_coordinates=temp_next_coordinates, fire_list=[False])
        self.cost = cost_dict['r']
    
    def __repr__(self):
        return f'Redirector{*self.coordinates, self.facing}'


class SDualSplitter(SEmitter):
    def __init__(self, x, y, direction):
        if direction in ('w', 's', 'v'):
            temp_facing = 'w', 's'
            temp_next_coordinates = (x, y + 1), (x, y - 1)
        else:  # 'a' or 'd' or 'h'
            temp_facing = 'a', 'd'
            temp_next_coordinates = (x - 1, y), (x + 1, y)
        super().__init__(x, y, facing=temp_facing, next_coordinates=temp_next_coordinates, fire_list=[False, False])
        self.cost = cost_dict['d']
    
    def __repr__(self):
        return f'Dual-Splitter{*self.coordinates, self.facing}'


class SQuadSplitter(SEmitter):
    def __init__(self, x, y):
        super().__init__(x, y, facing=('w', 'a', 's', 'd'), next_coordinates=((x, y + 1), (x - 1, y), (x, y - 1), (x + 1, y)), fire_list=[False, False, False, False])
        self.cost = cost_dict['q']
    
    def __repr__(self):
        return f'Quad-Splitter{self.coordinates}'


class SOutput(SBlock):
    def __init__(self, x, y, buffer, table):
        super().__init__(x, y)
        self.state = False
        self.cost = cost_dict['o']
        self.buffer = buffer
        self.table = table
        self.valid = True
    
    def __repr__(self):
        return f'Output{*self.coordinates, tuple(self.buffer.keys()), self.table}'
    
    def update_valid(self):
        self.valid = False
        delaybool = False
        result_str = ''
        for k, v in self.buffer.items():
            for block in block_coordinates.values():
                if type(block) is SInput and block.input_id == k:
                    bufferpop = v.popleft()
                    if bufferpop:
                        result_str += '1'
                    elif bufferpop is not None:
                        result_str += '0'
                    else:  # None; happens for delay
                        delaybool = True
        if delaybool:
            self.valid = True  # outputs are always valid during the delay period
        elif result_str in self.table:
            if (self.state and '1' in self.table[result_str]) or (not self.state and '0' in self.table[result_str]):
                self.valid = True
    
    def poststep(self):
        if self.coordinates in pulse_coordinates:
            self.state = True
        else:
            self.state = False
        self.update_valid()


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


def create_block(user_input, user_coordinates):
    if user_input[0] == 'g':
        if user_input[3] in ('w', 'a', 's', 'd'):
            block = SGenerator(*user_coordinates, user_input[3])
        else:
            return "Invalid direction provided."
    elif user_input[0] == 'r':
        if user_input[3] in ('w', 'a', 's', 'd'):
            block = SRedirector(*user_coordinates, user_input[3])
        else:
            return "Invalid direction provided."
    elif user_input[0] == 'd':
        if user_input[3] in ('w', 'a', 's', 'd', 'h', 'v'):
            block = SDualSplitter(*user_coordinates, user_input[3])
        else:
            return "Invalid direction provided."
    elif user_input[0] == 'q':
        block = SQuadSplitter(*user_coordinates)
    elif user_input[0] == 'l':
        block = SBlocker(*user_coordinates)
    elif user_input[0] == 'b':
        block = SBridge(*user_coordinates)
    elif user_input[0] == 'i':
        if user_input[3] in ('w', 'a', 's', 'd'):
            id_temp = None
            seq_temp = []
            for optional in user_input[5:]:
                if optional[:3] == 'id=' and {',', ';'}.isdisjoint(optional[3:]):
                    for block in block_coordinates.values():
                        if type(block) is SInput and block.input_id == optional[3:]:
                            break
                    else:
                        id_temp = optional[3:]
                elif optional[:4] == 'seq=':
                    seq_temp = [int(i) for i in optional[4:].split(';') if int(i) > 0]
            block = SInput(*user_coordinates, user_input[3], user_input[4], id_temp, seq_temp)
        else:
            return "Invalid direction provided."
    elif user_input[0] == 'o':
        buffer_temp = {}
        table_temp = {}
        for optional in user_input[3:]:
            if optional[:6] == 'table=':
                table_rows = optional[6:].split(';')
                header = table_rows[0].split(',')
                for input_id in header[:-1]:
                    buffer_temp[input_id] = deque(None for _ in range(int(header[-1])))
                for table_row in table_rows[1:]:
                    table_temp[table_row[:len(buffer_temp)]] = table_row[len(buffer_temp):]
        block = SOutput(*user_coordinates, buffer_temp, table_temp)
    else:
        return "Unrecognised command."
    return f"Created {block}"


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


def count_valid():
    valid_count = 0
    total_outputs = 0
    for block in block_coordinates.values():
        if type(block) is SOutput:
            total_outputs += 1
            if block.valid:
                valid_count += 1
    return valid_count, total_outputs


def tile_print(running=True, steady_state=False, clean=(True, True), strict=(True, True), output_info=None):
    global pulse_list
    global pulse_coordinates
    global cycle_count
    cost_sum = 0
    for block in block_coordinates.values():
        cost_sum += block.cost
    print(f"\nCost: {cost_sum}")
    max_x, min_x, max_y, min_y = edge()
    area_int = (max_x - min_x - 1) * (max_y - min_y - 1)
    print(f"Area: {area_int}")
    if running:
        print(f"Cycles: {cycle_count}")
        cycle_count += 1
        print(f"Steady State: {steady_state}")
        print(f"Clean: {clean[0]} before Steady State{f", {clean[1]} after" if steady_state else ""}")
        print(f"Strictly valid: {strict[0]} before Steady State{f", {strict[1]} after" if steady_state else ""}")
        if output_info is None:
            valid_count, total_outputs = count_valid()
        else:
            valid_count, total_outputs = output_info
        print(f"{valid_count}/{total_outputs} valid outputs")
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
                if (col, row) in block_coordinates:
                    block = block_coordinates[(col, row)]
                    block_type = type(block)
                    if block_type is SGenerator:
                        print(f"G{facing_dict[block.facing]}", end='')
                    elif block_type is SInput:
                        if block.state:
                            print(f"I{facing_dict[block.facing]}", end='')
                        else:
                            print("If", end='')
                    elif block_type is SRedirector:
                        if block.state:
                            print(f"{block.facing[0].upper()}t", end='')
                        else:
                            print(f"{block.facing[0].upper()}f", end='')
                    elif block_type is SDualSplitter:
                        if block.state:
                            print(f"{'V' if block.facing == ('w', 's') else 'H'}t", end='')
                        else:
                            print(f"{'V' if block.facing == ('w', 's') else 'H'}f", end='')
                    elif block_type is SQuadSplitter:
                        if block.state:
                            print("Qt", end='')
                        else:
                            print("Qf", end='')
                    elif block_type is SOutput:
                        rep = 'O' if block.valid else 'X'
                        if block.state:
                            if len(pulse_coordinates[(col, row)]) == 1:
                                print(f"{rep}t", end='')
                            else:
                                print(f"{rep}#", end='')
                        else:
                            print(f"{rep}f", end='')
                    elif block_type is SBlocker:
                        if (col, row) in pulse_coordinates:
                            if len(pulse_coordinates[(col, row)]) == 1:
                                print("Lt", end='')
                            else:
                                print("L#", end='')
                        else:
                            print("Lf", end='')
                    elif block_type is SBridge:
                        if (col, row) in pulse_coordinates:
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
                                # Below case will be caught when (col, row) in pulse_coordinates == False, but it is
                                # included for consistency
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
                        else:
                            print("Bf", end='')
                else:  # no block at coordinates, find pulses at coordinates
                    if (col, row) in pulse_coordinates:
                        if len(pulse_coordinates[(col, row)]) == 1:
                            print(f"{facing_dict[pulse_coordinates[(col, row)][0]]} ", end='')
                        else:
                            print("# ", end='')
                    else:
                        print("  ", end='')
            if col != max_x:
                print("|", end='')
        if row != min_y:
            print(f"\n{'-- ' * (max_x - min_x + 2)}")
    print()


def main_menu():
    global block_coordinates
    global pulse_list
    global pulse_coordinates
    while True:
        if block_coordinates:
            tile_print(running=False)
        try:
            user_input = input('''\n'run': run solution (does not begin stepping, just displays initial state)
'help': full list of commands
Enter a command: ''').split()
            try:
                user_coordinates = int(user_input[1]), int(user_input[2])
                if user_input[0] == 'shiftall':
                    new_block_coordinates = {}
                    for block in block_coordinates.values():
                        block.set_coordinates(int(user_input[1]), int(user_input[2]), new_block_coordinates, True)
                    block_coordinates = new_block_coordinates
                elif user_coordinates in block_coordinates:  # Commands for existing blocks
                    this_block = block_coordinates[user_coordinates]
                    if user_input[0] == 'del':
                        del block_coordinates[user_coordinates]
                    elif user_input[0] == 'shift':
                        if not this_block.set_coordinates(int(user_input[3]), int(user_input[4]), block_coordinates, True):
                            print("Coordinates already occupied by block.")
                    elif user_input[0] == 'toggle':
                        if type(this_block) is SInput:
                            this_block.original_state = not this_block.original_state
                            this_block.state = this_block.original_state
                        else:
                            print("Block is not an input block.")
                    else:
                        print("Coordinates already occupied by block.")
                else:  # no existing block found at coordinates, thus user wants to add a block
                    print(create_block(user_input, user_coordinates))
            except IndexError:
                # Commands not concerning individual blocks
                if user_input[0] == 'run':
                    if block_coordinates:  # if there exists at least 1 block
                        for block in block_coordinates.values():
                            if type(block) is SInput:
                                block.update_outputs()
                        for block in block_coordinates.values():
                            if type(block) is SOutput:
                                block.update_valid()
                        return
                    else:
                        print("Must put down at least 1 block before running.")
                elif user_input[0] == 'clear':
                    block_coordinates.clear()
                elif user_input[0] == 'blocks':
                    print(f"{len(block_coordinates)} blocks:", *block_coordinates.values())
                elif user_input[0] == 'save':
                    make_folders()
                    save_name = input("Enter file name (enter nothing to escape): ").strip()
                    if save_name != '':
                        for char in save_name:
                            if not char.isalnum() and char not in ('-', '_', ' '):
                                print("Invalid filename. Allowed: a-z, A-Z, 0-9, '-', '_', space")
                                break
                        else:
                            flag = False
                            if path.exists(file_path := f'IDEALaser Saves\\Simultaneous Saves\\{save_name}.pickle'):
                                if input("File already exists. Overwrite? (y: yes, anything: back): ") == 'y':
                                    flag = True
                            else:
                                flag = True
                            if flag:
                                with open(file_path, 'wb') as f:
                                    dump(block_coordinates, f)
                elif user_input[0] == 'load':
                    make_folders()
                    load_list = listdir('IDEALaser Saves\\Simultaneous Saves')
                    print()
                    for file in load_list:
                        print(file)
                    print()
                    filename = input("Enter file name (without .pickle), or an invalid name to escape: ") + '.pickle'
                    if filename in load_list:
                        with open(f'IDEALaser Saves\\Simultaneous Saves\\{filename}', 'rb') as f:
                            block_coordinates = load(f)
                elif user_input[0] == 'loadcom':
                    make_folders()
                    command_list = listdir('commands')
                    print()
                    for file in command_list:
                        print(file)
                    print()
                    filename = input("Enter file name (without .txt), or an invalid name to escape: ") + '.txt'
                    if filename in command_list:
                        with open(f'commands\\{filename}', 'rb') as f:
                            for line in f.readlines():
                                user_input = line.decode("utf-8").split()
                                for i in range(len(user_input)):
                                    if user_input[i][0] == '#':
                                        user_input = user_input[:i]
                                        break
                                if user_input:
                                    user_coordinates = int(user_input[1]), int(user_input[2])
                                    if user_coordinates not in block_coordinates:
                                        print(create_block(user_input, user_coordinates))
                                    else:
                                        print("Coordinates already occupied by block.")
                elif user_input[0] == 'quit':
                    return 'quit'
                elif user_input[0] == 'help':
                    print(f'''
Block commands. Name (cost): BlockID, requirements (assume x=1, y=2, direction(wasd)=right, state=true)
Input ({cost_dict['i']}): 'i', coordinates, direction, state (firing or not).
    Optional (any order): ID (must be unique, and must not contain , or ;), oscillation sequence separated by ; (numbers
    must >0 int; if there are an odd number of numbers, state will alternate)
    e.g. 'i 1 2 d t id=Alpha seq=1;2;3' (fire 1, don't fire 2, fire 3, don't fire 1, fire 2, don't fire 3, repeat)
Output ({cost_dict['o']}): 'o', coordinates.
    Optional: 'table' with rows separated by ;
        Header: separated by ',', containing the IDs of all linked inputs, then delay (>=0) in order for the output's
        validity to be based on the state of inputs that number of cycles ago
        Body: first characters matching the state of the inputs, then remaining characters showing valid outputs.
    e.g. 'o 1 2 table=Alpha,Beta,4;0001;011;101;111' for an output based on Alpha and Beta 4 cycles ago; if both false,
    output is allowed to be either 0 or 1; otherwise, output must be 1. Missing scenarios mean it's always invalid.
Blocker ({cost_dict['l']}): 'l', coordinates, e.g. 'l 1 2'
Redirector ({cost_dict['r']}): 'r', coordinates, direction, e.g. 'r 1 2 d'
Dual-Splitter ({cost_dict['d']}): 'd', coordinates, direction, e.g. 'd 1 2 d' (also accepts 'h' or 'v' for direction)
Quad-Splitter ({cost_dict['q']}): 'q', coordinates, e.g. 'q 1 2'
Generator ({cost_dict['g']}): 'g', coordinates, direction, e.g. 'g 1 2 d'
Bridge ({cost_dict['b']}): 'b', coordinates, e.g. 'b 1 2'

Other Commands:
'symbols': Symbol meanings
'toggle x y': Change the state of an existing input at coordinates (x, y) from on to off, or from off to on
'shift x y a b': Shift block at coordinates (x, y) to (x+a, y+b)
'shiftall a b': Shift all blocks from coordinates (x, y) to (x+a, y+b)
'del x y': Delete block at coordinates (x, y)
'clear': Clear all blocks
'blocks': Show block list
'save': Save current setup (only saves blocks, does not save lasers)
'load': Load block setup from a save (unsaved setups will be lost)
'loadcom': Add blocks from a .txt file with block commands, separated by newlines. Will not overwrite existing blocks
'quit': Quit (usable when running solution) (unsaved setups will be lost)''')
                elif user_input[0] == 'symbols':
                    print('''
Each cell is represented by 2 characters. The first character is either a letter representing a block (key under
'help', except the redirector, dual-splitter and output, which are represented by 'WASD', 'HV' and 'OX' respectively
showing their directions/validity), or one of these: (^ > v < #), the first 4 representing lasers and their direction,
the last representing where 2+ lasers collided. The second character is used by all blocks, and shows the different
states they can be in based on whether there are lasers within them.

Redirector/Splitter: 't' when hit by laser, 'f' when not.
Blocker/Output: 't' when hit by a single laser, '#' when hit by multiple lasers (output still considered to be in 'on'
state), 'f' when not hit by any laser.

Generator: '^ > v <', showing which direction it is facing.

Input: '^ > v < f', first 4 same as generator if it is active, last one indicates that it is inactive.

Bridge: '- l t', if lasers within it are non-colliding and in horizontal, vertical or both tubes respectively; '~ z #'
if lasers are colliding in horizontal, vertical or both tubes respectively; 'x' when the vertical is colliding and the
horizontal is non-colliding; '+' when the horizontal is colliding and the vertical is non-colliding; 'f' if no lasers
within.''')
                else:
                    print("Unrecognised/failed command.")
        except (ValueError, IndexError):
            print("\nPlease enter valid values.")


def run_solution():
    global block_coordinates
    global pulse_list
    global pulse_coordinates
    global cycle_count
    input_periods = []
    for block in block_coordinates.values():
        if type(block) is SInput:
            if block.seq:  # empty means period 1 thus no need to append
                input_periods.append(sum(block.seq) * (1 if len(block.seq) % 2 == 0 else 2))
    input_lcm = lcm(*input_periods)
    past_pulses_deque = deque(None for _ in range(input_lcm * 2))
    clean_before = True
    clean_after = True
    strict_before = True
    strict_after = True
    while True:
        option = input('''\n'r': Step
'lasers': Show laser list (not usable in main menu)
'esc': Go back to main menu (clears lasers but does not clear blocks): ''')
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
                if k in block_coordinates:  # if no error, means block at coordinate, check if bridge (and related criteria)
                    block = block_coordinates[k]
                    if type(block) is SBridge:
                        if ('w' in v) != ('s' in v):
                            for pulse in pulse_list:
                                if pulse.coordinates == k and pulse.facing in ('w', 's'):
                                    new_pulses.append(pulse)
                                    break
                            if 'w' in v:
                                try:
                                    new_pulse_coordinates[k].append('w')
                                except KeyError:
                                    new_pulse_coordinates[k] = ['w']
                            else:
                                try:
                                    new_pulse_coordinates[k].append('s')
                                except KeyError:
                                    new_pulse_coordinates[k] = ['s']
                        if ('a' in v) != ('d' in v):
                            for pulse in pulse_list:
                                if pulse.coordinates == k and pulse.facing in ('a', 'd'):
                                    new_pulses.append(pulse)
                                    break
                            if 'a' in v:
                                try:
                                    new_pulse_coordinates[k].append('a')
                                except KeyError:
                                    new_pulse_coordinates[k] = ['a']
                            else:
                                try:
                                    new_pulse_coordinates[k].append('d')
                                except KeyError:
                                    new_pulse_coordinates[k] = ['d']
                else:  # no block found at coordinates, check if only one pulse and not out of board range
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
            past_pulses_deque.append(deepcopy(pulse_coordinates))
            past_pulses_deque.popleft()
            earlier_pulses = [past_pulses_deque[i] for i in range(input_lcm)]
            later_pulses = [past_pulses_deque[i] for i in range(input_lcm, input_lcm * 2)]
            steady_state = earlier_pulses == later_pulses
            for pulse_x, pulse_y in pulse_coordinates:
                if pulse_x <= min_x or pulse_x >= max_x or pulse_y <= min_y or pulse_y >= max_y:
                    if steady_state:
                        clean_after = False
                    else:
                        clean_before = False
                    break
            valid_count, total_outputs = count_valid()
            if valid_count < total_outputs:
                if steady_state:
                    strict_after = False
                else:
                    strict_before = False
            tile_print(steady_state=steady_state, clean=(clean_before, clean_after), strict=(strict_before, strict_after), output_info=(valid_count, total_outputs))
        elif option == 'lasers':
            print(pulse_list)
        elif option == 'esc':
            cycle_count = 0
            pulse_list.clear()
            pulse_coordinates.clear()
            for block in block_coordinates.values():
                if type(block) is SInput:
                    block.seq_index = 0
                    block.seq_count = 0
                    block.state = block.original_state
                else:
                    if hasattr(block, 'state'):
                        block.state = False
            return
        elif option == 'quit':
            return 'quit'
        else:
            print("Unrecognised command.")


if __name__ == '__main__':
    block_coordinates, pulse_list, pulse_coordinates, cycle_count = init_globals()
    print('''Welcome to IdeaLaser (simultaneous evaluation version).
Challenge: create logical gates using the tools provided.''')
    while True:
        if main_menu() == 'quit':
            break
        else:
            valid, total = count_valid()
            tile_print(strict=(valid == total, True), output_info=(valid, total))
            if run_solution() == 'quit':
                break
