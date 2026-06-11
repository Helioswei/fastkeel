# tests/test_contrib/test_llm.py
import pytest
from pydantic import BaseModel

from fastkeel.core.config import Config


class TestLLMClientInit:
    """Test LLMClient initialization."""

    def test_init_with_minimal_config(self):
        from fastkeel.contrib.llm import LLMClient
        config = Config(llm_api_key="sk-test")
        client = LLMClient(config)
        assert client is not None
        assert client.max_retries == 3
        assert client.semaphore._value == 10

    def test_init_with_custom_values(self):
        from fastkeel.contrib.llm import LLMClient
        config = Config(
            llm_api_key="sk-custom",
            llm_api_base="https://custom.api.com",
            llm_model="custom-model",
            llm_max_retries=5,
            llm_rate_limit=20,
        )
        client = LLMClient(config)
        assert client.api_base == "https://custom.api.com"
        assert client.model == "custom-model"
        assert client.max_retries == 5
        assert client.semaphore._value == 20


class TestLLMChat:
    """Test LLMClient.chat() with mocked HTTP."""

    @pytest.fixture
    def client(self):
        from fastkeel.contrib.llm import LLMClient
        return LLMClient(Config(llm_api_key="sk-test"))

    @pytest.fixture
    def mock_success(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mocker.patch("httpx.AsyncClient.post", return_value=mock_response)
        return mock_response

    @pytest.mark.asyncio
    async def test_chat_returns_content(self, client, mock_success):
        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_chat_retries_on_429(self, mocker):
        from fastkeel.contrib.llm import LLMClient
        client = LLMClient(Config(llm_api_key="sk-test", llm_max_retries=2))

        # First call 429, second succeeds
        fail_response = mocker.Mock()
        fail_response.status_code = 429

        success_response = mocker.Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "choices": [{"message": {"content": "Retried!"}}]
        }

        mock_post = mocker.patch("httpx.AsyncClient.post")
        mock_post.side_effect = [fail_response, success_response]

        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "Retried!"
        assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_chat_retries_on_5xx(self, mocker):
        from fastkeel.contrib.llm import LLMClient
        client = LLMClient(Config(llm_api_key="sk-test", llm_max_retries=1))

        fail = mocker.Mock()
        fail.status_code = 502

        success = mocker.Mock()
        success.status_code = 200
        success.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }

        mock_post = mocker.patch("httpx.AsyncClient.post")
        mock_post.side_effect = [fail, success]

        result = await client.chat([{"role": "user", "content": "Hi"}])
        assert result == "OK"

    @pytest.mark.asyncio
    async def test_chat_raises_on_max_retries_exceeded(self, mocker):
        from fastkeel.contrib.llm import LLMClient
        client = LLMClient(Config(llm_api_key="sk-test", llm_max_retries=2))

        error_response = mocker.Mock()
        error_response.status_code = 503
        error_response.text = "Service Unavailable"

        mock_post = mocker.patch("httpx.AsyncClient.post", return_value=error_response)

        with pytest.raises(RuntimeError, match="API error: HTTP 503"):
            await client.chat([{"role": "user", "content": "Hi"}])
        assert mock_post.call_count == 3  # initial + 2 retries


class TestLLMChatStructured:
    """Test structured output parsing."""

    @pytest.mark.asyncio
    async def test_chat_structured_returns_model(self, mocker):
        from fastkeel.contrib.llm import LLMClient
        client = LLMClient(Config(llm_api_key="sk-test"))

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Alice", "age": 30}'}}]
        }
        mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        class Person(BaseModel):
            name: str
            age: int

        result = await client.chat_structured(
            [{"role": "user", "content": "Tell me about someone"}],
            Person,
        )
        assert isinstance(result, Person)
        assert result.name == "Alice"
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_chat_structured_raises_on_bad_json(self, mocker):
        from fastkeel.contrib.llm import LLMClient
        client = LLMClient(Config(llm_api_key="sk-test"))

        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "not valid json"}}]
        }
        mocker.patch("httpx.AsyncClient.post", return_value=mock_response)

        class Person(BaseModel):
            name: str
            age: int

        with pytest.raises(ValueError, match="Failed to parse structured output"):
            await client.chat_structured([{"role": "user", "content": "Hi"}], Person)
