"""
Interactions with the slack channel (used for alerts and communication with human users)
"""

import os
from typing import Optional, Any
from slack_sdk import WebClient
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel

MAX_CHUNK_SIZE=3000 # max size for a message chunk in slack

class ChannelNotFound(Exception):
    pass

class ChannelReadError(Exception):
    pass

class SlackError(Exception):
    pass


def get_id_for_channel(channel_name:str) -> str:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    response = client.conversations_list(types="public_channel, private_channel")
    conversations = response["channels"]
    if conversations is not None:
        for conversation in conversations:
            if conversation['name']==channel_name:
                return conversation['id']
    raise ChannelNotFound(channel_name)


def get_bot_name(client, bot_id: str) -> str:
    """
    Converts a Slack bot ID to its name.
    Returns None if the bot is not found or an error occurs.
    """
    try:
        response = client.bots_info(bot=bot_id)
        if response["ok"]:
            bot_info = response["bot"]
            return bot_info["name"]
        else:
            raise SlackError(f"Error fetching bot info for ID {bot_id}: {response['error']}")
    except SlackError:
        raise
    except Exception as e:
        raise SlackError(f"An unexpected error occurred while fetching bot info for ID {bot_id}") from e


def get_user_name(client, user_id: str) -> str:
    """
    Converts a Slack user ID to their display name (or real name if display name is not set).
    """
    try:
        response = client.users_info(user=user_id)
        if response["ok"]:
            user_info = response["user"]
            # Prioritize display_name over real_name
            if user_info["profile"].get("display_name"):
                return user_info["profile"]["display_name"]
            elif user_info.get("real_name"):
                return user_info["real_name"]
            else:
                return user_info["name"] # Fallback to user handle if neither is available
        else:
            raise SlackError(f"Error fetching user info for ID {user_id}: {response['error']}")
    except SlackError:
        raise
    except Exception as e:
        raise SlackError(f"An unexpected error occurred while fetching user info for ID {user_id}") from e


class MessageInfo(BaseModel):
    timestamp: datetime
    ts: str
    thread_ts: str
    user_name: str
    is_a_bot: bool
    content: str
    replies: list['MessageInfo']

    def pp(self, indent=0):
        print(f"{' '*indent}Message:")
        print(f"{' '*indent}  timestamp: {self.timestamp}")
        print(f"{' '*indent}  ts:        {self.ts}")
        print(f"{' '*indent}  thread_ts: {self.thread_ts}")
        print(f"{' '*indent}  user_name: {self.user_name}")
        print(f"{' '*indent}  is_a_bot:  {self.is_a_bot}")
        print(f"{' '*indent}  content:")
        lines = self.content.split('\n')
        for line in lines:
            print(f"{' '*indent}   | {line}")
        if len(self.replies)>0:
            print(f"{'*'*indent}  Replies:")
            for reply in self.replies:
                reply.pp(indent=indent+4)
        else:
            print(f"{' '*indent}  Replies: []")

    def markdown(self, indent=0) -> str:
        """Return a markdown representation of this message and its replies."""
        md = f"{' '*indent}* Message:\n"
        md += f"{' '*indent}  * timestamp: {self.timestamp}\n"
        md += f"{' '*indent}  * user_name: {self.user_name}\n"
        md += f"{' '*indent}  * is_a_bot:  {self.is_a_bot}\n"
        md += f"{' '*indent}  * content:\n"
        #md += f"{' '*indent}    ```\n"
        lines = self.content.split('\n')
        for line in lines:
            md += f"{' '*indent}    {line}\n"
        #md += f"{' '*indent}    ```\n"
        if len(self.replies)>0:
            md += f"{'*'*indent}  * Replies:\n"
            for reply in self.replies:
                md += reply.markdown(indent=indent+4)
        else:
            md += f"{' '*indent}  * Replies: []\n"
        return md


def parse_message(client, channel_id:str, user_names:dict[str, str], bot_names:dict[str,str], message:dict) -> MessageInfo:
    content = message['text'].strip() if message['text'].strip()!='' else ''
    if 'user' in message:
        user_id = message['user']
        if user_id not in user_names:
            user_names[user_id] = get_user_name(client, user_id)
        user_name = user_names[user_id]
        is_a_bot = False
    elif 'bot_id' in message:
        bot_id = message['bot_id']
        if bot_id not in bot_names:
            bot_names[bot_id]= get_bot_name(client, bot_id)
        user_name = bot_names[bot_id]
        is_a_bot = True
    else:
        raise SlackError(f"Neither user nor bot_id in message. Keys were: {message.keys()}")

    # the timestamp is used to build a thread
    thread_ts = message['thread_ts'] if 'thread_ts' in message else message['ts']

    raw_ts = message['ts']
    ts = datetime.fromtimestamp(float(message['ts']), tz=ZoneInfo("UTC"))

    reply_count = int(message.get('reply_count', 0))

    if 'attachments' in message:
        for a in message['attachments']:
            if 'text' in a:
                content += a['text']
    msg = MessageInfo(timestamp=ts, ts=raw_ts, thread_ts=thread_ts,
                        user_name=user_name, is_a_bot=is_a_bot,
                        content=content, replies=[])
    if reply_count>0:
        replies_response = client.conversations_replies(channel=channel_id, ts=raw_ts)
        if not replies_response['ok']:
            raise ChannelReadError(f"Error fetching channel history: {replies_response['error']}")
        reply_messages = replies_response.get("messages")
        for reply_message in reply_messages:
            if reply_message.get("type") == "message" and "text" in reply_message:
                if reply_message['ts']==raw_ts:
                    continue # they seem to include the original message in the reply list
                msg.replies.append(parse_message(client, channel_id, user_names, bot_names, reply_message))
            else:
                print(f"Message of other type {reply_message.get('type')}")
    return msg

        


