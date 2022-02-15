import math


class Something:
    def __init__(self):
        self.property = "Hello"

    def other(self, alpha):
        return alpha + math.cos(alpha)


class Other:
    def test(self, alpha, beta):
        return alpha + beta.other(alpha)


test = Something()

other = Other()
print(other.test(12, test))
