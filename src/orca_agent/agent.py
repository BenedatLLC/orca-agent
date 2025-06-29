"""
Agent creation for orca-agent using pydantic.ai.
"""
import sys
import argparse
import datetime
from os.path import exists
import logging
import time
from pydantic_ai.agent import Agent
from .runbook import get_runbook_text
from .slack_client import send_message_to_channel
from .pydantic_utils import pp_run_result
from .conversations import get_conversations

SYSTEM_PROMPT =\
"""You are an automated assistant for monitoring alerts. You will be given a Grafana alert message that
was sent to Slack along with any replies. Construct a reply to the alert message that provides an explanation
of the alert message and debugging tips. Please be as specific as possible. Include any specific pods, containers,
deployments, and errors mentioned in the alert.

If the alert has a url for a runbook, use the provided tool `get_runbook_text` to retrieve the text of the runbook and use it to
improve your response.

If the alert mentions a `DatasourceError`, check whether this is a problem retrieving metrics from Prometheus or another
data source rather the problem associated with the original alert. If this is the case, make that clear in your
explanation.

Write your reply using Markdown formatting. In particular, please use Slack's flavor of markdown ('mrkdwn'), as the
message will be sent to a Slack channel. In particular, keep the following in mind:
 * Only use the '*' character for bullet lists (never '-')
 * Do not combine headings (e.g. '##') and numbered lists in the same line.
 * Leave a blank line after headings and before a bulleted or numbered list
 * Do not use bold text inside a list item
 * Do not use "---" as a separator, it doesn't work.
"""

def make_agent(model: str) -> Agent:
    """
    Create and return a pydantic.ai Agent with access to runbook and Slack tools.

    Parameters
    ----------
    model : str

    Returns
    -------
    Agent
        A configured pydantic.ai Agent instance.
    """
    tools = [
        get_runbook_text,
    ]
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools
    )

def check_loop(agent:Agent, later_than:datetime.datetime, args):
    logging.info(f"Entering main loop with later_than={later_than}")
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
            result = agent.run_sync(input)
            if args.debug:
                pp_run_result(result)
            if not args.dry_run:
                send_message_to_channel(args.alert_slack_channel, result.output, message.thread_ts)
                logging.info(f"Send message of length {len(result.output)} to channel {args.alert_slack_channel}")
            else:
                logging.info(f"[DRY RUN] Would send message of length {len(result.output)} to channel {args.alert_slack_channel}")
                print(f"{'='*15} Output from agent {'='*15}")
                print(result.output + '\n')
            sent_cnt += 1
        later_than = next_later_than
        if not args.dry_run:
            with open(args.check_time_file, 'w') as f:
                f.write(later_than.isoformat())
        logging.info(f"Processed {sent_cnt} alerts. Will sleep for {args.check_interval_seconds} seconds")
        time.sleep(args.check_interval_seconds)


        


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
        help='If specified, do not send messages to Slack (dry run mode)'
    )
    parser.add_argument(
        '--dump-messages-and-exit',
        action='store_true',
        default=False,
        help='If specified, print the markdown for all slack alert messages found and exit.'
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log.upper(), logging.WARNING))

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

    agent = make_agent(args.model)
    check_loop(agent, later_than, args)
    return 0

