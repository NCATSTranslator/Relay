from tr_smartapi_client.smart_api_discover import *
import unittest

"""
    Run via:
        python tr_sys/manage.py test tr_smartapi_client
"""

class SmartApiDiscovererSpec(unittest.TestCase):
    def setUp(self):
        print("setting up")

    def test_get_url(self):
        """"""
        url=SmartApiDiscover().urlServer("infores:aragorn-ranker")
        print("urlServer={}".format(url))
        assert(isinstance(url,str) and len(url) > 0)

    def test_get_endpoint(self):
        """"""
        endpoint=SmartApiDiscover().endpoint("infores:cam-kp")
        assert(isinstance(endpoint,str) and len(endpoint) > 0)

    def test_get_params(self):
        """"""
        params=SmartApiDiscover().params("infores:cam-kp")
        assert(isinstance(params,str) and len(params) > 0)
