"""
Agent creation for orca-agent using pydantic.ai.
"""
import os
import sys
import argparse
import datetime
from os.path import exists
import logging
import asyncio
from typing import Optional
from .slack_client import send_message_to_channel
from .conversations import get_conversations

# TODO: add tools for get_services and get_rdeployments
SYSTEM_PROMPT =\
"""You are an automated assistant for monitoring alerts. You will be given a Grafana alert message that
was sent to Slack along with any replies. Construct a reply to the alert message that provides an explanation
of the alert message and debugging tips. Please be as specific as possible. Include any specific pods, containers,
deployments, and errors mentioned in the alert.

Be sure to mention where and how you obtained the information you used in the response, including tool calls and their associated kubectl calls, if any.
This will help users to understand how they can debug this issue themselves in the future. Don't just tell the user about
available commands, but run them and analyze the outputs, if an associated tool is available.

# Kubernetes Tools
Be sure to use the provided tools to obtain any additional information from the kubernetes cluster regarding any affected
pods. Use this to make your response relevant to the specific issue in the alert and provide more specific guidance.
In particular, the following tools will be helpful in understanding the state of the system:

* get_namespaces - get a list of namespaces, like `kubectl get namespace`
* get_pod_summaries - get a list of pods, like `kubectl get pods`
* get_pod_container_statuses - return the status for each of the container in a pod
* get_pod_events - return the events for a pod
* get_pod_spec - retrieves the spec for a given pod
* get_logs_for_pod_and_container - retrieves logs from a pod and container

# Runbooks
If the alert has a url for a runbook, use the provided tool `get_runbook_text` to retrieve the text of the runbook and use it to
improve your response.

# Retrieval error handling
If the alert mentions a `DatasourceError`, check whether this is a problem retrieving metrics from Prometheus or another
data source rather the problem associated with the original alert. If this is the case, make that clear in your
explanation.

# Output format
Write your reply using Markdown formatting. Don't use tables, as they aren't supported by Slack's markdown.
"""

def make_agent(model: str, tools:Optional[list]=None, instrument:bool=False):
    """
    Create and return a pydantic.ai Agent with access to runbook and Slack tools.

    Parameters
    ----------
    model : str
        Name of the model.
    tools : Optional[list[Tool]]
        If specified, use the provides tool (e.g. for mocking the real tools). The most common case is to leave
        this unspecified, which will include the tools from k8stools and the runbook retriever. 
    instrument : bool
        Set to True to automatically instrument with OpenTelemetry,

    Returns
    -------
    Agent
        A configured pydantic.ai Agent instance.
    """
    from pydantic_ai.agent import Agent
    from k8stools.k8s_tools import TOOLS
    from .runbook import get_runbook_text
    if tools is None:
        tools = [get_runbook_text,] + TOOLS
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        instrument=instrument
    )

class StopAgentLoop(Exception):
    pass


