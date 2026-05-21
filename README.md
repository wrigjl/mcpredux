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

## Building

Requires Rust 1.70+.

```sh
cargo build --release
```

The binary will be at `target/release/mcp-redux-server`.

## Configuration

Add to your `claude_desktop_config.json` (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "redux": {
      "command": "/path/to/mcpredux/target/release/mcp-redux-server"
    }
  }
}
```

## Dependencies

- [rmcp](https://github.com/modelcontextprotocol/rust-sdk) — official Rust MCP SDK
- [reqwest](https://github.com/seanmonstar/reqwest) — HTTP client
- [tokio](https://tokio.rs) — async runtime
- [serde](https://serde.rs) — JSON serialization
