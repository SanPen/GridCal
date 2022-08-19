import collections

try:
    collections.Callable = collections.abc.Callable
except:
    pass
