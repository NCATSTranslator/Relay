
from tr_smartapi_client.smart_api_discover import SmartApiDiscover

class Actorconf:
    def __init__(self, inforesid,  name, path, method, params) -> None:
        self._inforesid = inforesid
        self._name = name
        self._path = path
        self._method = method
        self._params = params

    def inforesid(self):
        return self._inforesid

    def name(self):
        return self._name

    def path(self):
        return self._path

    def method(self):
        return self._method

    def params(self):
        return self._params

def urlRemoteFromInforesid(inforesid):
    urlServer=SmartApiDiscover().urlServer(inforesid)
    if urlServer is not None:
        endpoint=SmartApiDiscover().endpoint(inforesid)
        params=SmartApiDiscover().params(inforesid)
        return (urlServer +
                (("/"+endpoint) if endpoint is not None else "") +
                (("?"+params) if params is not None else "")) if urlServer is not None else None
    return None

