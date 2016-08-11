#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#   Writer (c) 23/06/2011, Khrysev D.A., E-mail: x86demon@gmail.com
#
#   This Program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2, or (at your option)
#   any later version.
#
#   This Program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; see the file COPYING.  If not, write to
#   the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#   http://www.gnu.org/licenses/gpl.html

__author__ = "Dmitry Khrysev"
__license__ = "GPL"
__maintainer__ = "Dmitry Khrysev"
__email__ = "x86demon@gmail.com"
__status__ = "Production"

import socket

socket.setdefaulttimeout(50)

import os
import re
import urllib

import simplejson as json
from kodiswift import Plugin, xbmc, xbmcvfs

plugin = Plugin()

from lib.fsua import FsUa
from lib.httpclient import HttpClient

import SimpleDownloader as downloader
from BeautifulSoup import BeautifulSoup
from lib import strutils, kodi

# from pydev import pydevd
# pydevd.settrace('localhost', port=63342, stdoutToServer=True, stderrToServer=True)

__addondir__ = xbmc.translatePath(plugin.addon.getAddonInfo('profile'))
icon = xbmc.translatePath(os.path.join(plugin.addon.getAddonInfo('path'), 'icon.png'))
cache_path = xbmc.translatePath(os.path.join(plugin.addon.getAddonInfo('profile'), 'cache'))

if not xbmcvfs.exists(__addondir__):
    xbmcvfs.mkdir(__addondir__)

if not xbmcvfs.exists(cache_path):
    xbmcvfs.mkdir(cache_path)

__language__ = plugin.addon.getLocalizedString

siteUrl = plugin.get_setting('Site URL')
# siteUrl = 'fs.to'
httpSiteUrl = 'http://' + siteUrl

client = HttpClient(http_site_url=httpSiteUrl, cookie_path=__addondir__)
fs_ua = FsUa(plugin=plugin, client=client)


def show_message(heading, message, times=3000):
    plugin.notify(message, heading, times, icon)


def get_flat_params():
    flat = plugin.request.args.copy()
    for k in flat.iterkeys():
        flat[k] = flat[k][0]
    return flat


def logout():
    client.GET(httpSiteUrl + '/logout.aspx', httpSiteUrl)
    plugin.set_setting("Login", "")
    plugin.set_setting("Password", "")


def check_login():
    login = plugin.get_setting("Login")
    password = plugin.get_setting("Password")

    if len(login) > 0:
        http = client.GET(httpSiteUrl, httpSiteUrl)
        if http is None:
            return False

        beautifulSoup = BeautifulSoup(http)
        userPanel = beautifulSoup.find('a', 'm-header__user-link_favourites')

        if userPanel is None:
            client.remove_cookie()

            loginResponse = client.GET(httpSiteUrl + '/login.aspx', httpSiteUrl, {
                'login': login,
                'passwd': password,
                'remember': 'on'
            })

            loginSoup = BeautifulSoup(loginResponse)
            userPanel = loginSoup.find('a', 'm-header__user-link_favourites')
            if userPanel is None:
                show_message('Login', 'Check login and password', 3000)
            else:
                return True
        else:
            return True
    return False


@plugin.route('/')
def main():
    items = [
        {
            'label': u'[Видео]',
            'path': plugin.url_for('get_categories', category='video', href=httpSiteUrl + '/video/', filter='',
                                   firstPage='yes')
        },
        {
            'label': u'[Аудио]',
            'path': plugin.url_for('get_categories', category='audio', href='http://brb.to/audio/', ilter='',
                                   firstPage='yes')
        }
    ]

    if check_login():
        items.extend([
            {
                'label': 'В процессе',
                'path': plugin.url_for('get_fav_categories', type='inprocess')
            },
            {
                'label': 'Избранное',
                'path': plugin.url_for('get_fav_categories', type='favorites')
            },
            {
                'label': 'Рекомендуемое',
                'path': plugin.url_for('get_fav_categories', type='recommended')
            },
            {
                'label': 'На будущее',
                'path': plugin.url_for('get_fav_categories', type='forlater')
            },
            {
                'label': 'Я рекомендую',
                'path': plugin.url_for('get_fav_categories', type='irecommended')
            },
            {
                'label': 'Завершенное',
                'path': plugin.url_for('get_fav_categories', type='finished')
            },
        ])

    return items


