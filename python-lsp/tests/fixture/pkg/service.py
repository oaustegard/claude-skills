from pkg.models import User, helper


def make_user(name: str) -> User:
    u = User(name)
    print(helper(3))
    return u
