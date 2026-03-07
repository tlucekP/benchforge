"""Clean Python fixture — no structural issues expected."""


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def greet(name: str) -> str:
    """Return a greeting string."""
    return f"Hello, {name}!"


def compute_average(numbers: list[float]) -> float:
    """Return the arithmetic mean of a list of numbers."""
    if not numbers:
        return 0.0
    return sum(numbers) / len(numbers)


def is_even(n: int) -> bool:
    """Return True if n is even."""
    return n % 2 == 0
