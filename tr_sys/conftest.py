
import pytest
from pytest_factoryboy import register
from unittest.mock import MagicMock
from factories import AgentFactory, ActorFactory, MessageFactory, ChannelFactory

register(AgentFactory)
register(ActorFactory)
register(ChannelFactory)
register(MessageFactory)

@pytest.fixture
def new_user(db, user_factory):
    user = user_factory.create()
    return user


@pytest.fixture
def test_agent(db, agent_factory):
    agent = agent_factory.create()
    return agent

@pytest.fixture
def test_channel(db, channel_factory):
    channel = channel_factory.create()
    return channel


@pytest.fixture
def test_actor(db, actor_factory):
    actor = actor_factory.create()
    return actor

@pytest.fixture
def test_message(db, message_factory):
    message = message_factory.create()
    return message

@pytest.fixture
def mock_span():
    """
    creating mock object that simulate an OpenTelemetry Span
    """
    span = MagicMock()
    span.set_attribute = MagicMock()
    return span

@pytest.fixture
def mock_tracer(mock_span):
    """
    creating mock object that simulate an OpenTelemetry trace
    """
    tracer = MagicMock()
    # Create a mock context manager for start_as_current_span
    tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
    tracer.start_as_current_span.return_value.__exit__.return_value = None
    return tracer


# RABBITMQ_IMAGE = "rabbitmq:3.13"
# RABBITMQ_PORT = 5672
# BROKER_URL = "amqp://guest:guest@localhost:5672//"
#
# # connect to rabbitmq via TCP and test its functionality
# @pytest.fixture(scope="session")
# def start_rabbitmq_container():
#     """
#         Start a RabbitMQ Docker container for the test session.
#     """
#     client = docker.from_env() #create a docker client in python so the code can control docker images/containers
#     try:
#         #start a RabbitMQ container
#         container = client.containers.run(
#             RABBITMQ_IMAGE,
#             detach=True,
#             ports={"5672/tcp": RABBITMQ_PORT},
#             name="test-rabbitmq",
#             remove=True,
#         )
#     except docker.errors.APIError as e:
#         pytest.fail(f"Failed to start RabbitMQ container: {e}")
#
#     # Wait for RabbitMQ port to open
#     for _ in range(10):
#         try:
#             #check if rabbitmq is actually up and accept TCP connection to localhost
#             socket.create_connection(("localhost", RABBITMQ_PORT), timeout=2).close()
#             break
#         except socket.error:
#             time.sleep(2)
#     else:
#         container.stop()
#         pytest.fail("RabbitMQ did not start in time")
#
#     yield  # Run tests
#     container.stop()
#
# # start celery worker and test its responsiveness
# @pytest.fixture(scope="session")
# def start_celery_worker(start_rabbitmq_container):
#     """
#     Start a Celery worker in the background for the duration of the test session.
#     """
#     worker = subprocess.Popen(
#         [sys.executable, "-m", "celery", "-A", "tr_sys", "worker", "--loglevel=info"],
#         stdout=subprocess.PIPE,
#         stderr=subprocess.PIPE,
#         preexec_fn=os.setsid  # Ensures we can kill the entire process group
#     )
#     time.sleep(10)  # Give Celery worker time to fully start
#     yield  # Test session runs here
#     # Graceful cleanup
#     os.killpg(os.getpgid(worker.pid), signal.SIGTERM)
#     worker.wait()
#
# @pytest.fixture(scope="session")
# def celery_worker_is_alive(start_celery_worker):
#     """
#     Ping Celery workers to ensure at least one is alive & responsive.
#     """
#     app = Celery('tr_sys')
#     app.conf.broker_url = BROKER_URL
#
#     inspector = app.control.inspect(timeout=5)
#     for i in range(5):  # Retry ping a few times in case it's not up yet
#         responses = inspector.ping()
#         if responses:
#             return responses
#         time.sleep(2)
#
#     pytest.fail("Celery worker did not respond to ping after retries.")



# connect to mysql DB









#
# @pytest.fixture(scope="session", autouse=True)
# def start_rabbitMQ():
#     client=docker.from_env()
#     container = client.containers.run(
#         "rabbitmq:3.13",  # or any specific version you prefer
#         detach=True,
#         ports={"5672/tcp": 5672},
#         name="test-rabbit",
#         remove=True,
#     )
#     time.sleep(10) # giving rabbitmq time to start
#     yield
#     container.stop()



# @pytest.fixture(autouse=True)
# def mock_send_message():
#     with patch('tr_ars.tasks.send_message.delay') as mock_task:
#         yield mock_task

# @pytest.fixture(params=["firefox"], scope="class")
# def driver_init(request):
#     if request.param == "chrome1920":
#         options = webdriver.ChromeOptions()
#         options.add_argument("--headless")
#         options.add_argument("--window-size=1920,1080")
#         web_driver = webdriver.Chrome(options=options)
#         request.cls.browser = "Chrome1920x1080"
#     if request.param == "chrome411":
#         options = webdriver.ChromeOptions()
#         options.add_argument("--headless")
#         options.add_argument("--window-size=411,823")
#         web_driver = webdriver.Chrome(options=options)
#         request.cls.browser = "Chrome411x823"
#     if request.param == "firefox":
#         options = webdriver.FirefoxOptions()
#         options.add_argument("--headless")
#         web_driver = webdriver.Firefox(options=options)
#         request.cls.browser = "Firefox"
#     request.cls.driver = web_driver
#     yield
#     web_driver.close()
