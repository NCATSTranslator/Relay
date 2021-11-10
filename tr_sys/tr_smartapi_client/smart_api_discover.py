
import logging
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import json
import yaml
import time

"""
    getpath: Collect a value from a hierarchical json path without throwing exceptions.
"""

def getpath_impl(j, fields, i):
    if(j is None or i>=len(fields)):
        return j
    field = fields[i]
    jNext = j[field] if field in j else None
    return getpath_impl(jNext, fields, i+1)

def getpath(j, fields):
    return getpath_impl(j, fields, 0)

"""
    UrlMapSmartApiFetcher: Fetches TRAPI service url configuration from the servers: field in smart-api.info.

    Presumes that TRAPI services have registered paths in the way the TRAPI specification recommends, so that
    the servers: field does not contain a method name such as /query.

    This class has no responsibility for caching.  Every method call regenerates all entries.  We expect the
    caller to cache.  Currently the caller is SmartApiDiscoverer.

    Allows variation according to TR_ENV via the "maturity" field.
"""

urlSmartapi = "https://smart-api.info"
secsTimeout = 5

class UrlMapSmartApiFetcher(object):
    def __init__(self) -> None:
        super().__init__()
    
    def _irhits_from_res(self, j):
        for hit in j["hits"]:
            _id = getpath(hit,["_id"])
            date_created = getpath(hit,["_meta", "date_created"])
            date_updated = getpath(hit,["_meta", "last_updated"])
            title = getpath(hit, ["info", "title"])
            #info = getpath(hit, ["info"])
            x_trapi = getpath(hit, ["info", "x-trapi"])
            x_trapi_version = getpath(hit, ["info", "x-trapi", "version"])
            team = getpath(hit, ["info", "x-translator", "team"])
            infores = getpath(hit, ["info", "x-translator", "infores"])
            servers = getpath(hit, ["servers"])
            if servers is not None:
                for server in servers:
                    maturity = getpath(server, ["x-maturity"])
                    urlServer = getpath(server, ["url"])
                    if x_trapi_version is not None:
                        d = {
                            "infores":infores,
                            "urlServer":urlServer,
                            "maturity":maturity,
                            "_id":_id,
                            "date_updated":date_updated
                            } #,team,title,x_trapi_version]
                        yield d

    def _key_of_irhit(self, irhit):
        return irhit["infores"] if "infores" in irhit else None

    def _newer(self, irhit1, irhit2):
        # Assumes lexicographically comparable date format: 2021-11-04T07:06:04.827864+00:00
        return irhit1["date_updated"] > irhit2["date_updated"]

    def _by_infores_latest(self, j, maturity):
        byIrid = {}
        for irhit in self._irhits_from_res(j):
            if maturity == irhit["maturity"]:
                key = self._key_of_irhit(irhit)
                if key is not None:
                    irhit0 = byIrid[key] if key in byIrid else None
                    if irhit0 is None or self._newer(irhit, irhit0):
                        byIrid[key] = irhit
        return byIrid

    def get_map(self, maturity):
        #try:
            s = requests.Session()

            retries = Retry(total=5,
                            backoff_factor=0.5,
                            status_forcelist=[ 500, 502, 503, 504 ])
                            # Parameter definitions at:
                            #   https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html#module-urllib3.util.retry

            s.mount('http://', HTTPAdapter(max_retries=retries))
            m = {}
            urlRequest = "{}/api/query?q=tags.name:translator&size=150&fields=_meta,info,servers".format(urlSmartapi)
            res = s.get(urlRequest, timeout=secsTimeout)
            if not res.ok:
                logging.warn("status {} for {}".format(res.status_code, urlRequest))
                return False
            j = res.json()
            for irid, irhit in self._by_infores_latest(j, maturity).items():
                m[irid] = irhit
            #    logging.info("found 3 {} => {}".format(irid, irhit))
            return m
        #except (Exception, ArithmeticError) as ex:
        #    logging.error("ruh roh ex={}".format(ex))
        #    return False

