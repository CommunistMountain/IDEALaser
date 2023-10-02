# IDEALaser
Latest version: 1.2

Original idea by OMGITSABIST in the Zachtronics Unofficial Discord.

Rules:
1. When lasers collide, they annihilate each other.
2. Lasers move in 2 speeds: simultaneous, where each laser progresses by 1 tile per cycle, and blocktime, where each
laser progresses to the next block (except bridges or bridge output) or infinity per cycle.
3. Maximum of 1 block per tile.
4. Blocks may not move.
5. No editing of blocks while solution is running; after edits, lasers are cleared and the whole thing is reset.

Important Notes:
1. To import and use many of these functions, the init_globals() function must be used, and assigned to specified
variable names.
2. There are no XOR or AND Output blocks, always OR, because lasers do not remember which input fired them, necessary
due to redirectors being able to merge lasers. NOR output block is not implemented because it is trivial to convert
OR to NOR. (Although, if a new output block has conditional true, e.g. bridge output with vertical and horizontal pipes,
it may be possible to implement AND or XOR).
3. Input block can be provided additional arguments to oscillate its pulse in a specific pattern. "1" will cause it
to alternate between firing and not firing every cycle.
