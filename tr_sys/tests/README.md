# Autonomous Relay System (ARS)

The **Autonomous Relay System (ARS)** is developed on a Django web server, utilizing **Celery** for asynchronous task handling and **RabbitMQ** as the message broker. On the backend, a **MySQL** database is used to manage and persist records.

ARS interacts with a set of external services to post-process data received from its **Autonomous Relay Agents (ARAs)**. These services include a mix of live HTTP-based servers (e.g., *Appraiser* and *NodeNorm*) and an importable Python module (*Annotator*), which are invoked via HTTP requests and asynchronous calls, respectively.

Given this architecture, the following unit and integration tests were designed to assess the quality and robustness of the ARS system.

---

## Unit Testing

Several test cases were developed to validate individual Django model instances using isolated test data, which was created and cleaned up automatically within each test run. The **`factory_boy`** library was used to define dummy field values through a dedicated factory class, while a separate script provided **Pytest fixtures** to create and save these objects to the test database. The **`@pytest.mark.django_db`** decorator enabled database access during testing.

These tests verified:

- That Django model methods behaved as expected, including correct save operations
- Proper handling of data compression and decompression logic
- Relevant endpoints were accessible and returned successful GET responses

### Celery Task Testing

Celery functionality was tested without relying on RabbitMQ. The `notify_subscribers_task.apply_async` method was mocked to avoid triggering actual background jobs. A `test_message` object was created, updated to status `'D'` (Done), saved, and passed to the `notify_subscribers()` method. Assertions confirmed that `apply_async` was:

- Called exactly once
- Passed the expected arguments: the message’s primary key, code, and a dictionary with `'complete': True`

### Health Check Tests

A test was implemented to verify that the application's health check endpoint:

- Connected successfully to the MySQL database
- Properly executed a Celery task
- Returned an HTTP 200 status when both services were operational

A complementary test simulated a database failure by mocking Django’s `connections` object. The mock raised an `OperationalError` when `.cursor()` was called, simulating an outage. The test sent a GET request to the health check endpoint and confirmed the app returned a 500 status and an appropriate error message indicating a database failure.

### HTTP External Service Test

Given ARS's interaction with external HTTP services, a test was written to validate this behavior. The `canonize` function, which sends a list of CURIEs to the Node Normalizer service, was tested as follows:

- Mock tracer and span objects were created to support OpenTelemetry tracing
- The HTTP POST request and its response were mocked, returning `{"normalized": True}`
- The test verified that the expected result was returned
- The POST call was made exactly once
- No error attributes were recorded on the span

---

## Integration Testing

Integration test cases were developed to ensure the ARS API is operational and returns the expected results. These tests verified:

- That the ARS API exposes data on agents and actors
- A specific agent is consistently present in both datasets

### External Service Integration

Tests were also conducted to validate interactions with external services:

- Two live server endpoints were tested by sending real HTTP POST requests and asserting that responses matched expectations
- The Python-based annotator module was tested for asynchronous behavior:
  - Input was submitted
  - The pipeline was executed
  - Output was validated to ensure it returned a dictionary as expected for valid input

---

## Continuous Integration

All unit and integration tests are automatically executed for every pull request to the Relay GitHub repository. Tests are run inside an isolated **tox** virtual environment to ensure consistent and reliable results across different development setups.

---

## Technologies Used

- Python
- Django
- Celery
- RabbitMQ
- MySQL
- Pytest
- Factory Boy
- OpenTelemetry
- tox

