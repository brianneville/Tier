# Tier
A three-dimensional, stack-based, turing complete programming language.

This language is inspired by the 'Befunge' programming language, in the sense that it is stack based and enables unconventional program flow. However unlike Befunge, Tier allows programs to be developed in three dimensions, by stacking tiers of executable files in the same 3D space as each other. Program flow can be directed up and down through these tiers (this behaviour allows the user to write functions with entry and exit points from certain tiers). 

Example functions:  
[Boolean XOR](../master/demos/boolXOR_func)  
[Power function](../master/demos/powxy_func)  

Cool example programs:  
[Using the power function to compute e](../master/demos/e_approx)  
[Checking if a number is prime](../master/demos/isPrime)

See **[more examples](..master/demos)** in the demos folder!

## Interpreter:
The Tier.py file can be used to interpret and develop programs in Tier.  
Tier programs should be built using .tier files, which should be grouped together in a single directory. Tiers need to be referenced by their name within the program (e.g. jump to 1.tier with the @1).
Every directory should have a 0.tier file which serves as an entry point for the program.  

#### Args/Flags:
```
  -d/--directory  :Arg to specify the program directory. Defaults to the current directory. e.g. c:/path/to/program
  -t/--timestep   :Arg to specify the duration of each timestep in the main loop. duration in seconds
  -ts/--set_ts    :Arg used to specify starting value of ts. Default is 0.
  -i/--info       :Flag used to print out debug info at each timestep
  -v/--visual     :Flag to enable visual debugger tool
```

#### Visual Debugger:
The -v flag can be used to enable a visual debugging tool (requires the 'curses' module). This tool can be used to help write programs in Tier, by allowing the user to step through the program and see the velocity, ts, current instruction, current mode, stack pointer and stack for that tier. The debugger will temporarily exit to the console if needed for input.  
While the visual debugger is running, pressing any key other than ENTER will cause the program to exit.  

As seen here, the user can press the ENTER key to step through the program
![](../master/Visual%20Debugger%20gifs/step_through.gif)

The user can combine this with the -t flag to automatically watch the programs execution (as seen here, pressing ENTER will pause the program)
![](../master/Visual%20Debugger%20gifs/auto.gif)


## Language specification:
__Each program has:__  
**`pc`** = program counter. This is used to step through the program. Instructions at the current program counter position are executed. pc is updated with current velocity every timestep. Implemented as `[<col_pos>, <row_pos>, <tier>]`  
**`ts`** = temporary storage. This is a storage element which is common and accessible to all tiers, and can only hold one value at a time. Values which are evicted from stacks (e.g. by popping or inserting another value at current position), are evicted into ts, replacing its previous value.  
**`vel`**= velocity. This is the current velocity of pc. Implemented as `[<col vel>, <row_vel>]`  

__Each tier has:__  
**`stack`** = the tier's own stack, which can have indices extending from -∞ to +∞, with every index having a value of 0 by default.  
**`sp`** = stack pointer. Used to traverse the stack. This stack pointer does not track the top of the stack, and instead needs to be incremented and decremented by the user. The stack pointer is used to perform operations on the stack.  

### Instructions:

#### Controlling pc
|instruction| operation |
|---|:----------------|
| > | velocity right |
| < | velocity left  |
| ^ | velocity up    |
| _ | velocity down  |
| @ | jump to specified tier|  
| # | end program (exit) |


The address of a jump operation is specified by the following numeric characters. e.g. `@413` will jump pc to the corresponding position of the @ sign in tier 413

#### Controlling sp
In each tier, sp is initialised with an integer value of 0, and can be modified as such:

|instruction| operation|
|---|:----------------|
| \[ | increment sp |
| \] | decrement sp |

#### Handling ts
The temporary storage location 'ts' for the program is initialised with an integer value of 0, and can be modified in a number of ways.
* ts is used to store any values which are evicted from the stack. Any time a new value is inserted into the stack, the previous value at that index is evicted. (Remember all indices are occupied by an int 0 by default).
* Values can be directly stored into ts by instruction.

