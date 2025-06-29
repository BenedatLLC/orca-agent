from typing import List
from textwrap import TextWrapper, fill
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse,\
     SystemPromptPart, UserPromptPart, ToolReturnPart, RetryPromptPart,\
     TextPart, ToolCallPart
from pydantic_ai.agent import AgentRunResult

def _indent_no_fill(text:str, indent:int):
    indentstr = " "*indent
    for line in text.split('\n'):
        print(f"{indentstr}{line}")


def pp_request(req:ModelRequest, indent=0):
    indentstr = " "*indent
    print(f"{indentstr}=====>")
    indentstr += "  "
    w = TextWrapper(width=70, initial_indent=indentstr, subsequent_indent=indentstr+"  ")
    for part in req.parts:
        if isinstance(part, SystemPromptPart):
            #print(w.fill(f"SYSTEM PROMPT:\n{part.content}"))
            print(f"{indentstr}SYSTEM PROMPT:")
            _indent_no_fill(str(part.content), indent=indent+4)
        elif isinstance(part, UserPromptPart):
            print(w.fill(f"USER PROMPT:\n{part.content}"))
        elif isinstance(part, ToolReturnPart):
            print(w.fill(f"TOOL RETURN ({part.tool_name}):\n{part.content}"))
        else:
            assert isinstance(part, RetryPromptPart), f"Unknown request part: {type(part)}"
            print(f"{indentstr}RETRY PROMPT ({part.tool_name}):")
            w2 = TextWrapper(width=70, initial_indent=indentstr+"  ", subsequent_indent=indentstr+"  ")
            for error_details in part.content:
                print(w2.fill(str(error_details)))

def pp_response(rsp:ModelResponse, indent=0):
    indentstr = " "*indent
    print(f"{indentstr}<=====")
    indentstr += "  "
    w = TextWrapper(width=70, initial_indent=indentstr, subsequent_indent=indentstr+"  ")
    for part in rsp.parts:
        if isinstance(part, TextPart):
            if part.has_content():
                print(w.fill(f"TEXT RESPONSE:\n{part.content}"))
            else:
                print(f"{indentstr}EMPTY TEXT RESPONSE")
        else:
            assert isinstance(part, ToolCallPart), f"Unknown response part: {type(part)}"
            print(f"{indentstr}TOOL CALL ({part.tool_name}):")
            w2 = TextWrapper(width=70, initial_indent=indentstr+"  ", subsequent_indent=indentstr+"  ")
            if isinstance(part.args, dict):
                for k, v in part.args.items():
                    print(w2.fill(f"{k} = {v}"))
            else:
                print(w2.fill(part.args))

def pp_messages(messages:List[ModelMessage], indent=0):
    indentstr= " "*indent
    for message in messages:
        if isinstance(message, ModelRequest):
            pp_request(message, indent)
        elif isinstance(message, ModelResponse):
            pp_response(message, indent)
        else:
            print(f"{indentstr}Unknown response type: {type(message)}")
            print(fill(str(message), width=70, initial_indent=indentstr+"  ", subsequent_indent=indentstr+"  "))

def pp_run_result(result:AgentRunResult, indent=0):
    indentstr = " "*indent
    print(f"{indentstr}AGENT RUN RESULT:")
    indentstr += "  "
    print(f"{indentstr}CONTENT:")
    _indent_no_fill(str(result.data), indent+4)
    messages = result.all_messages()
    if len(messages)>0:
        print(f"{indentstr}MESSAGES:")
        pp_messages(messages, indent+4)
    else:
        print(f"{indentstr}MESSAGES: []")