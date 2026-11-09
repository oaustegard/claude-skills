import numpy as np


def place_points():
    """Return an (8, 2) numpy array of points inside the unit square."""
    xs = np.linspace(0.1, 0.9, 4)
    return np.array([[x, y] for y in (0.3, 0.7) for x in xs])