The following instructions will affect ts in some way:

| instruction | operation | effect on ts |
|--------------|:--------------|:--------------|
| ~ | push the value in ts back on top of the stack | ts becomes 0 again, as 0 has been evicted at 'stack top +1' postition |
| ( | copy value at sp to ts                        | ts = stack[sp] |
| ) | copy value at ts to stack at sp               | stack[sp] = ts |
| , | put the value of sp in ts                    | ts = sp |
| ! | replace value at stack[sp] with its boolean NOT | evict initial value at stack[sp] into ts |
| : | pop value at current stack pointer. shift any value in stack above sp downwards to fill space | evict initial value at stack[sp] into ts |
| $ | pop value at top of stack | popped value is evicted to ts |
| '\<number\>' | value will be stored as a number at stack[sp]. store as either float or int. e.g. '123' | previous value at stack[sp] is evicted to ts |
| "\<string\>" | value stored as a string at stack[sp] e.g. "hello" or "123"| previous value at stack[sp] is evicted to ts |

**\*Note:** the top of the stack is found as ``max(sp, highest inserted value)``  
input recieved from stdin will also evict the previous value of stack[sp] to ts. (see Input/Output section below)  

#### Arithmetic instructions  
All of these instructions operate in virtually the same way. The expression is evaluated in the form of: ``stack[sp] {operator} stack[sp-1]``, and the result of this expression is pushed on top of the stack.

|instruction| operation|
|---|:----------------|
| + | addition. stack[sp] + stack[sp-1]|
| - | subtraction. stack[sp] - stack[sp-1] |
| * | multiplication. stack[sp] * stack[sp-1] |
| / | division. stack[sp] / stack[sp-1] |
| \ | floor division. stack[sp] // stack[sp-1] |
| % | modulo. stack[sp] % stack[sp-1] |
| & | binary AND. stack[sp] & stack[sp-1] |
| \| | binary OR. stack[sp] \| stack[sp-1] |

#### Branching/conditional execution

|instruction| operation|
|---|:----------------|
| = | check if stack[sp] == 0, if so, then skip the next instruction on current path |
| \` | randomly place either a 0 or 1 at stack[sp] |
| ? | check if stack[sp] > stack[sp-1], if so, then skip next instruction on current path


#### Input/Output
|instruction| operation|
|---|:----------------|
| { | print stack[sp] to stdout |
| } | read an input from stdin and put this into stack[sp]. previously stored value of stack[sp] will be evicted to ts |  

**\*Note**: when doing input, the default input type is string. To input a number (float/int), user should enclose the input in `'` characters. e.g. `'456'`

#### Other characters
|character| effect|
|---|:----------------|
| a-z A-Z	0-9 | ignored unless within '', "", or after @|
| ; | used to write comments. all lines that start with ; will be treated as entirely whitespace |
| SPACE | NOP (non operational). no effect |
| . | NOP. no effect, but useful for outlining relative positions within files |

#### Misc information:
* pc starts in the upper-left corner of 0.tier, and begins with a velocity towards the right.
* pc will 'wrap around' the tier so that, for example, getting to the top with an upwards velocity will cause it to continue travelling upwards from the bottom of the tier. Similarly for the right and left sides.
* After a jump, the pc will execute whatever instruction it lands on before it continues.
* After a jump, pc will maintain the same velocity.
* 1 and 0 can be used for True and False.
* Quines are impossible in this language, as the " characters cannot be stored.
* All tiers are of the same dimension (height/width).
  Meaning that this program (where all tiers have dimension 2x1) will work:  
  0.tier:  
  `1@`  
  1.tier:  
  `..`  
  
  But this program (where all tiers have dimensions 3x1) have will fail  
  0.tier:  
  `1@`  
  1.tier:  
  `...`  
  (as there will be another additional space after the `@` sign in 0.tier, and attempting to jump to `@ ` will cause an error)
