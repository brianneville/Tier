# interpreter for the Tier language
# All in one file to make things easier when running (no need to have multiple modules)
# Language and interpreter created by Brian Neville 21/12/19
import os
import sys
import argparse
import fnmatch
from collections import defaultdict
import re
from random import randint
from time import sleep


def get_input_type(arg):
    if len(arg) < 2:
        # ts has not been wrapped with brackets to specify type
        return str(arg)
    if arg[-1:] is "'" and arg[:1] is "'":
        v = arg[1:-1]
        # ts has been specified as an int or float type
        return float(v) if re.search('[.]', v) else int(v)
    # ts type unspecified, assume string
    return str(arg)

    # raise Exception("Please specify type (number or string) using the ' or \" characters")


def get_input() -> list:
    global timestep, show_info, visual_dbg, ts
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--directory', required=False, type=str, action='store', default=os.curdir,
                        help='directory containing .tier files for program. default to curdir')
    parser.add_argument('-t', '--timestep', required=False, type=float, action='store', default=0,
                        help='the duration of each timestep in the control loop')
    parser.add_argument('-i', '--info', required=False, action='store_true', default=False,
                        help='show debug information from the program')
    parser.add_argument('-v', '--visual', required=False, action='store_true', default=False,
                        help='visual tool to aid debugging')
    parser.add_argument('-ts', '--set_ts', required=False, type=get_input_type, action='store', default=0,
                        help='set the starting value of ts. enclose in \' characters to input numbers. e.g. \'123\'')

    args = parser.parse_args()
    ts = args.set_ts
    visual_dbg = args.visual
    timestep = args.timestep
    show_info = args.info
    usedir = args.directory.replace("\\", "/")

    if usedir[-1:] is not '/':  # formatting
        usedir += '/'

    files = []
    entry_point_exists = False
    print(f'Building program from directory:{usedir}')
    for f in os.listdir(usedir):
        if fnmatch.fnmatch(f, '*.tier'):
            files.append(f'{usedir + f}')
            if f == '0.tier':
                entry_point_exists = True
    if not entry_point_exists:
        raise Exception('Please add a 0.tier file to this dir as an entry point')
    return files


def store_chars(files) -> (defaultdict, list, int, int, dict):
    global visual_dbg
    char_dict = defaultdict(lambda: None)
    tier_list = []
    fmax_width, fmax_height = 0, 0  # used to wrap pc around edge of file

    lines_dict = None
    if visual_dbg:
        lines_dict = {}

    for file in files:
        with open(file, 'r') as f:
            fname = file[file.rfind('/') + 1:file.rfind('.')]
            tier_list.append(fname)
            lines = f.readlines()
            if visual_dbg:
                # if curses module present set up all lines
                lines_dict[fname] = lines
            for row_indx, line in enumerate(lines):
                if row_indx > fmax_height:
                    fmax_height = row_indx

                for col_indx, char in enumerate(line):
                    if col_indx > fmax_width:
                        fmax_width = col_indx
                    if char == ';' and col_indx == 0 or char in ('\n', '\r'):
                        break  # break if comment, ignore endlines
                    # required to store ' ' chars, as they may be inside directional strings
                    char_dict[f'{col_indx}-{row_indx}-{fname}'] = char

    return char_dict, tier_list, fmax_height, fmax_width, lines_dict


def create_stacks(tier_list) -> (dict, defaultdict):
    # stack and stack pointer for all tiers
    sp_dict, stacks = {}, {}
    # ts = 0   # should not be arrays as tiers can have arbitrary, non-sequential names
    for t in tier_list:
        sp_dict[f'{t}'] = 0
        # ts_dict[f'{t}'] = 0
        stacks[f'{t}'] = defaultdict(lambda: 0)

    return sp_dict, stacks


def get_sp_stack() -> (int, defaultdict):
    global pc, gsp_dict, gstacks_dict
    return gsp_dict[f"{pc[2]}"], gstacks_dict[f"{pc[2]}"]  # return sp, stack for current tier


def get_stack_top(sp, stack) -> int:
    return 0 if not len(stack) else int(max(int(max(stack.keys())), sp))


def view_debug():
    global mode, pc, ts, char, velocity
    sp, stack = get_sp_stack()
    print(f"char={char}\npc={pc}, vel={velocity}\nts={ts}\nmode={mode}\nsp={sp}\nstack={stack}\n---")


def change_vel(arg):
    global velocity
    velocity = arg


def jump():
    global mode, jump_address, pc
    if not mode:
        mode = 3
    elif mode is 3:
        mode = 0
        str_ver = ''.join(jump_address)  # string version allows to jump to -1.tier
        col_correction = velocity[0] * (len(str_ver) + 1)  # add 1 for the @ sign position
        row_correction = velocity[1] * (len(str_ver) + 1)
        pc[0] -= col_correction
        pc[1] -= row_correction
        pc[2] = int(str_ver)
        jump_address = []


