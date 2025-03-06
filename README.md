# Nuanced MCP Server

A Model Context Protocol (MCP) server that provides call graph analysis capablities to LLMs through the [nuanced](https://github.com/nuanced-dev/nuanced) library.

## Overview

This MCP server enables LLMs to understand code structure by accessing function call graphs through standardized tools and resources. It allows AI assistants to:

- Initialize call graphs for Python repos
- Explore function call relationships
- Analyze dependencies between functions
- Provide more contextually aware code assistance

## API

### Tools

- **initialize_graph**

  - Initialize a code graph for the given repository path
  - Input: `repo_path` (string)

- **get_function_call_graph**
  - Get the call graph for a specific function
  - Inputs:
    - `file_path`
    - `function_name`

## Usage with Claude Desktop

Add this to your `claude_desktop_config.json`

### UV

```json
{
  "mcpServers": {
    "nuanced": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/nuanced-mcp",
        "run",
        "nuanced_mcp_server.py"
      ]
    }
  }
}
```
