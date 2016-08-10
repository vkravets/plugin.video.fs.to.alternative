import urllib


class FsUa:
    def __init__(self, plugin=None, client=None):
        self.plugin = plugin
        self.client = client

    def get_url_with_sort_by(self, url, section, start, view_mode):
        sort_by = self.plugin.get_setting("Sort by")
        sort_by_map = {'0': 'new', '1': 'rating', '2': 'year', '3': 'popularity', '4': 'trend'}

        separator = '?'
        if separator in url:
            separator = '&'

        request_params = {
            'view': view_mode,
            'sort': sort_by_map[sort_by],
            'page': start
        }
        return url + self.get_filters(section) + separator + urllib.urlencode(request_params)

    def get_filters(self, section):
        filter_params = []
        ret = ''
        section_settings = {
            'video': ['mood', 'vproduction', 'quality', 'translation'],
            'audio': ['genre', 'aproduction']
        }
        for settingId in section_settings[section]:
            setting = self.plugin.get_setting(settingId)
            if setting != 'Any':
                filter_params.append(setting)
        if len(filter_params) > 0:
            ret = '/fl_%s/' % ('_'.join(filter_params))

        return ret

    def poster(self, src):
        return self.image(src, '1')

    def thumbnail(self, src):
        return self.image(src, '6')

    def image(self, src, quality):
        src = src.split('/')
        src[-2] = quality

        return self.client.get_full_url('/'.join(src))
