class User:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> str:
        return f"hi {self.name}"


def helper(x: int) -> int:
    return x + 1
