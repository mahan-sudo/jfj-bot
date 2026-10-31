_CASTERS = {}
ISOLATION_LEVEL_AUTOCOMMIT = 0
ISOLATION_LEVEL_READ_COMMITTED = 1


class _T:
    def __init__(self, oids, name, fn):
        self.values, self.name, self.fn = oids, name, fn


def new_type(oids, name, fn):
    return _T(oids, name, fn)


def register_type(t, scope=None):
    for o in t.values:
        _CASTERS[o] = t.fn
