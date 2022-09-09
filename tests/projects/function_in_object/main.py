def foo():
    print("test")

def other():
    exit(0)

test = {
    "hello": foo(),
    "other": other()
}