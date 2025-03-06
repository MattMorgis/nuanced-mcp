#!/usr/bin/env python3
"""
MCP Server for nuanced code graph analysis
"""

from mcp.server.fastmcp import FastMCP, Context
from nuanced import CodeGraph
import os
import json
from typing import Dict, Optional, Any, List, Set, Tuple
import glob

# Create an MCP server
mcp = FastMCP(
    "Nuanced",
    dependencies=["nuanced"],
    description="Code call graph analysis using nuanced",
)

# Store the code graphs as global variables to reuse across requests
_code_graphs = {}
_active_repo = None


@mcp.tool()
def initialize_graph(repo_path: str) -> str:
    """Initialize a code graph for the given repository path.

    Args:
        repo_path: Path to the repository to analyze

    Returns:
        Success message with information about the initialized graph
    """
    global _code_graphs, _active_repo

    # Check if path exists
    if not os.path.exists(repo_path):
        return f"Error: Path '{repo_path}' does not exist"
    
    # Use absolute path as key
    abs_path = os.path.abspath(repo_path)

    try:
        result = CodeGraph.init(repo_path)

        if result.errors:
            error_messages = [str(error) for error in result.errors]
            return f"Errors initializing code graph:\n" + "\n".join(error_messages)

        _code_graphs[abs_path] = result.code_graph
        _active_repo = abs_path

        # Count Python files
        py_files = glob.glob(f"{repo_path}/**/*.py", recursive=True)

        return (
            f"Successfully initialized code graph for {repo_path}.\n"
            f"Repository contains {len(py_files)} Python files.\n"
            f"This is now the active repository."
        )
    except Exception as e:
        return f"Error initializing code graph: {str(e)}"


@mcp.tool()
def switch_repository(repo_path: str) -> str:
    """Switch to a different initialized repository.
    
    Args:
        repo_path: Path to the repository to switch to
    
    Returns:
        Success message or error
    """
    global _code_graphs, _active_repo
    
    abs_path = os.path.abspath(repo_path)
    
    if abs_path not in _code_graphs:
        return f"Error: Repository at '{repo_path}' has not been initialized. Use initialize_graph first."
    
    _active_repo = abs_path
    return f"Successfully switched to repository: {repo_path}"


@mcp.tool()
def list_repositories() -> str:
    """List all initialized repositories.
    
    Returns:
        List of initialized repositories
    """
    global _code_graphs, _active_repo
    
    if not _code_graphs:
        return "No repositories have been initialized yet."
    
    repo_list = []
    for repo_path in _code_graphs.keys():
        prefix = "* " if repo_path == _active_repo else "  "
        repo_list.append(f"{prefix}{repo_path}")
    
    return "Initialized repositories:\n" + "\n".join(repo_list) + "\n\n* indicates active repository"


@mcp.tool()
def get_function_call_graph(file_path: str, function_name: str, repo_path: str = None) -> str:
    """Get the call graph for a specific function.

    Args:
        file_path: Path to the file containing the function
        function_name: Name of the function to analyze
        repo_path: Optional repository path (uses active repository if not specified)

    Returns:
        Information about the function's call graph
    """
    global _code_graphs, _active_repo
    
    # Determine which repository to use
    target_repo = repo_path
    if target_repo:
        target_repo = os.path.abspath(target_repo)
        if target_repo not in _code_graphs:
            return f"Error: Repository '{repo_path}' not initialized"
    else:
        if _active_repo is None:
            return "Error: No active repository. Please initialize a graph first."
        target_repo = _active_repo
    
    code_graph = _code_graphs[target_repo]

    try:
        # Resolve relative paths to absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(target_repo, file_path)

        # Get enrichment result
        enrichment = code_graph.enrich(file_path, function_name)

        if enrichment.errors:
            error_messages = [str(error) for error in enrichment.errors]
            return f"Errors retrieving call graph:\n" + "\n".join(error_messages)

        if not enrichment.result:
            return f"Function '{function_name}' not found in '{file_path}'"

        # Format the result for better readability
        result = format_enrichment_result(file_path, function_name, enrichment.result)
        return result

    except Exception as e:
        return f"Error retrieving call graph: {str(e)}"


