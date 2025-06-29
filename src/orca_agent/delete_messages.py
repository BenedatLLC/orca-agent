"""Utility to delete slack messages.
This is useful in development, where we may want to tweak an options and try the run again"""

import sys
import argparse
import datetime

from .slack_client import delete_recent_messages_from_channel

def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser("Utility to delete messages from a specified user")
    parser.add_argument(
        '--alert-slack-channel',
        type=str,
        default="alerts",
        help="Slack channel where alerts are sent (default: alerts)"
    )
    parser.add_argument(
        "--slack-user",
        type=str,
        default="orca-alerts",
        help="Slack user name for user to delete messages (default: orca-alerts)"
    )
    parser.add_argument(
        "--later-than",
        type=str,
        default=None,
        help="Only for messages later than this, ISO formatted date or datetime (default: None)"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=1000,
        help="Maxumum number of messages to delete (default: 1000)"
    )
    args = parser.parse_args(argv)
    if args.later_than:
        later_than = datetime.datetime.fromisoformat(args.later_than)
    else:
        later_than = None
    cnt = delete_recent_messages_from_channel(args.alert_slack_channel, args.slack_user, later_than=later_than,
                                              limit=args.limit)
    print(f"Deleted {cnt} messages")
    return 0

if __name__=='__main__':
    sys.exit(main())