@plugin.route('/categories/<category>/')
def get_categories(category):
    params = get_flat_params()
    categoryUrl = urllib.unquote_plus(params['href'])

    http = client.GET(categoryUrl, httpSiteUrl)
    if http is None:
        return False

    items = []

    beautifulSoup = BeautifulSoup(http)

    submenuSelector = 'b-header__menu'
    submenuItemSelector = 'b-header__menu-section-link'
    if category == 'audio':
        submenuSelector = 'b-subsection-menu__items'
        submenuItemSelector = 'b-subsection-menu__item'

    categorySubmenu = beautifulSoup.find('div', submenuSelector)
    if categorySubmenu is None:
        show_message('ОШИБКА', 'Неверная страница', 3000)
        return False

    subcategories = categorySubmenu.findAll('a', submenuItemSelector)
    if len(subcategories) == 0:
        show_message('ОШИБКА', 'Неверная страница', 3000)
        return False

    for subcategory in subcategories:
        # label = subcategory.find('span')
        items.append({
            'label': '[' + subcategory.text + ']',
            'path': plugin.url_for('readcategory', category=category,
                                   href=client.get_full_url(subcategory['href']),
                                   cleanUrl=client.get_full_url(subcategory['href']),
                                   start=0, filter='')
        })
    loadMainPageItems = plugin.get_setting('Load main page items')
    if loadMainPageItems == 'true':
        items.extend(
            readcategory(category, {
                'href': params['href'],
                'cleanUrl': params['href'],
                'section': category,
                'start': 0,
                'filter': '',
                'disableFilters': 'yes'
            })
        )

    return items


@plugin.route("/favourites")
def get_fav_categories():
    params = get_flat_params()
    http = client.GET(httpSiteUrl + '/myfavourites.aspx?page=' + params['type'], httpSiteUrl)
    if http is None:
        return False

    items = []

    beautifulSoup = BeautifulSoup(http)
    favSectionsContainer = beautifulSoup.find('div', 'b-tabpanels')
    if favSectionsContainer is None:
        show_message('ОШИБКА', 'В избранном пусто', 3000)
        return False

    favSections = favSectionsContainer.findAll('div', 'b-category')
    if len(favSections) == 0:
        show_message('ОШИБКА', 'В избранном пусто', 3000)
        return False
    sectionRegexp = re.compile("\s*\{\s*section:\s*'([^']+)")
    subsectionRegexp = re.compile("subsection:\s*'([^']+)")
    for favSection in favSections:
        rel = favSection.find('a', 'b-add')['rel'].encode('utf-8')
        section = sectionRegexp.findall(rel)[0]
        subsection = subsectionRegexp.findall(rel)[0]
        title = str(favSection.find('a', 'item').find('b').string)
        items.append({
            'label': title,
            'is_playable': False,
            'path': plugin.url_for('read_favs', section=section, subsection=subsection, type=params['type'], page=0)
        })
    return items


