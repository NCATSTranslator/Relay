# import socket
# import pytest
# from django.db import connections, OperationalError
# from celery import Celery
#
# app = Celery('tr_sys')
# app.config_from_object('django.conf:settings', namespace='CELERY')
#
# @pytest.mark.healthcheck
# def test_rabbitmq_reachable():
#     import socket
#     try:
#         socket.create_connection(("localhost", 5672), timeout=5).close()
#     except Exception as e:
#         pytest.fail(f"RabbitMQ not reachable: {e}")
#
# @pytest.mark.healthcheck
# def test_celery_worker_ping(celery_worker_is_alive):
#     # Just accessing the fixture is enough — it fails if ping is empty
#     assert isinstance(celery_worker_is_alive, dict)
