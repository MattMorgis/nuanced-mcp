# Nuanced MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that provides call graph analysis capabilities to LLMs through the [nuanced](https://github.com/nuanced-dev/nuanced) library.

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

- **switch_repository**

  - Switch to a different initialized repository
  - Input: `repo_path` (string)

- **list_repositories**

  - List all initialized repositories
  - No inputs required

- **get_function_call_graph**

  - Get the call graph for a specific function
  - Inputs:
    - `file_path` (string)
    - `function_name` (string)
    - `repo_path` (string, optional) - uses active repository if not specified

- **analyze_dependencies**

  - Find all module or file dependencies in the codebase
  - Inputs (at least one required):
    - `file_path` (string, optional)
    - `module_name` (string, optional)

- **analyze_change_impact**
  - Analyze the impact of changing a specific function
  - Inputs:
    - `file_path` (string)
    - `function_name` (string)

### Resources

- **graph://summary**

  - Get a summary of the currently loaded code graph
  - No parameters required

- **graph://repo/{repo_path}/summary**

  - Get a summary of a specific repository's code graph
  - Parameters:
    - `repo_path` (string) - Path to the repository

- **graph://function/{file_path}/{function_name}**
  - Get detailed information about a specific function
  - Parameters:
    - `file_path` (string) - Path to the file containing the function
    - `function_name` (string) - Name of the function to analyze

### Prompts

- **analyze_function**

  - Create a prompt to analyze a function with its call graph
  - Parameters:
    - `file_path` (string) - Path to the file containing the function
    - `function_name` (string) - Name of the function to analyze

- **impact_analysis**

  - Create a prompt to analyze the impact of changing a function
  - Parameters:
    - `file_path` (string) - Path to the file containing the function
    - `function_name` (string) - Name of the function to analyze

- **analyze_dependencies_prompt**
  - Create a prompt to analyze dependencies of a file or module
  - Parameters (at least one required):
    - `file_path` (string, optional) - Path to the file to analyze
    - `module_name` (string, optional) - Name of the module to analyze

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
