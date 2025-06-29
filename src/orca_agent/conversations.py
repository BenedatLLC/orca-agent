"""Process groups of messages as conversations"""
from typing import Generator, Optional
from datetime import datetime
from .slack_client import get_recent_messages_from_channel, MessageInfo

def _has_any_replies_by_user(message:MessageInfo, user_name:str) -> bool:
    if message.user_name==user_name:
        return True
    for reply in message.replies:
        if _has_any_replies_by_user(reply, user_name):
            return True
    return False


def get_conversations(alert_user:str, my_user:str, channel_name:str, limit:int=10, later_than:Optional[datetime]=None) \
    -> list[MessageInfo]:
    """We return all top level messages and their replies, if the message originated by the alert user and we have not already replied.
    These messages are returned one at a time"""
    messages = get_recent_messages_from_channel(channel_name=channel_name, limit=limit, later_than=later_than)
    return [
        message for message in messages
        if message.user_name==alert_user and not _has_any_replies_by_user(message, my_user)
    ]