def change_sp(arg):
    global pc, gsp_dict
    # increment/decrement stack pointer for tier
    gsp_dict[f"{pc[2]}"] += arg


def push_ts():
    global ts
    sp, stack = get_sp_stack()
    stack_top = get_stack_top(sp, stack)
    # there are no items in stack. ts may still be non-zero as ts is available to all stacks, sp is 0, item at sp is 0
    stack[stack_top+1] = ts
    # reset ts back to 0, replacing the 0 that was just evicted
    ts = 0


def copy_ts():
    global ts
    sp, stack = get_sp_stack()
    ts = stack[sp]


def copy_sp():
    global ts
    sp, stack = get_sp_stack()
    stack[sp] = ts


def end_prog():
    global prog_over
    prog_over = True


def print_sp():
    # get coords from pc, sp from dict, print stack at sp
    sp, stack = get_sp_stack()
    print(str(stack[sp]).replace('\\n', '\n'), end='')


def input_sp():
    global visual_dbg, VDB, window, lines_dict
    sp, stack = get_sp_stack()
    if visual_dbg:
        VDB.destroy_window()
    inp = input()
    if visual_dbg:
        window = VDB.create_window()
    stack[sp] = get_input_type(inp)


def stack_operate(arg):
    global ts
    # use python exec on operation

    sp, stack = get_sp_stack()
    v_sp = stack[sp]
    v_below_sp = stack[sp-1]
    local_dict_hack = {}
    # this is a way to get locals() to work in exec(). see https://bugs.python.org/issue4831
    exec(f"res = {v_sp} {arg} {v_below_sp}", local_dict_hack)
    res = local_dict_hack['res']

    # push back on top of stack
    stack_top = get_stack_top(sp, stack)
    stack[stack_top+1] = res

    # set ts to zero as zero has been evicted
    ts = 0


def check_zero():
    global pc, velocity
    sp, stack = get_sp_stack()
    if stack[sp] == 0:
        # skip next instruction on current path
        pc[0] += velocity[0]
        pc[1] += velocity[1]


def boolean_not():
    global ts
    sp, stack = get_sp_stack()
    v = stack[sp]
    ts = v
    stack[sp] = 1 if not v else 0


def compare():
    global pc, velocity
    sp, stack = get_sp_stack()
    if stack[sp] > stack[sp-1]:
        # skip next instruction on current path
        pc[0] += velocity[0]
        pc[1] += velocity[1]


def bin_random():
    global ts
    sp, stack = get_sp_stack()
    # set ts to item about to be evicted
    ts = stack[sp]
    stack[sp] = randint(0, 1)


def pop_stack():
    global ts
    # set ts
    sp, stack = get_sp_stack()
    ts = stack[sp]

    # shift stack down to overwrite
    top = get_stack_top(sp, stack)
    if sp == top:
        # if item popped is at top of stack, then just remove from dict
        stack.pop(sp)
        return
    # else if sp is somewhere in the middle of the stack,
    # move all elements with higher indexes down one, and then
    for i in range(sp, top):
        stack[i] = stack[i+1]

    # now remove top element. new top can be found at top - 1, if top-1 exists
    stack.pop(top)


def store_num_sp():
    global mode, num_to_store, ts
    if not mode:
        mode = 1
    elif mode is 1:
        mode = 0
        sp, stack = get_sp_stack()
        # stack_top = get_stack_top(sp, stack)
        ts = stack[sp]  # store evicted

        str_version = r''.join(num_to_store)
        num_version = int(str_version) if str_version.rfind('.') is -1 else float(str_version)

        stack[sp] = num_version  # join into string
        num_to_store = []


def store_str_sp():
    global mode, string_to_store, ts
    # again, this must be done with checks as we need "'" to be valid (result in storing string ' at sp)
    if not mode:
        mode = 2
    elif mode is 2:
        mode = 0
        # replace on top of stack
        sp, stack = get_sp_stack()
        # stack_top = get_stack_top(sp, stack)
        ts = stack[sp]  # store evicted
        stack[sp] = r''.join(string_to_store)  # join into string
        string_to_store = []


def advance_pc():
    global pc, velocity, show_info, window, lines_dict, VDB

    if show_info:
        view_debug()
    if visual_dbg:
        VDB.step_through(window, lines_dict)

    pc[0] += velocity[0]
    pc[1] += velocity[1]
    # print(f"updated pc to {pc}")

    if pc[0] > max_width:
        pc[0] = 0
    elif pc[0] < 0:
        pc[0] = max_width
    if pc[1] > max_height:
        pc[1] = 0
    elif pc[1] < 0:
        pc[1] = max_height


