# coding=utf-8
# Author: Gonçalo M. (aka duramato/supergonkas) <supergonkas@gmail.com>
#
# URL: https://sickchill.github.io
#
# This file is part of SickChill.
#
# SickChill is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickChill is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickChill. If not, see <http://www.gnu.org/licenses/>.
# Stdlib Imports
import re
import traceback

# Third Party Imports
from bs4 import BeautifulSoup

# First Party Imports
import sickbeard
from sickbeard import logger, tvcache
from sickchill.helper.common import convert_size, try_int
from sickchill.providers.media.torrent import TorrentProvider


class LimeTorrentsProvider(TorrentProvider):

    def __init__(self):

        super().__init__('LimeTorrents', extra_options=('public', 'minseed', 'minleech'))

        self.urls = {
            'index': 'https://www.limetorrents.info/',
            'search': 'https://www.limetorrents.info/searchrss/',
            'rss': 'https://www.limetorrents.info/rss/tv/'
        }

        self.url = self.urls['index']

        self.proper_strings = ['PROPER', 'REPACK', 'REAL']

        self.cache_search_params = {'RSS': ['rss']}

    def search(self, search_strings, ep_obj=None) -> list:
        results = []
        for mode in search_strings:
            items = []
            logger.debug("Search Mode: {0}".format(mode))
            for search_string in search_strings[mode]:

                if mode != 'RSS':
                    logger.debug("Search string: {0}".format(search_string))

                try:
                    search_url = (self.urls['rss'], self.urls['search'] + search_string + '/')[mode != 'RSS']

                    data = self.get_url(search_url, returns='text')
                    if not data:
                        logger.debug("No data returned from provider")
                        continue

                    if not data.startswith('<?xml'):
                        logger.info('Expected xml but got something else, is your mirror failing?')
                        continue

                    data = BeautifulSoup(data, 'html5lib')

                    entries = data('item')
                    if not entries:
                        logger.info('Returned xml contained no results')
                        continue

                    for item in entries:
                        try:
                            title = item.title.text
                            download_url = item.enclosure['url']
                            torrent_hash = re.match(r"(.*)([A-F0-9]{40})(.*)", download_url, re.I).group(2)

                            if sickbeard.TORRENT_METHOD != "blackhole" and 'magnet:?' not in download_url:
                                download_url = "magnet:?xt=urn:btih:" + torrent_hash + "&dn=" + title + self._custom_trackers

                            if not (title and download_url):
                                continue

                            # seeders and leechers are presented diferently when doing a search and when looking for newly added
                            if mode == 'RSS':
                                # <![CDATA[
                                # Category: <a href="http://www.limetorrents.info/browse-torrents/TV-shows/">TV shows</a><br /> Seeds: 1<br />Leechers: 0<br />Size: 7.71 GB<br /><br /><a href="http://www.limetorrents.info/Owen-Hart-of-Gold-Djon91-torrent-7180661.html">More @ limetorrents.info</a><br />
                                # ]]>
                                description = item.find('description')
                                seeders = try_int(description('br')[0].next_sibling.strip().lstrip('Seeds: '))
                                leechers = try_int(description('br')[1].next_sibling.strip().lstrip('Leechers: '))
                            else:
                                # <description>Seeds: 6982 , Leechers 734</description>
                                description = item.find('description').text.partition(',')
                                seeders = try_int(description[0].lstrip('Seeds: ').strip())
                                leechers = try_int(description[2].lstrip('Leechers ').strip())

                            torrent_size = item.find('size').text

                            size = convert_size(torrent_size) or -1

                        except (AttributeError, TypeError, KeyError, ValueError):
                            continue

                            # Filter unseeded torrent
                        if seeders < self.config('minseed') or leechers < self.config('minleech'):
                            if mode != 'RSS':
                                logger.debug("Discarding torrent because it doesn't meet the minimum seeders or leechers: {0} (S:{1} L:{2})".format
                                           (title, seeders, leechers))
                            continue

                        item = {'title': title, 'link': download_url, 'size': size, 'seeders': seeders, 'leechers': leechers, 'hash': torrent_hash}
                        if mode != 'RSS':
                            logger.debug("Found result: {0} with {1} seeders and {2} leechers".format(title, seeders, leechers))

                        items.append(item)

                except (AttributeError, TypeError, KeyError, ValueError):
                    logger.exception("Failed parsing provider. Traceback: {0!r}".format(traceback.format_exc()))

            # For each search mode sort all the items by seeders if available
            items.sort(key=lambda d: try_int(d.get('seeders', 0)), reverse=True)

            results += items

        return results