@plugin.route('/favourites/<section>/<subsection>')
def read_favs(section, subsection):
    params = get_flat_params()
    href = httpSiteUrl + "/myfavourites.aspx?ajax&section=" + section \
           + "&subsection=" + subsection \
           + "&rows=1&curpage=" + params['page'] \
           + "&action=get_list&setrows=1&page=" + params['type']

    favorites = read_fav_data(urllib.unquote_plus(href))
    if len(favorites) == 0:
        show_message('ОШИБКА', 'В избранном пусто', 3000)
        return False

    result_items = []
    for item in favorites:
        additional = ''
        if item['season'] > 0:
            additional = ' (s%se%s)' % (item['season'], item['episode'])

        id = item['href'].split('/')[-1]
        result_items.append({
            'label': strutils.html_entities_decode(item['title']) + additional,
            'icon': fs_ua.thumbnail(item['cover']),
            'thumbnail': fs_ua.poster(item['cover']),
            'is_playable': False,
            'path': plugin.url_for('read_dir', href=item['href'], referer=href, cover=item['cover'], folder=0,
                                   isMusic=item['isMusic']),
            'context_menu': [
                (
                    __language__(50003),
                    "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='favorites', id=id, title=item['title'])
                ),
                (
                    __language__(50004),
                    "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='playlist', id=id, title=item['title'])
                )
            ]

        })

    params['page'] = int(params['page']) + 1
    result_items.append({
        'label': '[NEXT PAGE >]',
        'path': strutils.construct_request(params),
        'is_playable': False
    })
    return result_items


def read_fav_data(favoritesUrl):
    favorites = []
    http = client.GET(favoritesUrl, httpSiteUrl)
    if http is None:
        return favorites

    data = json.loads(str(http))
    http = data['content'].encode('utf-8')

    beautifulSoup = BeautifulSoup(http)
    container = beautifulSoup.find('div', 'b-posters')
    if container is None:
        return favorites

    items = container.findAll('div', 'b-poster-thin__wrapper ')
    if len(items) == 0:
        return favorites

    cover_regexp = re.compile("url\s*\('([^']+)")
    episode_regexp = re.compile("s(\d+)e(\d+)")

    for wrapper in items:
        item = wrapper.find('a', 'b-poster-thin')

        season = 0
        episode = 0

        episode_data = episode_regexp.findall(str(wrapper))
        if episode_data is not None and len(episode_data) > 0:
            season = episode_data[0][0]
            episode = episode_data[0][1]

        cover = cover_regexp.findall(str(item['style']))[0]
        title = str(item.find('b', 'subject-link').find('span').string)
        href = client.get_full_url(item['href'])

        isMusic = "no"
        if re.search('audio', href):
            isMusic = "yes"

        # get_material_details(href)

        favorites.append({
            'href': href,
            'title': strutils.html_entities_decode(title),
            'cover': cover,
            'season': season,
            'episode': episode,
            'isMusic': isMusic
        })

    return favorites


# def get_material_details(url):
#     data = {}
#     cache_file_name = '%s.json' % hashlib.md5(url).hexdigest()
#     cache_file_path = os.path.join(cache_path, cache_file_name)
#
#     if xbmcvfs.exists(cache_file_path):
#         fp = open(cache_file_path, 'r')
#         data = json.load(fp)
#         fp.close()
#
#         return data
#
#     http = client.GET(url, httpSiteUrl)
#     if http is None:
#         return data
#
#     cover_regexp = re.compile("url\s*\(([^\)]+)")
#
#     beautifulSoup = BeautifulSoup(http)
#
#     info = beautifulSoup.find('div', 'item-info')
#     genre_element_container = info.findAll('span', {"itemprop" : "genre"})
#     genres = []
#     for genre_element in genre_element_container:
#         genres.append(strutils.fix_string(genre_element.find('span').string.strip()))
#
#     title = strutils.fix_string(beautifulSoup.find('div', 'b-tab-item__title-inner').find('span').string)
#     original_title = strutils.html_entities_decode(beautifulSoup.find('div', 'b-tab-item__title-origin').string)
#     description = beautifulSoup.find('p', 'item-decription').string.encode('utf-8')
#
#     poster = fs_ua.poster(client.get_full_url(beautifulSoup.find('div', 'poster-main').find('img')['src']))
#
#     images_container = beautifulSoup.find('div', 'b-tab-item__screens')
#     image_elements = images_container.findAll('a')
#     images = []
#     for image_element in image_elements:
#         images.append(
#             client.get_full_url(
#                 fs_ua.poster(
#                     cover_regexp.findall(str(image_element['style']).strip())[0]
#                 )
#             )
#         )
#
#     rating_positive = beautifulSoup.find('div', 'm-tab-item__vote-value_type_yes').string.strip()
#     rating_negative = beautifulSoup.find('div', 'm-tab-item__vote-value_type_no').string.strip()
#
#     data = {
#         'title': title.strip(),
#         'original_title': original_title.strip(),
#         'poster': poster,
#         'description': description,
#         'images': images,
#         'genres': genres,
#         'rating_positive': rating_positive,
#         'rating_negative': rating_negative
#     }
#
#     fp = open(cache_file_path, 'w')
#     json.dump(data, fp)
#     fp.close()
#
#     return data

