"""Tools for talking with MCP. We build on
https://github.com/rohitg00/kubectl-mcp-server.
"""

import sys
import os
import logging
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

MCP_SERVER_MODULE="kubectl_mcp_tool.mcp_server"
#MCP_SERVER_MODULE="kubectl_mcp_tool.minimal_wrapper"

PYTHON=sys.executable

def make_k8s_mcp():
    return MCPServerStdio(
        PYTHON,
        args=["-m", MCP_SERVER_MODULE],
        env={
            'PATH':os.environ['PATH'],
            'KUBECONFIG':os.environ["KUBECONFIG"],
            "MCP_LOG_FILE":os.environ['MCP_LOG_FILE'],
            'MCP_DEBUG':'1'
        },
        allow_sampling=False
    )
