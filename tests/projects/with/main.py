class TestThing(object):
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, tb):
        pass


def other():
    print("Other")


with TestThing() as test:
    other()