@mcp.tool()
def analyze_dependencies(file_path: str = None, module_name: str = None) -> str:
    """Find all module or file dependencies in the codebase.
    
    Identifies all function dependencies for a file or module
    in the active repository. This identifies all modules that
    depend on the specified module or file.
    
    Args:
        file_path: Path to a specific file to analyze dependencies for
        module_name: Name of a module to analyze dependencies for
                    (e.g., 'auth' will match 'app.auth', 'auth.users', etc.)
    
    Returns:
        A list of all functions and files that depend on the specified module
    """
    global _code_graphs, _active_repo
    
    if _active_repo is None:
        return "Error: No active repository. Please initialize a graph first."
    
    if file_path is None and module_name is None:
        return "Error: Please specify either file_path or module_name"
    
    code_graph = _code_graphs[_active_repo]
    graph = code_graph.graph
    
    # Dict to store dependents: {filepath -> [function_names]}
    dependents: Dict[str, List[str]] = {}
    
    try:
        # Filter for target nodes based on criteria
        target_nodes = []
        
        if file_path:
            # If file_path is specified, convert to absolute path if needed
            if not os.path.isabs(file_path):
                file_path = os.path.join(_active_repo, file_path)
            
            # Find all nodes in the specified file
            for node_key, node in graph.items():
                if node.get("filepath") == file_path:
                    target_nodes.append(node_key)
        
        if module_name:
            # Find all nodes in modules matching the pattern
            for node_key, node in graph.items():
                if f".{module_name}." in node_key or node_key.startswith(f"{module_name}.") or \
                   node_key.endswith(f".{module_name}"):
                    target_nodes.append(node_key)
        
        if not target_nodes:
            if file_path:
                return f"No functions found in '{file_path}'"
            else:
                return f"No functions found matching module '{module_name}'"
        
        # Find all functions that call our target functions
        for node_key, node in graph.items():
            callees = node.get("callees", [])
            
            # Check if this node calls any of our target nodes
            calls_targets = any(target in callees for target in target_nodes)
            
            if calls_targets:
                filepath = node.get("filepath")
                function_name = node_key.split(".")[-1]
                
                if filepath not in dependents:
                    dependents[filepath] = []
                
                dependents[filepath].append(function_name)
        
        # Format the result
        if file_path:
            header = f"# Dependencies for file: {file_path}\n"
        else:
            header = f"# Dependencies for module: {module_name}\n"
        
        if not dependents:
            return f"{header}\nNo dependencies found. This code is not used by other parts of the codebase."
        
        result = [header, "The following code depends on this component:\n"]
        
        # Group by files for readability
        for filepath, functions in sorted(dependents.items()):
            relative_path = os.path.relpath(filepath, _active_repo) if filepath.startswith(_active_repo) else filepath
            result.append(f"## {relative_path}")
            for function in sorted(functions):
                result.append(f"- {function}")
            result.append("")
        
        # Add summary statistics
        total_dependents = sum(len(funcs) for funcs in dependents.values())
        result.append(f"**Summary:** {len(dependents)} files with {total_dependents} functions depend on this component")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error analyzing dependencies: {str(e)}"


