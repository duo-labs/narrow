def other():
    print("Other")

def notused():
    print("Not Used")

def foo():
    print("Foo")
    bar()

def bar():
    print("Bar")

test = 102

if test > 20:
    foo()
else:
    other()