@plugin.route('/categories/read/<category>')
def readcategory(category, params=None):
    params = params or get_flat_params()
    start = int(params['start'])
    category_href = urllib.unquote_plus(params['href'])

    categoryUrl = category_href
    if 'disableFilters' not in params:
        categoryUrl = fs_ua.get_url_with_sort_by(
            category_href,
            category,
            params['start'],
            'detailed'
        )

    http = client.GET(categoryUrl, httpSiteUrl)
    if http is None:
        return False

    try:
        filter = params['filter']
    except:
        filter = ''
        params['filter'] = filter

    beautifulSoup = BeautifulSoup(http)
    itemsClass = 'b-poster-detail'

    items = beautifulSoup.findAll('div', itemsClass)
    result_items = []

    if len(items) == 0:
        show_message('ОШИБКА', 'Неверная страница', 3000)
        return False
    else:
        if start == 0 and 'hideFirstPageData' not in params:
            result_items.extend(load_first_page_sections(category_href, category, params))

        for item in items:
            cover = None
            href = None

            img = item.find('img')
            link = item.find('a', itemsClass + '__link')
            title = item.find('span', 'b-poster-detail__title').contents[0]
            if img is not None:
                cover = img['src']
                href = client.get_full_url(link['href'])

            if title is not None:
                plot = []
                details = item.find('span', 'b-poster-detail__description').contents
                for detail in details:
                    try:
                        plot.append(detail.encode('utf8'))
                    except:
                        pass

                isMusic = 'no'
                if category == 'audio':
                    isMusic = 'yes'

                id = str(link['href'].split('/')[-1])
                titleText = strutils.html_entities_decode(title.encode('utf8'))
                item = {
                    'label': titleText,
                    'path': plugin.url_for('read_dir', href=href, referer=categoryUrl, cover=cover, folder=0,
                                           isMusic=isMusic),
                    'icon': fs_ua.thumbnail(cover),
                    'thumbnail': fs_ua.poster(cover),
                    'is_playable': False,

                    'context_menu': [
                        (
                            __language__(50001),
                            "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='favorites', id=id)
                        ),
                        (
                            __language__(50002),
                            "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='playlist', id=id)
                        )
                    ]
                }
                if plot != '':
                    item['info_type'] = category
                    item['info'] = {'title': titleText, 'plot': plot}

                result_items.append(item)

    result_items.append({
        'label': '[NEXT PAGE >]',
        'is_playable': False,
        'path': plugin.url_for('readcategory', category=category, href=category_href, filter=filter, start=start + 1,
                               firstPage='no')
    })
    return result_items