def get_recent_messages_from_channel(channel_name:str, limit:int=10, later_than:Optional[datetime]=None) -> list[MessageInfo]:
    """
    Get recent messages from a Slack channel and extract their content.

    Parameters
    ----------
    channel_name : str
        The name of the Slack channel to fetch messages from.
    limit : int, optional
        The maximum number of messages to retrieve. Default is 10.
    later_than : Optional[datetime], optional
        If provided, only messages sent after this datetime will be returned. Default is None.

    Returns
    -------
    list of MessageInfo
        A list of MessageInfo objects, each representing a message from the channel with extracted content and metadata.
        The fields of MessageInfo are:
        timestamp: datetime
            The timestamp of the message.
        thread_ts: str
            The timestamp of the message thread, used to reply to this message.
        user_name: str
            The name of the user or bot that sent the message
        is_a_bot: bool
            True if this user is a bot rather than a human
        content: str
            The text extracted from the message

    Raises
    ------
    ChannelReadError
        If there is an error fetching the channel history from Slack.
    SlackError
        If a message does not contain either a user or bot_id field.
    """
    bot_names = {}
    user_names = {}
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    channel_id = get_id_for_channel(channel_name)
    oldest = str(later_than.timestamp()) if later_than is not None else None
    history_response = client.conversations_history(channel=channel_id, limit=limit, oldest=oldest)
    if history_response["ok"]:
        messages = history_response.get("messages")
        import json
        result = []
        if messages is not None:
            for message in messages:
                # Messages can have different types (e.g., 'message', 'channel_join', etc.)
                # We are primarily interested in 'message' type for actual content
                if message.get("type") == "message" and "text" in message:
                    result.append(parse_message(client, channel_id, user_names, bot_names, message))
                else:
                    print(f"Message of other type {message.get('type')}")
        return result
    else:
        raise ChannelReadError(f"Error fetching channel history: {history_response['error']}")
    

def delete_recent_messages_from_channel(channel_name:str, user_name:str, limit:int,
                                        later_than:Optional[datetime]=None) -> int:
    """Get the matching messages for this user and delete them. Returns the number of
    mesages deleted."""
    messages = get_recent_messages_from_channel(channel_name=channel_name, limit=limit, later_than=later_than)
    if len(messages)==0:
        return 0
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    channel_id = get_id_for_channel(channel_name)
    def delete_children(message) -> int:
        """Delete the children before the parent"""
        total = 0
        for reply in message.replies:
            total += delete_children(reply)
        if message.user_name==user_name:
            client.chat_delete(channel=channel_id, ts=message.ts)
            total += 1
        return total
    total = 0
    for message in messages:
        total += delete_children(message)
    return total

    

def chunkify(s:str, max_chunk_size:int) -> list[str]:
    """
    Break a string into chunks of at most max_chunk_size, breaking at
   line breaks where possible.
    """
    chunks = []
    chunk = ""
    for line in s.splitlines(keepends=True):
        if len(chunk) + len(line) <= max_chunk_size:
            chunk += line
        else:
            while len(line)>max_chunk_size:
                additional = max_chunk_size - len(chunk)
                chunk += line[0:additional]
                chunks.append(chunk)
                chunk = ""
                line = line[additional:]
            if len(chunk)>0:
                chunks.append(chunk)
                chunk = line
    if len(chunk)>0:
        chunks.append(chunk)
    return chunks
    

def send_message_to_channel(channel_name: str, markdown_text: str, thread_ts: Optional[str]) -> None:
    """
    Send a message to a Slack channel, optionally as a reply in a thread.

    Parameters
    ----------
    channel_name : str
        The name of the Slack channel to send the message to.
    markdown_text : str
        The message content in Slack markdown format. If the message exceeds 3000 characters, it will be split into chunks.
    thread_ts : Optional[str]
        The timestamp of the thread to reply to. If None, the message is sent as a new message.

    Raises
    ------
    SlackError
        If there is an error posting the message to Slack.
    """
    channel_id = get_id_for_channel(channel_name)
    # we can only send messages of max length 3000, so we
    # break into chunks if needed. The last chunk gets the image
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    if len(markdown_text) > MAX_CHUNK_SIZE:
        text_chunks = chunkify(markdown_text, MAX_CHUNK_SIZE)
        blocks = [{
            "type": "section",
            "block_id": str(i),
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        } for (i, text) in enumerate(text_chunks)]
        text = text_chunks[0]
    else:
        text = markdown_text
        blocks = []

    response = client.chat_postMessage(thread_ts=thread_ts, text=text, channel=channel_id, blocks=blocks, mrkdwn=True)
    if not response['ok']:
        raise SlackError(f"Got error in Slack post to chanel {channel_name}. Full response:\n{response}")