import os

"""
    UrlConfigLegacy: Maps inforesid to a url in the style of the "servers" field of swagger/openapi/smartapi.
    
    Provided for purposes of pushing code without breaking any services not yet registered
    on smart-api with the required x-maturity field.  Once all services are registered on smart-api with
    x-maturity, UrlConfigLegacy should be deleted.

    UrlConfigLegacy is not a way for the ARS to avoid a successful request to smart-api.info in order
    to be ready to serve requests.
"""

class UrlConfigLegacy:
    def __init__(self) -> None:
        self._path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "url-config-legacy.yaml")

    def get_map(self, maturity):
        f = open(self._path)
        j = {}
        with open(self._path, "r") as stream:
            try:
                j=yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        return j
        # TODO? return j[maturity] if maturity in j else {}

"""
    HttpclientConfig: Maps inforesid to various attributes necessary for making a service call.

    Backed by the file config/config.yaml.  Uses a field httpclients: so that the file could be amended
    with other kinds of configuration with this class given a name with broader scope.

    Currently does not allow variation by TR_ENV.
"""
class HttpclientConfig:
    def __init__(self) -> None:
        self._path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "config.yaml")

    def get_map(self, maturity):
        f = open(self._path)
        j = {}
        with open(self._path, "r") as stream:
            try:
                j=yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        logging.info("HttpclientConfig j={}".format(json.dumps(j)))
        return j["httpclients"] if "httpclients" in j else {}


"""
    SmartApiDiscoverer: Responsible for combining HttpclientConfig, UrlConfigLegacy, and UrlMapSmartApiFetcher.

    Refreshes between initial failures every secsTimeToLive seconds.

    Refreshes between success every secsTimeToLive seconds.

    Currently does not allow variation by TR_ENV.
"""

secsTimeToLive = 60*60
secsBetweenRetries = 30

class SmartApiDiscoverer:

    def __init__(self) -> None:
        self._maturity = os.getenv("TR_ENV") if os.getenv("TR_ENV") is not None else "production"
        self._config = HttpclientConfig()
        self._config_legacy = UrlConfigLegacy()
        self._urlmap_fetcher = UrlMapSmartApiFetcher()

        self._t_next_refresh = time.time()
        self._map_legacy = self._config_legacy.get_map(self._maturity)
        self._map_fixed = self._config.get_map(self._maturity)
        self._map_dynamic = {}
        #logging.info("set map legacy {}".format(self._map))
        super().__init__()
    
    def ensure(self):
        if time.time() >= self._t_next_refresh:
            map = self._urlmap_fetcher.get_map(self._maturity)
            if map is not None:
                self._map_dynamic = map
                logging.info("set map dynamic")
                self._t_next_refresh = time.time() + secsTimeToLive
            else:
                logging.warn("*** map_dynamic: Could not fetch from smart-api")
                self._t_next_refresh = time.time() + secsBetweenRetries

    def urlServer(self, inforesid):
        self.ensure()
        u = (self._map_dynamic[inforesid] if inforesid in self._map_dynamic else
            {"urlServer":self._map_legacy[inforesid]} if inforesid in self._map_legacy else {})
        return u["urlServer"] if "urlServer" in u else None

    def endpoint(self, inforesid):
        m = self._map_fixed[inforesid] if inforesid in self._map_fixed else {}
        u = m["endpoint"] if "endpoint" in m else None
        return u

    def params(self, inforesid):
        m = self._map_fixed[inforesid] if inforesid in self._map_fixed else {}
        u = m["params"] if "params" in m else None
        return u


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

"""
    SmartApiDiscover: Singleton of SmartApiDiscoverer.  All clients should use the singleton to take
    advantage of proper caching.
"""

class SmartApiDiscover(SmartApiDiscoverer, metaclass=Singleton):
    pass

# TODO: cache to reduce load on smart-api

