import asyncio
import json
from unittest.mock import Mock
from uuid import UUID

import httpx
import pytest
from pydantic.v1 import ValidationError

from vocode.streaming.action.default_factory import DefaultActionFactory
from vocode.streaming.action.parallel_search import (
    PARALLEL_SEARCH_URL,
    PARALLEL_USER_AGENT,
    ParallelFetchVocodeActionConfig,
    ParallelSearchVocodeActionConfig,
    WebFetchParameters,
)
from vocode.streaming.action.record_email import RecordEmailVocodeActionConfig
from vocode.streaming.action.worker import ActionsWorker
from vocode.streaming.agent.base_agent import GeneratedResponse, TranscriptionAgentInput
from vocode.streaming.agent.chat_gpt_agent import ChatGPTAgent
from vocode.streaming.models.actions import ActionConfig, FunctionCall
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.models.transcriber import Transcription
from vocode.streaming.models.transcript import Transcript
from vocode.streaming.utils.state_manager import AbstractConversationStateManager
from vocode.streaming.utils.worker import InterruptibleEvent, QueueConsumer


class MCPServer:
    """A deterministic HTTP MCP peer; the production MCP client remains in use."""

    def __init__(self):
        self.requests = []
        self.calls = []
        self.model_requests = []
        self.tools = ["web_search", "web_fetch"]
        self.mode = "success"
        self.started = asyncio.Event()

    async def handle(self, request):
        if str(request.url) == "https://model.example/v1/chat/completions":
            message = json.loads(request.content)
            self.model_requests.append(message)
            if any(m["role"] == "function" for m in message["messages"]):
                delta = {"content": "It is sunny."}
            else:
                delta = {
                    "function_call": {
                        "name": "action_web_search",
                        "arguments": json.dumps(
                            {"objective": "Current weather", "search_queries": ["current weather"]}
                        ),
                    }
                }
            chunk = {
                "id": "scripted-model",
                "object": "chat.completion.chunk",
                "created": 1,
                "model": "gpt-3.5-turbo-1106",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            return httpx.Response(
                200,
                content="data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n",
                headers={"Content-Type": "text/event-stream"},
            )
        self.requests.append(request)
        assert str(request.url) == "https://search.parallel.ai/mcp"
        assert request.headers["User-Agent"] == PARALLEL_USER_AGENT
        assert "authorization" not in request.headers
        if request.method == "GET":
            return httpx.Response(405)
        if request.method == "DELETE":
            return httpx.Response(200)
        message = json.loads(request.content)
        method = message["method"]
        if method == "notifications/initialized":
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test", "version": "1"},
            }
        elif method == "tools/list":
            result = {
                "tools": [{"name": name, "inputSchema": {"type": "object"}} for name in self.tools]
            }
        elif method == "tools/call":
            self.calls.append(message["params"])
            self.started.set()
            if self.mode == "wait":
                await asyncio.Event().wait()
            if self.mode == "http_error":
                return httpx.Response(503)
            if self.mode == "malformed":
                return httpx.Response(200, content="not json")
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Anonymous quota reached"
                            if self.mode == "quota"
                            else "Source https://example.org/weather: sunny, 18 C."
                        ),
                    }
                ],
                "isError": self.mode == "quota",
            }
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": message["id"], "result": result})


