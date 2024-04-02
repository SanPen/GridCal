"""
An extended dictionary offering limited LRU entries in the dictionary
and an interface to an unlimited backing store.

https://github.com/rzzzwilson/pyCacheBack
"""


class PyCacheBack(dict):
    """An LRU limited in-memory store fronting an unlimited on-disk store."""

    # default maximum number of key/value pairs for pyCacheBack
    DefaultMaxLRU = 1000

    # default path to tiles directory
    DefaultTilesDir = 'tiles'

    def __init__(self, *args, **kwargs):
        self._lru_list = []
        self._max_lru = kwargs.pop('max_lru', self.DefaultMaxLRU)
        self._tiles_dir = kwargs.pop('tiles_dir', self.DefaultTilesDir)
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        if key in self:
            value = super().__getitem__(key)
        else:
            value = self._get_from_back(key)
        self._reorder_lru(key)
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._put_to_back(key, value)
        self._reorder_lru(key)
        self._enforce_lru_size()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._reorder_lru(key, remove=True)

    def clear(self):
        """

        """
        super().clear()
        self._lru_list = []

    def pop(self, *args):
        """

        :param args:
        :return:
        """
        k = args[0]
        try:
            self._lru_list.remove(k)
        except ValueError:
            pass
        return super().pop(*args)

    def popitem(self):
        """

        :return:
        """
        kv_return = super().popitem()
        try:
            self._lru_list.remove(kv_return[0])
        except ValueError:
            pass
        return kv_return

    def _reorder_lru(self, key, remove=False):
        """Move key in LRU (if it exists) to 'recent' end.

        If 'remove' is True just remove from the LRU.
        """

        try:
            self._lru_list.remove(key)
        except ValueError:
            pass
        if remove:
            return
        self._lru_list.insert(0, key)

    def _enforce_lru_size(self):
        """Enforce LRU size limit in cache dictionary."""

        # if a limit was defined and we have blown it
        if self._max_lru and len(self) > self._max_lru:
            # make sure in-memory dictionary doesn't get bigger
            for key in self._lru_list[self._max_lru:]:
                super().__delitem__(key)
            # also truncate the LRU list
            self._lru_list = self._lru_list[:self._max_lru]

    #####
    # override the following two methods to implement the backing cache
    #####

    def _put_to_back(self, key, value):
        """Store 'value' in backing store, using 'key' to access."""

        pass

    def _get_from_back(self, key):
        """Retrieve value for 'key' from backing storage.

        Raises KeyError if key not in backing storage.
        """

        raise KeyError