def load_first_page_sections(href, category, params):
    # Add search list item
    items = [{
        'label': '[ПОИСК]',
        'is_playable': False,
        'path': plugin.url_for('runsearch', category=category, url=params['cleanUrl'])
    }]
    first_page_data = client.GET(href, httpSiteUrl)
    if first_page_data is None:
        return False

    beautifulSoup = BeautifulSoup(first_page_data)
    if beautifulSoup is None:
        return False

    groups = beautifulSoup.find('div', 'b-section-menu')
    if groups is not None:
        yearLink = groups.find('a', href=re.compile(r'year'))
        if yearLink is not None:
            items.append({
                'label': '[По годам]',
                'is_playable': False,
                'path': plugin.url_for('getGenreList', category=category, filter=params['filter'],
                                       href=yearLink['href'], cleanUrl=urllib.unquote_plus(params['cleanUrl']),
                                       css='main')
            })
        genreLink = groups.find('a', href=re.compile(r'genre'))
        if genreLink is not None:
            items.append({
                'label': '[Жанры]',
                'is_playable': False,
                'path': plugin.url_for('getGenreList', category=category, filter=params['filter'],
                                       href=genreLink['href'], cleanUrl=urllib.unquote_plus(params['cleanUrl']),
                                       css='b-list-subcategories')
            })
    return items


@plugin.route('/genres/<category>')
def getGenreList(category):
    params = get_flat_params()
    http = client.GET(urllib.unquote_plus(params['href']), httpSiteUrl)
    if http is None:
        return False

    beautifulSoup = BeautifulSoup(http)
    items = beautifulSoup.find('div', params['css']).findAll('a')

    result_items = []
    if len(items) == 0:
        show_message('ОШИБКА', 'Неверная страница', 3000)
        return False
    else:
        for item in items:
            result_items.append({
                'label': item.string,
                'is_playable': False,
                'path': plugin.url_for('readcategory', category=category,
                                       href=client.get_full_url(item['href'].encode('utf-8')), filter='',
                                       cleanUrl=urllib.unquote_plus(params['cleanUrl']),
                                       start=0, hideFirstPageData=1)
            })
    return result_items


@plugin.route('/directory')
def read_dir():
    params = get_flat_params()
    folderUrl = urllib.unquote_plus(params['href'])
    cover = urllib.unquote_plus(params['cover'])
    folder = params['folder']

    getUrl = folderUrl + '?ajax&folder=' + folder

    http = client.GET(getUrl, httpSiteUrl)
    if http is None:
        return False

    beautifulSoup = BeautifulSoup(http)
    if params['folder'] == '0':
        has_blocked = beautifulSoup.find('div', attrs={'id': 'file-block-text'})
        if has_blocked is not None:
            show_message('Blocked content', 'Некоторые файлы заблокированы')

    mainItems = beautifulSoup.find('ul', 'filelist')

    if mainItems is None:
        show_message('ОШИБКА', 'No filelist', 3000)
        return False

    if 'quality' in params \
            and params['quality'] is not None \
            and params['quality'] != 'None' \
            and params['quality'] != '':
        items = mainItems.findAll('li', 'video-' + params['quality'])
    else:
        items = mainItems.findAll('li')

    materialQualityRegexp = re.compile('quality_list:\s*[\'|"]([a-zA-Z0-9,]+)[\'|"]')
    result_items = []
    if len(items) == 0:
        show_message('ОШИБКА', 'Неверная страница', 3000)
        return False
    else:
        for item in items:
            isFolder = 'folder' in item['class']
            playLink = None
            if isFolder:
                linkItem = item.find('a', 'title')
                playLinkClass = ''
            else:
                playLinkClass = 'b-file-new__link-material'
                linkItem = item.find('a', 'b-file-new__link-material-download')
                playLink = item.find('a', playLinkClass)
                if playLink is None:
                    playLinkClass = 'b-file-new__material'
                    playLink = item.find('div', playLinkClass)

            if linkItem is not None:
                materialData = linkItem['rel']
                if materialData is not None:
                    qualities = materialQualityRegexp.findall(linkItem['rel'])
                    itemsCount = item.find('span', 'material-series-count')
                    if qualities is not None and len(qualities) > 0:
                        qualities = str(qualities[0]).split(',')
                        for quality in qualities:
                            result_items.append(
                                add_directory_item(linkItem, isFolder, playLink, playLinkClass, cover, folderUrl,
                                                   folder,
                                                   params['isMusic'], quality, itemsCount))
                    else:
                        result_items.append(
                            add_directory_item(linkItem, isFolder, playLink, playLinkClass, cover, folderUrl, folder,
                                               params['isMusic'], None, itemsCount))
                else:
                    result_items.append(
                        add_directory_item(linkItem, isFolder, playLink, playLinkClass, cover, folderUrl, folder,
                                           params['isMusic'], None, None))

    return result_items


