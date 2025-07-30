"""Tests of the agent, using differing levels of mocking out the external world.
"""
import datetime
import os
from types import SimpleNamespace
from os.path import join
import pytest
from unittest.mock import patch
from orca_agent.slack_client import MessageInfo
import k8stools.mock_tools as mock_tools
from orca_agent.runbook import get_runbook_text # we'll use the real runbook tool

REAL_MODEL = "openai:gpt-4.1"

MESSAGE_CONTENT=\
"""**Firing**

Value: A=2, C=1
Labels:
- alertname = CrashLoopBackOff
- container = ad
- grafana_folder = k8s alerts
- pod = ad-647b4947cc-s5mpm
Annotations:
- description = At least one pod is in the crash loop backoff state. See the labels for the pod and container.
- runbook_url = <https://github.com/BenedatLLC/otel-demo/blob/main/RCA/CrashLoop.md>
- summary = Pods are in a crash loop!
Source: <http://localhost:3000/grafana/alerting/grafana/fepoho3wnrfuod/view?orgId=1>
Silence: <http://localhost:3000/grafana/alerting/silence/new?alertmanager=grafana&amp;matcher=alertname%3DCrashLoopBackOff&amp;matcher=container%3Dad&amp;matcher=grafana_folder%3Dk8s+alerts&amp;matcher=pod%3Dad-f4fd4fb69-r5w9b&amp;orgId=1>
Dashboard: <http://localhost:3000/grafana/d/cepoet44w4wzke?orgId=1>
Panel: <http://localhost:3000/grafana/d/cepoet44w4wzke?orgId=1&amp;viewPanel=1>
"""

MESSAGE_TIME="2025-07-26 23:04:30.373719+00:00"
EXAMPLE_ALERT_MESSAGE = MessageInfo(
    timestamp=datetime.datetime.fromisoformat(MESSAGE_TIME),
    ts=MESSAGE_TIME,
    thread_ts="2025-07-26 23:04:30.373719+00:00",
    user_name="Grafana notifications",
    is_a_bot=True,
    content=MESSAGE_CONTENT,
    replies=[]
)
LATER_THAN=EXAMPLE_ALERT_MESSAGE.timestamp - datetime.timedelta(minutes=1)

@pytest.fixture(autouse=True)
def mock_get_conversations():
    """Mock conversations.get_conversations() to return EXAMPLE_ALERT_MESSAGE on first call, 
    then empty list on subsequent calls within each test."""
    call_count = 0
    
    def mock_get_conversations_fn(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [EXAMPLE_ALERT_MESSAGE]
        else:
            return []
    
    with patch('orca_agent.conversations.get_conversations', side_effect=mock_get_conversations_fn) as mock:
        yield mock
        # Reset call count after each test
        call_count = 0

@pytest.fixture(autouse=True)
def mock_send_message_to_channel():
    """Mock slack_client.send_message_to_channel to print the message and check for
    'OOMKilled' and '137'. If both are found, raises StopAgentLoop exception."""
    
    def mock_send_message_fn(channel_name: str, markdown_text: str, thread_ts=None):
        print(f"Mock sending message to channel '{channel_name}':")
        print(f"Thread TS: {thread_ts}")
        print(f"Message content:\n{markdown_text}")
        print("-" * 50)
        
        # Check for both 'OOMKilled' and '137' in the message
        if 'OOMKilled' in markdown_text and '137' in markdown_text:
            print("Found 'OOMKilled' and '137' in message - raising StopAgentLoop exception")
            from orca_agent.agent import StopAgentLoop
            raise StopAgentLoop("Found OOMKilled and exit code 137 in message")
    
    with patch('orca_agent.slack_client.send_message_to_channel', side_effect=mock_send_message_fn) as mock:
        yield mock


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("OPENAI_API_KEY") is None or os.getenv("OPENAI_API_KEY")=="",
                    reason="OPENAI_API_KEY environment variable not set")
async def test_agent_with_real_llm_and_mocked_tools():
    """This test case will run the agent using a real llm, but mocked tools. The mocked tools should
    correspond to a real scenario, so we should get something useful in response."""
    from orca_agent.agent import StopAgentLoop, make_agent, check_loop
    tools = [get_runbook_text,] + mock_tools.TOOLS
    args = SimpleNamespace(
        alert_slack_channel='alerts',
        agent_slack_user='orca-alerts',
        alert_slack_user='Grafana notifications',
        debug = False, # test to true if yo are trying to debug this test
        dry_run=False,
        )
    agent = make_agent(model=REAL_MODEL, tools=tools)
    await check_loop(agent, later_than=LATER_THAN, args=args)


@pytest.mark.asyncio
async def test_agent_with_mocked_llm_and_mocked_tools(tmp_path):
    """This test case will run the agent using a mocked llm and  mocked tools.
    The pydantic TestModel will call all the tools."""
    from orca_agent.agent import StopAgentLoop, make_agent, check_loop
    def get_runbook_text(url: str) -> str:
        """Return the runbook at the specified URL"""
        return (f"This is the mocked runbook at {url}"
                "OOMKilled and 137 are expected in the output")
    
    tools = [get_runbook_text,] + mock_tools.TOOLS
    args = SimpleNamespace(
        alert_slack_channel='alerts',
        agent_slack_user='orca-alerts',
        alert_slack_user='Grafana notifications',
        check_time_file = join(tmp_path, 'check_time.txt'),
        debug = False, # set to True if you are trying to debug this test
        dry_run=False,
        )
    from pydantic_ai.models.test import TestModel
    
    agent = make_agent(model='test', tools=tools)
    m = TestModel()
    with agent.override(model=m):
        await check_loop(agent, later_than=LATER_THAN, args=args)