@mcp.tool()
def analyze_change_impact(file_path: str, function_name: str) -> str:
    """Analyze the impact of changing a specific function.
    
    This tool performs a comprehensive impact analysis to help understand
    what would be affected if you modify the specified function.
    
    Args:
        file_path: Path to the file containing the function
        function_name: Name of the function to analyze
    
    Returns:
        A detailed analysis of the potential impact of changing the function
    """
    global _code_graphs, _active_repo
    
    if _active_repo is None:
        return "Error: No active repository. Please initialize a graph first."
    
    code_graph = _code_graphs[_active_repo]
    graph = code_graph.graph
    
    try:
        # Resolve relative paths to absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(_active_repo, file_path)
        
        # First get the enrichment result for the function
        enrichment = code_graph.enrich(file_path, function_name)
        
        if enrichment.errors:
            error_messages = [str(error) for error in enrichment.errors]
            return f"Errors analyzing impact:\n" + "\n".join(error_messages)
        
        if not enrichment.result:
            return f"Function '{function_name}' not found in '{file_path}'"
        
        subgraph = enrichment.result
        
        # Find the entry point node key
        entrypoint_keys = [k for k in subgraph.keys() if k.endswith(function_name)]
        if not entrypoint_keys:
            return f"Error: Entry point function {function_name} not found in subgraph"
        
        entrypoint_key = entrypoint_keys[0]
        entrypoint_node = subgraph[entrypoint_key]
        
        # Structure to hold our impact analysis
        direct_callers = []  # Functions that directly call our target
        indirect_callers = []  # Functions that indirectly depend on our target
        potential_tests = []  # Likely test files that might need updates
        critical_paths = []  # Paths with many dependencies (high risk)
        
        # Find direct callers by scanning the full graph
        for node_key, node in graph.items():
            if node_key == entrypoint_key:
                continue
                
            callees = node.get("callees", [])
            if entrypoint_key in callees:
                direct_callers.append({
                    "name": node_key.split(".")[-1],
                    "full_path": node_key,
                    "filepath": node.get("filepath"),
                    "lineno": node.get("lineno")
                })
        
        # BFS to find indirect callers (up to depth 3)
        def find_indirect_callers(start_nodes, max_depth=3):
            visited = set(start_nodes)
            queue = [(node, 1) for node in start_nodes]  # (node, depth)
            results = []
            
            while queue:
                current, depth = queue.pop(0)
                
                if depth > max_depth:
                    continue
                
                # Find callers of current
                for node_key, node in graph.items():
                    if node_key in visited:
                        continue
                        
                    callees = node.get("callees", [])
                    if current in callees:
                        visited.add(node_key)
                        queue.append((node_key, depth + 1))
                        results.append({
                            "name": node_key.split(".")[-1],
                            "full_path": node_key,
                            "filepath": node.get("filepath"),
                            "lineno": node.get("lineno"),
                            "depth": depth
                        })
            
            return results
        
        # Get indirect callers
        if direct_callers:
            indirect_callers = find_indirect_callers([caller["full_path"] for caller in direct_callers])
        
        # Find potential test files
        for caller in direct_callers + indirect_callers:
            filepath = caller.get("filepath", "")
            if "test" in filepath.lower() and filepath not in potential_tests:
                potential_tests.append(filepath)
        
        # Identify critical paths (functions called by many others)
        caller_counts = {}
        for node_key, node in graph.items():
            for caller in direct_callers + indirect_callers:
                caller_path = caller["full_path"]
                if caller_path in node.get("callees", []):
                    if caller_path not in caller_counts:
                        caller_counts[caller_path] = 0
                    caller_counts[caller_path] += 1
        
        # Get top 5 most called functions in the impact path
        for path, count in sorted(caller_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count > 1:  # Only include if called by multiple functions
                node = graph.get(path, {})
                critical_paths.append({
                    "name": path.split(".")[-1],
                    "full_path": path,
                    "filepath": node.get("filepath"),
                    "count": count
                })
        
        # Format the results
        result = [
            f"# Change Impact Analysis for {function_name} in {file_path}",
            "",
            "This analysis helps you understand the potential impact of changing this function.",
            "",
            "## Direct Dependents",
            "These functions directly call the function you plan to change:",
            ""
        ]
        
        if direct_callers:
            # Group by file for readability
            file_groups = {}
            for caller in direct_callers:
                filepath = caller["filepath"]
                if filepath not in file_groups:
                    file_groups[filepath] = []
                file_groups[filepath].append(caller)
            
            for filepath, callers in sorted(file_groups.items()):
                rel_path = os.path.relpath(filepath, _active_repo) if filepath.startswith(_active_repo) else filepath
                result.append(f"### {rel_path}")
                for caller in callers:
                    result.append(f"- {caller['name']} (line {caller['lineno']})")
                result.append("")
        else:
            result.append("No direct dependents found. This function is not called directly by other functions.\n")
        
        result.append("## Indirect Dependents")
        result.append("These functions indirectly depend on the function through the call chain:\n")
        
        if indirect_callers:
            # Group by depth for readability
            depth_groups = {}
            for caller in indirect_callers:
                depth = caller.get("depth", 0)
                if depth not in depth_groups:
                    depth_groups[depth] = []
                depth_groups[depth].append(caller)
            
            for depth in sorted(depth_groups.keys()):
                result.append(f"### Depth {depth} (Call Chain Length)")
                for caller in sorted(depth_groups[depth], key=lambda x: x["name"]):
                    filepath = caller["filepath"]
                    rel_path = os.path.relpath(filepath, _active_repo) if filepath.startswith(_active_repo) else filepath
                    result.append(f"- {caller['name']} in {rel_path}")
                result.append("")
        else:
            result.append("No indirect dependents found.\n")
        
        if potential_tests:
            result.append("## Potential Tests Affected")
            result.append("These test files might need updates:\n")
            for test_file in sorted(potential_tests):
                rel_path = os.path.relpath(test_file, _active_repo) if test_file.startswith(_active_repo) else test_file
                result.append(f"- {rel_path}")
            result.append("")
        
        if critical_paths:
            result.append("## Critical Components")
            result.append("These are the most heavily used components in the impact path (high risk):\n")
            for path in critical_paths:
                filepath = path["filepath"]
                rel_path = os.path.relpath(filepath, _active_repo) if filepath and filepath.startswith(_active_repo) else filepath
                result.append(f"- {path['name']} in {rel_path} (used by {path['count']} dependents)")
            result.append("")
        
        # Add impact summary and recommendations
        total_impact = len(direct_callers) + len(indirect_callers)
        impact_level = "High" if total_impact > 10 else "Medium" if total_impact > 3 else "Low"
        
        result.append("## Impact Summary")
        result.append(f"- **Impact Level**: {impact_level}")
        result.append(f"- **Direct Dependents**: {len(direct_callers)}")
        result.append(f"- **Indirect Dependents**: {len(indirect_callers)}")
        result.append(f"- **Potential Tests Affected**: {len(potential_tests)}")
        result.append("")
        
        result.append("## Recommendations")
        if impact_level == "High":
            result.append("- Consider breaking the change into smaller, incremental changes")
            result.append("- Implement thorough tests before changing the function")
            result.append("- Communicate the change to other developers")
            result.append("- Document all breaking changes carefully")
        elif impact_level == "Medium":
            result.append("- Maintain backward compatibility if possible")
            result.append("- Test all direct dependent functions")
            result.append("- Consider deprecation warnings before removing functionality")
        else:  # Low impact
            result.append("- Proceed with changes while maintaining the same function signature if possible")
            result.append("- Update related tests")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error analyzing change impact: {str(e)}"


def format_enrichment_result(
    file_path: str, function_name: str, subgraph: Dict[str, Any]
) -> str:
    """Format the enrichment result for better readability"""
    # Find the entry point node key
    entrypoint_keys = [k for k in subgraph.keys() if k.endswith(function_name)]
    if not entrypoint_keys:
        return f"Error: Entry point function {function_name} not found in subgraph"

    entrypoint_key = entrypoint_keys[0]
    entrypoint_node = subgraph[entrypoint_key]

    # Extract direct callees
    direct_callees = entrypoint_node.get("callees", [])
    direct_callee_names = [path.split(".")[-1] for path in direct_callees]

    # Get callers (functions that call this function)
    # This requires iterating through all nodes in the graph
    callers = []
    for node_key, node in subgraph.items():
        if node_key == entrypoint_key:
            continue
        if entrypoint_key in node.get("callees", []):
            callers.append(node_key)

    caller_names = [path.split(".")[-1] for path in callers]

    # Format the result
    result = [
        f"## Function Call Graph for '{function_name}' in {file_path}",
        "",
        "### Function Information",
        f"- Full path: {entrypoint_key}",
        f"- Filepath: {entrypoint_node.get('filepath', 'Unknown')}",
        f"- Line number: {entrypoint_node.get('lineno', 'Unknown')}",
        "",
        "### Direct Function Calls",
    ]

    if direct_callee_names:
        for name in direct_callee_names:
            result.append(f"- {name}")
    else:
        result.append("- No direct function calls found")

    result.extend(
        [
            "",
            "### Called By",
        ]
    )

    if caller_names:
        for name in caller_names:
            result.append(f"- {name}")
    else:
        result.append("- Not called by any other functions in the analyzed code")

    result.extend(
        [
            "",
            "### Full Call Graph (JSON)",
            "```json",
            json.dumps(subgraph, indent=2),
            "```",
        ]
    )

    return "\n".join(result)


@mcp.resource("graph://summary")
def get_graph_summary() -> str:
    """Get a summary of the currently loaded code graph."""
    global _code_graphs, _active_repo

    if not _code_graphs or _active_repo is None:
        return "No code graph has been initialized yet."

    try:
        # Count Python files
        py_files = glob.glob(f"{_active_repo}/**/*.py", recursive=True)

        # Count functions in the graph
        code_graph = _code_graphs[_active_repo]
        function_count = len(code_graph.graph) if hasattr(code_graph, "graph") else 0

        return f"""
# Code Graph Summary

- Repository: {_active_repo}
- Python files: {len(py_files)}
- Functions tracked: {function_count}

## Usage

To analyze specific functions:

1. Use the `get_function_call_graph` tool with:
   - file_path: Path to the Python file
   - function_name: Name of the function to analyze

Example: `get_function_call_graph("app/models.py", "authenticate")`

## Available Resources

- `graph://summary`: This summary
- `graph://function/{file_path}/{function_name}`: Get details for a specific function
"""
    except Exception as e:
        return f"Error generating graph summary: {str(e)}"


@mcp.resource("graph://repo/{repo_path}/summary")
def get_repo_summary(repo_path: str) -> str:
    """Get a summary of a specific repository's code graph."""
    global _code_graphs
    
    abs_path = os.path.abspath(repo_path)
    if abs_path not in _code_graphs:
        return f"Repository '{repo_path}' not initialized"
    
    try:
        code_graph = _code_graphs[abs_path]
        py_files = glob.glob(f"{abs_path}/**/*.py", recursive=True)
        function_count = len(code_graph.graph) if hasattr(code_graph, "graph") else 0
        
        return f"""
# Code Graph Summary for {repo_path}

- Python files: {len(py_files)}
- Functions tracked: {function_count}

## Usage

To analyze specific functions:

1. Use the `get_function_call_graph` tool with:
   - file_path: Path to the Python file
   - function_name: Name of the function to analyze
   - repo_path: "{repo_path}"

Example: `get_function_call_graph("app/models.py", "authenticate", "{repo_path}")`
"""
    except Exception as e:
        return f"Error generating graph summary: {str(e)}"


@mcp.resource("graph://function/{file_path}/{function_name}")
def get_function_details(file_path: str, function_name: str) -> str:
    """Get detailed information about a specific function."""
    global _code_graphs, _active_repo

    if not _code_graphs or _active_repo is None:
        return "No code graph has been initialized yet."

    try:
        # Resolve relative paths to absolute
        if not os.path.isabs(file_path):
            file_path = os.path.join(_active_repo, file_path)

        code_graph = _code_graphs[_active_repo]
        enrichment = code_graph.enrich(file_path, function_name)

        if enrichment.errors:
            error_messages = [str(error) for error in enrichment.errors]
            return f"Errors retrieving function details:\n" + "\n".join(error_messages)

        if not enrichment.result:
            return f"Function '{function_name}' not found in '{file_path}'"

        # Format the result similarly to the tool, but without the JSON
        result = format_resource_result(file_path, function_name, enrichment.result)
        return result

    except Exception as e:
        return f"Error retrieving function details: {str(e)}"


def format_resource_result(
    file_path: str, function_name: str, subgraph: Dict[str, Any]
) -> str:
    """Format the enrichment result for resource output"""
    # Find the entry point node key
    entrypoint_keys = [k for k in subgraph.keys() if k.endswith(function_name)]
    if not entrypoint_keys:
        return f"Error: Entry point function {function_name} not found in subgraph"

    entrypoint_key = entrypoint_keys[0]
    entrypoint_node = subgraph[entrypoint_key]

    # Extract direct callees
    direct_callees = entrypoint_node.get("callees", [])

    # Format callees with more detail
    callee_details = []
    for callee in direct_callees:
        callee_node = subgraph.get(callee)
        if callee_node:
            callee_name = callee.split(".")[-1]
            callee_file = callee_node.get("filepath", "Unknown")
            callee_line = callee_node.get("lineno", "Unknown")
            callee_details.append(f"- {callee_name} (in {callee_file}:{callee_line})")
        else:
            callee_name = callee.split(".")[-1]
            callee_details.append(f"- {callee_name} (external)")

    # Get callers (functions that call this function)
    callers = []
    for node_key, node in subgraph.items():
        if node_key == entrypoint_key:
            continue
        if entrypoint_key in node.get("callees", []):
            caller_name = node_key.split(".")[-1]
            caller_file = node.get("filepath", "Unknown")
            caller_line = node.get("lineno", "Unknown")
            callers.append(f"- {caller_name} (in {caller_file}:{caller_line})")

    # Format the result
    result = [
        f"# Function: {function_name}",
        "",
        f"**File:** {file_path}",
        f"**Line:** {entrypoint_node.get('lineno', 'Unknown')}",
        f"**Full path:** {entrypoint_key}",
        "",
        "## Calls",
    ]

    if callee_details:
        result.extend(callee_details)
    else:
        result.append("- This function doesn't call any other functions")

    result.extend(
        [
            "",
            "## Called By",
        ]
    )

    if callers:
        result.extend(callers)
    else:
        result.append("- Not called by any other functions in the analyzed code")

    return "\n".join(result)


@mcp.prompt()
def analyze_function(file_path: str, function_name: str) -> str:
    """Create a prompt to analyze a function with its call graph."""
    return f"""
Please analyze the function '{function_name}' in file '{file_path}'.

First, I need to understand how this function fits into the codebase. Please use the 'get_function_call_graph' tool to retrieve the call graph for this function.

Once you have the call graph, please analyze:

1. What does this function do? (based on its name and call patterns)
2. What other functions does it call? What is the purpose of each call?
3. Which parts of the codebase call this function? In what contexts is it used?
4. Is this a central/critical function in the codebase?
5. What potential bugs or optimization opportunities do you see?

Please provide a comprehensive analysis that helps me understand both the function itself and its role in the broader codebase.
"""


@mcp.prompt()
def impact_analysis(file_path: str, function_name: str) -> str:
    """Create a prompt to analyze the impact of changing a function."""
    return f"""
I'm planning to modify the function '{function_name}' in file '{file_path}'. 

Please use the 'analyze_change_impact' tool to get a detailed impact analysis for this function. 
This will show me which parts of the codebase would be affected by my changes.

Alternatively, you can use the 'get_function_call_graph' tool to retrieve the basic call graph.

Please analyze:

1. Which other parts of the codebase depend on this function?
2. If I change the function signature, what code will need to be updated?
3. Are there any functions that might be particularly sensitive to changes in this function?
4. What tests might I need to update if I modify this function?
5. Based on the call graph, what would be a safe approach to refactoring this function?

Please provide a comprehensive impact analysis to help me plan my changes safely.
"""


@mcp.prompt()
def analyze_dependencies_prompt(file_path: str = None, module_name: str = None) -> str:
    """Create a prompt to analyze dependencies of a file or module."""
    
    target = f"file '{file_path}'" if file_path else f"module '{module_name}'"
    
    return f"""
I need to understand which parts of the codebase depend on {target}. This will help me
assess the impact of making changes to this component.

Please use the 'analyze_dependencies' tool to see all the code that depends on this component.
If you need to see specific function details, you can also use 'get_function_call_graph'.

Once you have the dependency information, please help me understand:

1. How extensively is this component used throughout the codebase?
2. Are there any unexpected dependencies that I should be aware of?
3. Which areas of the codebase would be most affected if I make changes?
4. Can you identify any potential refactoring opportunities to reduce tight coupling?
5. Should I be concerned about making changes to this component?

Please provide a thorough analysis to help me make informed decisions about modifying this code.
"""


if __name__ == "__main__":
    mcp.run()
