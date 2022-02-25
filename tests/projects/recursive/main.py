def tail():
    print("Tail")


def recurse(val):
    if val > 0:
        return recurse()
    else:
        return tail()

recurse(10)