async def check_loop(agent, later_than:datetime.datetime, args):
    """This is the main loop of the agent. In each iteration,
    we check for new alerts. For each alert found, we call the agent and
    then send the response.
    
    If we receive a StopAgentLoop exception, we exit early.
    """
    from .pydantic_utils import pp_run_result
    logging.info(f"Entering main loop with later_than={later_than}")
    try:
        while True:
            next_later_than = datetime.datetime.now()
            sent_cnt = 0
            logging.info(f"Checking for conversations since {later_than}")
            conversations = get_conversations(
                args.alert_slack_user, args.agent_slack_user,
                args.alert_slack_channel, limit=100,
                later_than=later_than
            )
            logging.info(f"Found {len(conversations)} messages")
            for message in conversations:
                input = message.markdown()
                logging.info(f"Calling agent with input of length {len(input)}")
                result = await agent.run(input)
                if args.debug:
                    pp_run_result(result)
                if not args.dry_run:
                    send_message_to_channel(args.alert_slack_channel, result.output, message.thread_ts)
                    logging.info(f"Send message of length {len(result.output)} to channel {args.alert_slack_channel}")
                else:
                    logging.info(f"[DRY RUN] Would send message of length {len(result.output)} to channel {args.alert_slack_channel}")
                    print(f"{'='*15} Output from agent {'='*15}")
                    print(result.output + '\n')
                    raise StopAgentLoop("[DRY RUN] Stopping agent loop after one message")
                sent_cnt += 1
            later_than = next_later_than
            if not args.dry_run:
                with open(args.check_time_file, 'w') as f:
                    f.write(later_than.isoformat())
            logging.info(f"Processed {sent_cnt} alerts. Will sleep for {args.check_interval_seconds} seconds")
            await asyncio.sleep(args.check_interval_seconds)
    except StopAgentLoop as e:
        logging.info(f"Exiting agent check loop per request: {e}")


        


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description="An agent to reply to Grafana alerts with summaries and debugging tips.")
    parser.add_argument(
        "--model",
        type=str,
        default="openai:gpt-4.1",
        help="Model to use for the agent (default: openai:gpt-4.1)"
    )
    parser.add_argument(
        '--alert-slack-channel',
        type=str,
        default="alerts",
        help="Slack channel where alerts are sent (default: alerts)"
    )
    parser.add_argument(
        "--agent-slack-user",
        type=str,
        default="orca-alerts",
        help="Slack user name for the agent (default: orca-alerts)"
    )
    parser.add_argument(
        "--alert-slack-user",
        type=str,
        default="Grafana notifications",
        help="Slack user name that sends alerts (default: Grafana notifications)"
    )
    parser.add_argument(
        "--last-check-time",
        type=str,
        default=None,
        help="ISO formatted date or datetime for last check (default: None)"
    )
    parser.add_argument(
        "--check-time-file",
        type=str,
        default="last_check_time.txt",
        help="File to store last check time (default: last_check_time.txt)"
    )
    parser.add_argument(
        "--check-interval-seconds",
        type=int,
        default=300,
        help="Interval in seconds between checks (default: 300)"
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        default=False,
        help="If specified, print additional debug information"
    )
    parser.add_argument(
        '--log',
        type=str,
        default='WARNING',
        help='Logging level (e.g. DEBUG, INFO, WARNING, ERROR, CRITICAL). Default: WARNING.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='If specified, do not send messages to Slack and process only one event (dry run mode)'
    )
    parser.add_argument(
        '--dump-messages-and-exit',
        action='store_true',
        default=False,
        help='If specified, print the markdown for all slack alert messages found and exit.'
    )
    parser.add_argument(
        '--enable-tracing',
        action='store_true',
        default=False,
        help='Enable OpenTelemetry tracing with Phoenix.'
    )
    

    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.WARNING))

    if args.enable_tracing:
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace import TracerProvider
            from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor

            # Set up the tracer provider
            tracer_provider = TracerProvider()
            trace.set_tracer_provider(tracer_provider)

            # Add the OpenInference span processor
            endpoint = f"{os.environ['PHOENIX_COLLECTOR_ENDPOINT']}/v1/traces"

            # If you are using a local instance without auth, ignore these headers
            headers = {} # {"Authorization": f"Bearer {os.environ['PHOENIX_API_KEY']}"}
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)

            tracer_provider.add_span_processor(OpenInferenceSpanProcessor())
            tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

            logging.info("OpenTelemetry tracing with Phoenix enabled.")
        except ImportError as e:
            logging.error(f"Tracing requested but OpenTelemetry or Phoenix is not installed: {e}")
            sys.exit(1)


    # figure out how far back we go for messages.
    if args.last_check_time:
        later_than = datetime.datetime.fromisoformat(args.last_check_time)
    elif exists(args.check_time_file):
        with open(args.check_time_file, 'r') as f:
            text = f.read().strip()
        later_than = datetime.datetime.fromisoformat(text)
    else:
        later_than = datetime.datetime.now() - datetime.timedelta(hours=24)

    if args.dump_messages_and_exit:
        conversations = get_conversations(
            args.alert_slack_user, args.agent_slack_user,
            args.alert_slack_channel, limit=100,
            later_than=later_than
        )
        for message in conversations:
            print(message.markdown())
        return 0

    agent = make_agent(args.model, instrument=args.enable_tracing)
    asyncio.run(check_loop(agent, later_than, args))
    return 0

