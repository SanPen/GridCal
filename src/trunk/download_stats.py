# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


"""
https://gist.github.com/dchaplinsky/1224948
Calculates the total number of downloads that a particular PyPI package has
received across all versions tracked by PyPI
"""

import locale
import sys
import xmlrpc.client

locale.setlocale(locale.LC_ALL, '')


class PyPIDownloadAggregator:
    """
    PyPIDownloadAggregator
    """

    def __init__(self, package_name, include_hidden=True):
        self.package_name = package_name
        self.include_hidden = include_hidden
        self.proxy = xmlrpc.client.ServerProxy('https://pypi.python.org/pypi')
        self._downloads = dict()

        self.first_upload = None
        self.first_upload_rel = None
        self.last_upload = None
        self.last_upload_rel = None

    @property
    def releases(self):
        """Retrieves the release number for each uploaded release"""

        result = self.proxy.package_releases(self.package_name, self.include_hidden)

        if len(result) == 0:
            # no matching package--search for possibles, and limit to 15 results
            results = self.proxy.search({
                'name': self.package_name,
                'description': self.package_name
            }, 'or')[:15]

            # make sure we only get unique package names
            matches = []
            for match in results:
                name = match['name']
                if name not in matches:
                    matches.append(name)

            # if only one package was found, return it
            if len(matches) == 1:
                self.package_name = matches[0]
                return self.releases

            error = """No such package found: %s
                    Possible matches include:
                    %s
                    """ % (self.package_name, '\n'.join('\t- %s' % n for n in matches))

            sys.exit(error)

        return result

    def init_downloads(self):
        """

        :return:
        """
        for release in self.releases:
            urls = self.proxy.release_urls(self.package_name, release)
            self._downloads[release] = 0
            for url in urls:
                # upload times
                uptime = url['upload_time']
                if self.first_upload is None or uptime < self.first_upload:
                    self.first_upload = uptime
                    self.first_upload_rel = release

                if self.last_upload is None or uptime > self.last_upload:
                    self.last_upload = uptime
                    self.last_upload_rel = release

                self._downloads[release] += url['downloads']

    @property
    def downloads(self, force=False):
        """Calculate the total number of downloads for the package"""

        if len(self._downloads) == 0 or force:
            self.init_downloads()

        return self._downloads

    def total(self):
        """

        :return:
        """
        return sum(self.downloads.values())

    def average(self):
        """

        :return:
        """
        return self.total() / len(self.downloads)

    def max(self):
        """

        :return:
        """
        return max(self.downloads.values())

    def min(self):
        """

        :return:
        """
        return min(self.downloads.values())

    def stats(self):
        """Prints a nicely formatted list of statistics about the package"""

        self.init_downloads()
        fmt = locale.nl_langinfo(locale.D_T_FMT)
        sep = lambda s: locale.format_string('%d', s, 3)
        val = lambda dt: dt and dt.strftime(fmt) or '--'

        params = (
            self.package_name,
            val(self.first_upload),
            self.first_upload_rel,
            val(self.last_upload),
            self.last_upload_rel,
            sep(len(self.releases)),
            sep(self.max()),
            sep(self.min()),
            sep(self.average()),
            sep(self.total()),
        )

        print("""PyPI Package statistics for: %s
              First Upload: %40s (%s)
              Last Upload:  %40s (%s)
              Number of releases: %34s
              Most downloads:    %35s
              Fewest downloads:  %35s
              Average downloads: %35s
              Total downloads:   %35s
              """ % params)


def main():
    """

    """
    pkg = 'GridCal'
    PyPIDownloadAggregator(pkg).stats()


if __name__ == '__main__':
    main()

# TODO This is not a test. So move to scripts or something.