def add_directory_item(linkItem, isFolder, playLink, playLinkClass, cover, folderUrl, folder, isMusic, quality=None,
                       itemsCount=None):
    folderRegexp = re.compile('(\d+)')
    lang = None
    langRegexp = re.compile('\s*m\-(\w+)\s*')
    lang_data = langRegexp.findall(linkItem['class'])
    if len(lang_data) > 0:
        lang = str(lang_data[0])
    title = ""
    if isFolder:
        title = strutils.fix_string(linkItem.text)

        if (itemsCount):
            title = "%s (%s)" % (title, strutils.fix_string(itemsCount.text))

        lang_quality_el = linkItem.find('font')
        if lang_quality_el:
            lang_quality = strutils.fix_string(lang_quality_el.text)
            title = title.replace(lang_quality, ' ' + lang_quality)

        if quality is not None:
            title = "%s [%s]" % (title, quality)
    else:
        try:
            title = str(playLink.find('span', playLinkClass + '-filename-text').string)
        except:
            pass
    if lang is not None:
        title = lang.upper() + ' - ' + title

    if playLink is not None and playLink.name == 'a':
        if 'href' in playLink:
            playLink = client.get_full_url(str(playLink['href']))
        elif 'rel' in playLink:
            playLink = client.get_full_url(str(playLink['rel']))
        else:
            playLink = ''
    else:
        playLink = ''

    href = linkItem['href']
    try:
        folder = folderRegexp.findall(linkItem['rel'])[0]
    except:
        pass

    if isFolder:
        item = {
            'label': strutils.html_entities_decode(title),
            'icon': fs_ua.thumbnail(cover),
            'thumbnail': fs_ua.poster(cover),
            'is_playable': False,
            'path': plugin.url_for('read_dir',
                                   cover=cover,
                                   href=folderUrl,
                                   referer=folderUrl,
                                   folder=folder,
                                   isMusic=isMusic,
                                   quality=quality
                                   )
        }

        return item
    else:
        item_type = 'video'
        if isMusic == 'yes':
            item_type = 'music'

        return add_folder_file({
            'title': title,
            'cover': cover,
            'href': href,
            'referer': folderUrl,
            'type': item_type,
            'playLink': playLink
        })


def add_folder_file(item):
    title = item['title']
    cover = item['cover']
    href = item['href']
    referer = item['referer']
    item_type = item['type']

    result_item = {
        'label': strutils.html_entities_decode(title),
        'icon': fs_ua.thumbnail(cover),
        'thumbnail': fs_ua.poster(cover),
        'path': plugin.url_for('play', path=href),
        'is_playable': True,
        'info_type': item_type,
        'info': {'title': title}
    }

    playCount = kodi.get_play_count(strutils.html_entities_decode(title))
    if playCount:
        result_item['info_type'] = item_type
        result_item['info'] = {'title': title, 'playcount': 1}
        result_item['context_menu'] = [
            (
                __language__(40001),
                "XBMC.RunPlugin(%s)" % plugin.url_for('download', file_url=str(href.encode('utf-8')),
                                                      file_name=strutils.html_entities_decode(title))
            ),
        ]

    # if item_type == 'music' or (plugin.addon.getSetting('Autoplay next') == 'true'):
    #     uri = strutils.construct_request({
    #         'file': str(href.encode('utf-8')),
    #         'referer': referer,
    #         'mode': 'play',
    #         'playLink': item['playLink']
    #     })
    # else:
    #     uri = client.get_full_url(href)

    return result_item


