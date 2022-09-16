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
cost_dict = {  # edit this to edit block costs
    'g': 20,  # generator
    'r': 10,  # redirector
    'p': 10,  # splitter
    'l': 20,  # blocker
    'b': 40,  # bridge
    'i': 0,  # input (must be 0)
    'o': 0  # output (must be 0)
}