import requests
from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

# DEFAULT_HOST = 'https://ars-prod.transltr.io'
# def test_response():
#     response = requests.get(DEFAULT_HOST+"/ars/api/agents")
#     print(response)
#     response_body = response.json()
#     print(response_body)
#     assert (response_body[0])["fields"]["name"] == "ara-aragorn"
