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
# 2. Generator + Dual < Generator + Splitter <= 2 Generator < Generator + Dual + Redirector
# 3. Blocker < Generator (as that can be used to block lasers)
# 4. Non-bridge < Bridge
cost_dict = {  # edit this to edit block costs
    'g': 20,  # generator
    'r': 10,  # redirector
    # 'd': 15,  # dual
    'p': 20,  # splitter
    'l': 10,  # blocker
    'b': 30,  # bridge
    'i': 0,  # input (must be 0)
    'o': 0  # output (must be 0)
}