def get_index():
    # place the actual value of sp in ts
    global ts, pc, gsp_dict
    ts = gsp_dict[f"{pc[2]}"]


def pop_highest():
    global ts
    sp, stack = get_sp_stack()
    # pop the highest item in the stack into ts
    stack_top = get_stack_top(sp, stack)
    ts = stack[stack_top]
    stack.pop(stack_top)


if __name__ == '__main__':

    # ------------------------------------------CURSES VISUAL DEBUGGING-----------------------------------------------
    try:
        import curses  # this interpreter was made with windows-curses version 2.2
    except ModuleNotFoundError:
        print("The module 'curses' has not been found.\n"
              "This module is required for the visual debugger")

    if 'curses' in sys.modules:
        curses_found = True


        class Debugger:

            def __init__(self):
                global ts
                self.prev_vel = [1, 0]
                self.done_startup = False
                self.prev_sp = 0
                self.prev_ts = ts
                self.prev_stacklen = 0
                self.prev_tierlen = 0
                self.prev_tier = 0
                self.prev_mode = 0

            def create_window(self) -> object:
                global timestep
                win = curses.initscr()
                curses.noecho()
                curses.curs_set(0)
                curses.cbreak()     # added to handle destroy()-ing and re-create()-ing the window for input_sp
                curses.start_color()
                win.nodelay(not not timestep)
                # if timestep is 0 then rely on getch to advance debugger. else use timestep to move onwards
                curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED)  # mode = 0, standard
                curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_GREEN)  # mode = 1, reading number
                curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # mode = 2, reading string
                curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN)  # mode = 3, jumping

                curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_MAGENTA)  # debug
                curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_BLACK)  # debug
                return win

            def destroy_window(self):
                curses.nocbreak()
                curses.echo()
                curses.endwin()

            def step_through(self, cwindow, clines_dict):
                global pc, prog_over, mode, ts
                sp, stack = get_sp_stack()

                # use while window.getch() to step through
                # window.bkgd(' ', curses.color_pair(1) | curses.A_BOLD)
                if self.prev_tier != pc[2]:
                    self.done_startup = 0
                    cwindow.clear()
                for indx, k in enumerate(clines_dict[f'{pc[2]}']):
                    if indx == pc[1]:
                        col_start = pc[0]
                        cwindow.addstr(indx, 0, k[:col_start])
                        cwindow.addstr(indx, col_start, k[col_start:col_start + 1], curses.color_pair(mode + 1))
                        cwindow.addstr(indx, col_start + 1, k[col_start + 1:])
                    else:
                        cwindow.addstr(indx, 0, k)

                if (self.prev_vel[0] is not velocity[0] and self.prev_vel[1] is not velocity[1]) \
                        or not self.done_startup:
                    cwindow.addstr(max_height + 3, 0, f'vel=     ')
                    cwindow.addstr(max_height + 3, 0, f'vel={velocity[0]},{velocity[1]}')
                    self.prev_vel = velocity

                if self.prev_mode is not mode or not self.done_startup:  # sp may exceed 255, regularly exceeds -5
                    cwindow.addstr(max_height + 4, 0, f"mode= ")
                    cwindow.addstr(max_height + 4, 0, f'mode={mode}')
                    self.prev_sp = sp

                if self.prev_sp != sp or not self.done_startup:  # sp may exceed 255, regularly exceeds -5
                    cwindow.addstr(max_height + 5, 0, f"sp={re.sub('[^ ]',' ', str(self.prev_sp))}")
                    cwindow.addstr(max_height + 5, 0, f'sp={sp}')
                    self.prev_sp = sp

                if self.prev_ts != ts or not self.done_startup:
                    cwindow.addstr(max_height + 6, 0, f"ts={re.sub('[^ ]',' ', str(self.prev_ts))}")
                    cwindow.addstr(max_height + 6, 0, f'ts={ts}')
                    self.prev_ts = ts

                cwindow.addstr(max_height + 8, 0, "Stack view")

                strstack = []
                for k, v in sorted(stack.items(), key=lambda x: int(x[0])):
                    strstack.append(f"[{k}:{str(type(v)).replace('class ','')}: {v}]")
                strstack = ''.join(strstack)
                cwindow.addstr(max_height + 9, 0, f"Stack {''.ljust(len(str(self.prev_tier))+20)}"
                                                  f"{''.ljust(self.prev_stacklen)}")
                cwindow.addstr(max_height + 9, 0, f"Stack {pc[2]}.tier={''.join(strstack)}", curses.color_pair(6))
                self.prev_stacklen = len(strstack)
                self.prev_tier = pc[2]

                if not self.done_startup:
                    cwindow.addstr(max_height + 2, 0,
                                   "DEBUG - press enter to continue, press other keys to exit", curses.color_pair(5))
                    self.done_startup = True

                cwindow.refresh()
                c = cwindow.getch()  # if timestep is 0, then -1 will be returned if no keys are pressed
                if c not in (10, -1):
                    prog_over = True

                if timestep and c is 10:
                    cwindow.nodelay(0)
                    cwindow.getch()  # block until user enters another character
                    cwindow.nodelay(1)

    else:
        curses_found = False
        window = None


        class Debugger:
            pass

    # -----------------------------------------------------------------------------------------------------------------

    show_info = False
    timestep = 0
    visual_dbg = False

    ts = 0  # temp storage, common to all stacks. holds the most recent stack operation result

    # take in command line arg of directory with the 0.tier, 1.tier, 2.tier etc files
    gfiles = get_input()

    # handle visual debugging
    visual_dbg &= curses_found
    window = None
    VDB = None

    if visual_dbg:
        VDB = Debugger()
        window = VDB.create_window()
        # timestep = 0

    # open all the files and add all characters to dictionaries where key:val  = "row-col-dim":'char'
    # ignore all lines which have a ; character in the column 0
    # (space inefficient, but allows for O(1) lookup time for characters at each timestep)
    gchar_dict, gtier_list, max_height, max_width, lines_dict = store_chars(gfiles)
    # create empty stacks and stack pointers for every layer
    gsp_dict, gstacks_dict = create_stacks(gtier_list)

    # create velocity and pc
    velocity = [1, 0]  # eastwards     0th index = col velocity, 1st index = row velocity
    pc = [0, 0, 0]  # top left corner, tier 0

    # ts set by user or defaults to zero
    # timestep logic:
    # evaluate current operation (use decorator parsing)
    # advance according to velocity
    parse_options = \
        defaultdict(lambda: (lambda: None, None),  # lambda since func needs callable object
                    {  # char : (function, args)
                        '^': (change_vel, [0, -1]),
                        '_': (change_vel, [0, 1]),
                        '>': (change_vel, [1, 0]),
                        '<': (change_vel, [-1, 0]),
                        '@': (jump, None),
                        '[': (change_sp, 1),  # sp += 1
                        ']': (change_sp, -1),  # sp -= 1,
                        '~': (push_ts, None),
                        '(': (copy_ts, None),  # ts = stack[sp]
                        ')': (copy_sp, None),  # stack[sp] = ts
                        '#': (end_prog, None),
                        '{': (print_sp, None),
                        '}': (input_sp, None),
                        '+': (stack_operate, '+'),  # operator for exec
                        '-': (stack_operate, '-'),
                        '*': (stack_operate, '*'),
                        '/': (stack_operate, '/'),
                        '%': (stack_operate, '%'),
                        '&': (stack_operate, '&'),
                        '|': (stack_operate, '|'),
                        '\\': (stack_operate, '//'),
                        '?': (compare, None),
                        '=': (check_zero, None),
                        '!': (boolean_not, None),
                        '`': (bin_random, None),
                        ':': (pop_stack, None),
                        '$': (pop_highest, None),
                        '\'': (store_num_sp, None),
                        "\"": (store_str_sp, None),
                        ',': (get_index, None)
                    })   

    prog_over = False
    mode = 0  # 0 = simple traversal, 1 = reading numbers, 2 = reading strings, 3 = jumping
    string_to_store = []
    num_to_store = []  # build as str to handle '.' (vs num*10 + new)
    jump_address = []
    changing_mode = False

    while not prog_over:
        if timestep is not 0:
            sleep(timestep)
        # get current char
        char = gchar_dict[f'{pc[0]}-{pc[1]}-{pc[2]}']

        # ignore specific characters if mode = 0
        find = re.search('[a-zA-Z0-9.;£ ]', f'{char}')  # non-command chars

        if mode is 1:
            # reading number
            if char is "'":
                changing_mode = True
            else:
                num_to_store.append(char)
        if mode is 2:
            # reading string
            if char is '\"':
                changing_mode = True
            else:
                string_to_store.append(char)

        if mode is 3:
            # jumping

            # this or statement enables jumping to negative tiers, should it be allowed?
            if (char not in parse_options.keys() or char is '-') and (char not in (None, ' ', '.')):
                jump_address.append(char)
            else:
                jump()
                continue

        if char is None:
            advance_pc()
            continue  # blank space

        if not mode or changing_mode:
            changing_mode = False
            if not find:
                func, arg = parse_options[f'{char}']
                if func is None:
                    raise Exception(f"unexpected character encountered. unknown purpose. "
                                    f"\nCharacter: {char}.\nFile:{pc[2]}.tier\nLine:{pc[1]}\nCol:{pc[0]}")
                if arg is None:
                    output = func()
                else:
                    output = func(arg)

        # add velocity and continue
        advance_pc()

    if visual_dbg:
        VDB.destroy_window()