@pytest.fixture
def server(monkeypatch):
    server = MCPServer()
    transport = httpx.MockTransport(server.handle)
    # Observe the real SDK's HTTP request construction, including URL and headers.
    monkeypatch.setattr(httpx.AsyncClient, "_transport_for_url", lambda self, url: transport)
    monkeypatch.delenv("PARALLEL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert PARALLEL_SEARCH_URL == "https://search.parallel.ai/mcp"
    return server


def make_agent(**kwargs):
    config = ChatGPTAgentConfig(
        prompt_preamble="Use sources.", openai_api_key="model-test", **kwargs
    )
    return prepare_agent(ChatGPTAgent(config))


def prepare_agent(agent):
    class ConversationState(AbstractConversationStateManager):
        def using_input_streaming_synthesizer(self):
            return False

    agent.attach_transcript(Transcript())
    agent.attach_conversation_state_manager(ConversationState())
    agent.actions_consumer = QueueConsumer()
    agent.agent_responses_consumer = QueueConsumer()
    return agent


async def dispatch(agent, name="action_web_search", params=None, conversation_id="test"):
    if params is None:
        params = {"objective": "Current weather", "search_queries": ["example current weather"]}
    await agent.call_function(
        FunctionCall(name=name, arguments=json.dumps(params)),
        TranscriptionAgentInput(
            conversation_id=conversation_id,
            transcription=Transcription(message="What's the weather?", confidence=1, is_final=True),
        ),
    )
    item = agent.actions_consumer.input_queue.get_nowait()
    worker = ActionsWorker(agent.action_factory)
    worker.attach_conversation_state_manager(agent.conversation_state_manager)
    worker.consumer = QueueConsumer()
    await worker.process(item)
    result = worker.consumer.input_queue.get_nowait()
    consumed = []

    async def scripted_response(*args, **kwargs):
        # Script model output, but use the production transcript-to-model formatter.
        consumed.append(agent.get_chat_parameters())
        yield GeneratedResponse(message=BaseMessage(text="It is sunny."), is_interruptible=True)

    agent.generate_response = scripted_response
    await agent.process(result)
    assert consumed
    function_messages = [m for m in consumed[0]["messages"] if m["role"] == "function"]
    assert function_messages
    response = result.payload.action_output.response
    assert (response.content or response.error) in function_messages[-1]["content"]
    return result.payload.action_output.response


@pytest.mark.asyncio
async def test_fresh_agent_dispatches_search_and_fetch_to_model_context(server):
    agent = make_agent()
    assert {f["name"] for f in agent.functions} == {"action_web_search", "action_web_fetch"}
    response = await dispatch(agent)
    assert response.success and "https://example.org/weather" in response.content
    response = await dispatch(
        agent, "action_web_fetch", {"urls": ["https://example.org/weather"], "objective": "Weather"}
    )
    assert response.success and "18 C" in response.content
    methods = [json.loads(r.content)["method"] for r in server.requests if r.method == "POST"]
    assert methods.count("initialize") == 2
    assert methods.count("tools/list") == 2
    assert [call["name"] for call in server.calls] == ["web_search", "web_fetch"]
    assert server.calls[1]["arguments"]["urls"] == ["https://example.org/weather"]


@pytest.mark.asyncio
async def test_scripted_openai_stream_runs_normal_agent_tool_loop(server):
    agent = make_agent(base_url_override="https://model.example/v1/")
    await agent.process(
        InterruptibleEvent(
            payload=TranscriptionAgentInput(
                conversation_id="normal-loop",
                transcription=Transcription(message="Weather?", confidence=1, is_final=True),
            )
        )
    )
    worker = ActionsWorker(agent.action_factory)
    worker.attach_conversation_state_manager(agent.conversation_state_manager)
    worker.consumer = QueueConsumer()
    await worker.process(agent.actions_consumer.input_queue.get_nowait())
    await agent.process(worker.consumer.input_queue.get_nowait())
    assert len(server.model_requests) == 2
    assert {f["name"] for f in server.model_requests[0]["functions"]} == {
        "action_web_search",
        "action_web_fetch",
    }
    results = [m for m in server.model_requests[1]["messages"] if m["role"] == "function"]
    assert "https://example.org/weather" in results[0]["content"]
    responses = []
    while not agent.agent_responses_consumer.input_queue.empty():
        responses.append(agent.agent_responses_consumer.input_queue.get_nowait().payload)
    assert any(getattr(r.message, "text", None) == "It is sunny." for r in responses)


@pytest.mark.parametrize("actions", [None, [], [RecordEmailVocodeActionConfig()]])
def test_explicit_permissions_and_saved_choices(actions):
    agent = make_agent(actions=actions)
    assert agent.agent_config.actions == actions
    assert not agent.functions or [f["name"] for f in agent.functions] == ["action_record_email"]
    saved = ChatGPTAgentConfig(prompt_preamble="Saved", openai_api_key="test").json()
    restored = ChatGPTAgent(ChatGPTAgentConfig.parse_raw(saved))
    assert restored.agent_config.actions is None
    assert restored.functions is None


def test_explicit_factory_override_is_preserved():
    config = ChatGPTAgentConfig(prompt_preamble="Custom", openai_api_key="test")
    factory = Mock()
    agent = ChatGPTAgent(config, action_factory=factory)
    assert agent.action_factory is factory
    assert agent.functions is None
    assert config.actions is None
    assert ChatGPTAgent(config, action_factory=None).functions is None


def test_config_subclass_action_default_is_preserved():
    class CustomConfig(ChatGPTAgentConfig):
        actions: list[ActionConfig] = [RecordEmailVocodeActionConfig()]

    agent = ChatGPTAgent(CustomConfig(prompt_preamble="Custom", openai_api_key="test"))
    assert [f["name"] for f in agent.functions] == ["action_record_email"]


@pytest.mark.asyncio
async def test_disabled_actions_cannot_dispatch_web_search(server):
    agent = make_agent(actions=[])
    await agent.call_function(
        FunctionCall(name="action_web_search", arguments="{}"),
        TranscriptionAgentInput(
            conversation_id="disabled",
            transcription=Transcription(message="Search", confidence=1, is_final=True),
        ),
    )
    assert agent.actions_consumer.input_queue.empty()
    assert not server.requests
    with pytest.raises(Exception, match="not supported"):
        DefaultActionFactory([]).create_action(ParallelSearchVocodeActionConfig())


@pytest.mark.asyncio
async def test_conversation_ids_survive_followups_quota_and_interleaving(server):
    first = make_agent()
    # Sharing a factory must not share a conversation identifier.
    second = prepare_agent(ChatGPTAgent(first.agent_config, action_factory=first.action_factory))
    await asyncio.gather(
        dispatch(first, conversation_id="first"), dispatch(second, conversation_id="second")
    )
    first_id = first.conversation_state_manager.get_web_search_session_id()
    second_id = second.conversation_state_manager.get_web_search_session_id()
    assert UUID(first_id) != UUID(second_id)
    await dispatch(first, "action_web_fetch", {"urls": ["https://example.org/weather"]}, "first")
    server.mode = "quota"
    assert not (await dispatch(first, conversation_id="first")).success
    server.mode = "success"
    await dispatch(first, conversation_id="first")
    assert [c["arguments"]["session_id"] for c in server.calls[2:]] == [first_id] * 3
    assert {c["arguments"]["session_id"] for c in server.calls[:2]} == {first_id, second_id}
    first.attach_conversation_state_manager(AbstractConversationStateManager())
    await dispatch(first, conversation_id="reset")
    assert server.calls[-1]["arguments"]["session_id"] not in {first_id, second_id}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["http_error", "malformed", "quota"])
async def test_failures_return_to_agent_without_fallback(server, mode):
    server.mode = mode
    response = await dispatch(
        make_agent(actions=[ParallelSearchVocodeActionConfig(timeout_seconds=0.5)])
    )
    assert not response.success
    assert response.error
    assert len(server.calls) == 1


@pytest.mark.asyncio
async def test_missing_tool_returns_failure(server):
    server.tools = []
    response = await dispatch(make_agent())
    assert not response.success
    assert "unavailable" in response.error
    assert not server.calls


@pytest.mark.asyncio
async def test_timeout_is_bounded(server):
    server.mode = "wait"
    response = await dispatch(
        make_agent(actions=[ParallelSearchVocodeActionConfig(timeout_seconds=0.05)])
    )
    assert not response.success
    assert "timed out" in response.error


@pytest.mark.asyncio
async def test_cancellation_propagates(server):
    server.mode = "wait"
    task = asyncio.create_task(dispatch(make_agent()))
    await asyncio.wait_for(server.started.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=5)


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://example.org/file", "javascript:alert(1)"]
)
def test_fetch_only_accepts_http_urls(url):
    with pytest.raises(ValidationError):
        WebFetchParameters(urls=[url])