@plugin.route('/download/<file_url>')
def download(file_url):
    fileUrl = client.get_full_url(urllib.unquote_plus(file_url))
    fileName = fileUrl.split('/')[-1]
    download_params = {
        'url': fileUrl,
        'download_path': plugin.addon.getSetting('Download Path')
    }
    download_client = downloader.SimpleDownloader()
    download_client.download(fileName, download_params)


@plugin.route('/search/<category>')
def runsearch(category):
    params = get_flat_params()
    skbd = xbmc.Keyboard()
    skbd.setHeading('Что ищем?')
    skbd.doModal()
    if skbd.isConfirmed():
        SearchStr = skbd.getText()
        searchUrl = '%ssearch.aspx?search=%s' % (urllib.unquote_plus(params['url']), urllib.quote_plus(SearchStr))
        params = {
            'href': searchUrl,
            'section': category
        }
        return render_search_results(category, params)


def render_search_results(category, params):
    searchUrl = urllib.unquote_plus(params['href'])
    http = client.GET(searchUrl, httpSiteUrl)
    if http is None:
        return False

    beautifulSoup = BeautifulSoup(http)
    results = beautifulSoup.find('div', 'b-search-page__results')

    result_items = []
    if results is None:
        show_message('ОШИБКА', 'Ничего не найдено', 3000)
        return False
    else:
        items = results.findAll('a', 'b-search-page__results-item')
        if len(items) == 0:
            show_message('ОШИБКА', 'Ничего не найдено', 3000)
            return False

        for item in items:
            title = str(item.find('span', 'b-search-page__results-item-title').text.encode('utf-8'))
            href = client.get_full_url(item['href'])
            cover = item.find('span', 'b-search-page__results-item-image').find('img')['src']
            section = item.find('span', 'b-search-page__results-item-subsection').text

            if title is not None:
                isMusic = 'no'
                if category == 'audio':
                    isMusic = 'yes'

                id = item['href'].split('/')[-1]
                result_items.append({
                    'label': '[%s] %s' % (strutils.html_entities_decode(section), strutils.html_entities_decode(title)),
                    'icon': fs_ua.thumbnail(cover),
                    'thumbnail': fs_ua.poster(cover),
                    'is_playable': False,
                    'path': plugin.url_for('read_dir', href=href, referer=searchUrl, cover=cover, folder=0,
                                           isMusic=isMusic),

                    'context_menu': [
                        (
                            __language__(50001),
                            "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='favorites', id=id)
                        ),
                        (
                            __language__(50002),
                            "XBMC.RunPlugin(%s)" % plugin.url_for('addto', category='playlist', id=id)
                        )
                    ]

                })
    return result_items


@plugin.route('/addto/<category>')
def addto(category):
    params = get_flat_params()
    idRegexp = re.compile("([^-]+)")
    itemId = idRegexp.findall(params['id'])[0]
    addToHref = httpSiteUrl + "/addto/" + category + '/' + itemId + "?json"
    client.GET(addToHref, httpSiteUrl)
    show_message('Result', "Toggled state in " + category, 5000)

@plugin.route('/play/<path>')
def play(path):
    plfile = urllib.urlopen(client.get_full_url(path))
    fileUrl = plfile.geturl()
    plugin.log.debug('Playing url: %s' % fileUrl)
    return plugin.set_resolved_url(fileUrl)


# def get_params(paramstring):
#     param = []
#     if len(paramstring) >= 2:
#         params = paramstring
#         cleanedparams = params.replace('?', '')
#         if (params[len(params) - 1] == '/'):
#             params = params[0:len(params) - 2]
#         pairsofparams = cleanedparams.split('&')
#         param = {}
#         for i in range(len(pairsofparams)):
#             splitparams = pairsofparams[i].split('=')
#             if (len(splitparams)) == 2:
#                 param[splitparams[0]] = splitparams[1]
#     return param


if __name__ == '__main__':
    plugin.run()
