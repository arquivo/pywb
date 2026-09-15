from warcio.timeutils import timestamp_to_datetime, datetime_to_iso_date
from six.moves.urllib.parse import urlsplit
from six.moves.urllib.robotparser import RobotFileParser
import re
import time
import requests


# ============================================================================
# Header Exclusions
# ============================================================================
class ExcludeSpecificHeaders(object):
    def __init__(self, exclude_headers=None):
        self.exclude_headers = [x.lower() for x in exclude_headers]

    def __call__(self, header):
        if header[0].lower() in self.exclude_headers:
            return None

        return header


# ============================================================================
class ExcludeHttpOnlyCookieHeaders(object):
    HTTPONLY_RX = re.compile(';\\s*HttpOnly\\s*(;|$)', re.I)

    def __call__(self, header):
        name = header[0].lower()
        if name == 'cookie':
            return None

        if (name == 'set-cookie' and
            self.HTTPONLY_RX.search(header[1])):
            return None

        return header


# ============================================================================
# Revisit Policy
# ============================================================================
class WriteRevisitDupePolicy(object):
    def __call__(self, cdx, params):
        dt = timestamp_to_datetime(cdx['timestamp'])
        return ('revisit', cdx['url'], datetime_to_iso_date(dt))


# ============================================================================
class SkipDupePolicy(object):
    def __call__(self, cdx, params):
        if cdx['url'] == params['url']:
            return 'skip'
        else:
            return 'write'


# ============================================================================
class WriteDupePolicy(object):
    def __call__(self, cdx, params):
        return 'write'


# ============================================================================
# Skip Record Filters
# ============================================================================
class SkipDefaultFilter(object):
    def skip_request(self, path, req_headers):
        if req_headers.get('Recorder-Skip') == '1':
            return True

        return False

    def skip_response(self, path, req_headers, resp_headers, params):
        if resp_headers.get('Recorder-Skip') == '1':
            return True

        return False


# ============================================================================
class CollectionFilter(SkipDefaultFilter):
    def __init__(self, accept_colls):
        self.rx_accept_map = {}

        if isinstance(accept_colls, str):
            self.rx_accept_map = {'*': re.compile(accept_colls)}

        elif isinstance(accept_colls, dict):
            for name in accept_colls:
                self.rx_accept_map[name] = re.compile(accept_colls[name])

    def skip_response(self, path, req_headers, resp_headers, params):
        if super(CollectionFilter, self).skip_response(path, req_headers,
                                                       resp_headers, params):
            return True

        path = path[1:].split('/', 1)[0]

        rx = self.rx_accept_map.get(path)
        if not rx:
            rx = self.rx_accept_map.get('*')

        if rx and not rx.match(resp_headers.get('Warcserver-Source-Coll', '')):
            return True

        return False


# ============================================================================
class RobotsExclusionFilter(SkipDefaultFilter):
    """Skip persisting (but not serving) responses disallowed for
    ``match_user_agent`` by the target site's robots.txt.

    ``match_user_agent`` is the (typically short) crawler token checked
    against the site's ``Disallow``/``Allow`` rules. ``fetch_user_agent``
    is the (typically longer, more descriptive) ``User-Agent`` actually
    sent when fetching ``robots.txt``, so the site's logs are consistent
    with whatever identity is used for the rest of the record-mode
    requests. If ``fetch_user_agent`` is not given, ``match_user_agent``
    is used for both.
    """

    ROBOTS_TIMEOUT = 10
    CACHE_TTL = 3600

    def __init__(self, match_user_agent, fetch_user_agent=None, cache_ttl=CACHE_TTL):
        self.match_user_agent = match_user_agent
        self.fetch_user_agent = fetch_user_agent or match_user_agent
        self.cache_ttl = cache_ttl
        # in-memory, per-process cache: not shared across uwsgi/gunicorn
        # workers or separate replicas, so each worker refetches robots.txt
        # independently (up to N fetches per host per cache_ttl for N
        # workers). Acceptable for low-QPS record-mode traffic; would need
        # a shared backend (e.g. Redis, as already used for dedup) to avoid
        # duplicate fetches across processes.
        self.parser_cache = {}

    def _get_parser(self, url):
        parts = urlsplit(url)
        host_key = (parts.scheme, parts.netloc)

        cached = self.parser_cache.get(host_key)
        now = time.time()
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        parser = RobotFileParser()
        robots_url = '{0}://{1}/robots.txt'.format(parts.scheme, parts.netloc)

        try:
            res = requests.get(robots_url,
                               headers={'User-Agent': self.fetch_user_agent},
                               timeout=self.ROBOTS_TIMEOUT)
            if res.status_code in (401, 403):
                parser.disallow_all = True
                parser.modified()
            elif res.status_code >= 400:
                # no robots.txt present -> nothing disallowed
                parser.allow_all = True
                parser.modified()
            else:
                parser.parse(res.text.splitlines())
        except Exception:
            # fail open: a flaky/unreachable robots.txt should not block
            # an interactively-requested capture. (Note: RobotFileParser
            # treats an un-parsed parser as disallow-all, so this must be
            # set explicitly rather than left as a no-op.)
            parser.allow_all = True
            parser.modified()

        self.parser_cache[host_key] = (now, parser)
        return parser

    def skip_response(self, path, req_headers, resp_headers, params):
        if super(RobotsExclusionFilter, self).skip_response(path, req_headers,
                                                             resp_headers, params):
            return True

        url = params.get('url')
        if not url:
            return False

        parser = self._get_parser(url)
        if not parser.can_fetch(self.match_user_agent, url):
            return True

        return False


# ============================================================================
class SkipRangeRequestFilter(SkipDefaultFilter):
    def skip_request(self, path, req_headers):
        if super(SkipRangeRequestFilter, self).skip_request(path,
                                                            req_headers):
            return True

        range_ = req_headers.get('Range')
        if range_ and not range_.lower().startswith('bytes=0-'):
            return True

        return False


