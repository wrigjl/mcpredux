# mcpredux

A [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server
that exposes the [Redux](https://redux.portneuf.cose.isu.edu/) algorithms
API as tools for AI assistants. Redux provides solvers, verifiers, and
polynomial reductions for a wide range of computational complexity
problems including NP-Complete, NP-Hard, and P-class problems.

## Tools

| Tool | Description |
|---|---|
| `list_problems` | List all problems, optionally filtered by class (`all`, `npc`, `p`, `nphard`) |
| `list_solvers` | List solvers available for a given problem |
| `list_verifiers` | List verifiers available for a given problem |
| `list_reductions` | List reductions available from a given problem |
| `list_visualizations` | List visualizations available for a given problem |
| `find_reduction_path` | Find the chain of reductions between two NP-Complete problems |
| `get_info` | Get detailed info about any named object (problem, solver, verifier, reduction) |
| `generate_problem` | Generate a random problem instance (undirected graph, directed graph, or 3SAT) |
| `solve_problem` | Solve a problem instance using a named solver |
| `verify_solution` | Check whether a solution certificate is valid for a problem instance |
| `reduce_problem` | Reduce a problem instance to another problem via a named reduction |
| `map_solution` | Map a solution from the reduced problem back to the original |
| `visualize_problem` | Get the visualization of a problem instance |

## Setup

Requires Python 3.10+.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Modes

### stdio (default)

Runs as a local MCP server over stdin/stdout. Used when the client and
server are on the same machine.

```sh
python server.py [--base-url URL]
```

Claude Desktop / Claude Code config:

```json
{
  "mcpServers": {
    "redux": {
      "command": "/path/to/mcpredux/.venv/bin/python",
      "args": ["/path/to/mcpredux/server.py"]
    }
  }
}
```

### http

Runs as an HTTP server (streamable-HTTP MCP transport) suitable for
deployment behind a reverse proxy such as nginx. Access is controlled
by bearer tokens stored in a SQLite database.

```sh
python server.py --mode http [--host 127.0.0.1] [--port 8000] [--token-file FILE]
```

**Token management:**

```sh
# Generate a new token and print it
python server.py tokens generate --description "Alice's laptop"

# Add an existing token
python server.py tokens add <token> --description "Bob's machine"

# List all tokens (truncated)
python server.py tokens list

# Revoke a token
python server.py tokens remove <token>
```

Tokens are stored at `~/.config/mcpredux/tokens.db` by default.

Claude Code config (supports remote HTTP natively):

```json
{
  "mcpServers": {
    "redux": {
      "type": "http",
      "url": "https://your-server/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

### proxy

Bridges Claude Desktop (stdio only) to a remote HTTP MCP server.
Claude Desktop spawns this process locally; it forwards all traffic
to the remote server with the bearer token attached.

```sh
python server.py --mode proxy --proxy-url https://your-server/mcp --proxy-token <token>
```

Claude Desktop config:

```json
{
  "mcpServers": {
    "redux": {
      "command": "/path/to/mcpredux/.venv/bin/python",
      "args": [
        "/path/to/mcpredux/server.py",
        "--mode", "proxy",
        "--proxy-url", "https://your-server/mcp",
        "--proxy-token", "<token>"
      ]
    }
  }
}
```

## Dependencies

- [mcp](https://github.com/modelcontextprotocol/python-sdk) — official Python MCP SDK (FastMCP)
- [httpx](https://www.python-httpx.org) — async HTTP client
- [uvicorn](https://www.uvicorn.org) — ASGI server (http mode)
