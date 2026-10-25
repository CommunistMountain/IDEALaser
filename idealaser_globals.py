facing_dict = {
    'w': '^',
    'a': '<',
    's': 'v',
    'd': '>'
}
opposite_face_dict = {
    'w': 's',
    'a': 'd',
    's': 'w',
    'd': 'a'
}
# Price rules:
# 1. Input and output must cost 0. (unless output is modified to allow lasers to be reused?)
# 2. Dual < Quad <= Generator <= Dual + Redirector
# 3. Blocker < Redirector (as that can be used to block lasers)
# 4. Non-bridge < Bridge
cost_dict = {  # edit this to edit block costs
    'i': 0,  # input (must be 0)
    'o': 0,  # output (must be 0)
    'l': 5,  # blocker
    'r': 10,  # redirector
    'd': 15,  # dualsplitter
    'q': 20,  # quadsplitter
    'g': 25,  # generator
    'b': 30,  # bridge
}
