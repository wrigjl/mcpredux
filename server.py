#!/usr/bin/env python3
from mcp.server.fastmcp import FastMCP
from typing import Optional
from pathlib import Path
from datetime import date
import argparse
import asyncio
import httpx
import json
import secrets
import sqlite3
import sys
import uvicorn

DEFAULT_BASE_URL = "http://redux.portneuf.cose.isu.edu:27000"
DEFAULT_TOKEN_FILE = Path.home() / ".config" / "mcpredux" / "tokens.db"

# Set by main() before the server starts.
_client: httpx.AsyncClient = None

mcp = FastMCP("redux")


# ── Token DB helpers ──────────────────────────────────────────────────────────

def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token       TEXT PRIMARY KEY,
            description TEXT NOT NULL DEFAULT '',
            created     TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

def token_exists(path: Path, token: str) -> bool:
    with _db(path) as conn:
        return conn.execute(
            "SELECT 1 FROM tokens WHERE token = ?", (token,)
        ).fetchone() is not None

def token_add(path: Path, token: str, description: str = "") -> None:
    with _db(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tokens (token, description, created) VALUES (?, ?, ?)",
            (token, description, str(date.today())),
        )

def token_remove(path: Path, token: str) -> bool:
    with _db(path) as conn:
        cur = conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
        return cur.rowcount > 0

def token_list(path: Path) -> list:
    with _db(path) as conn:
        return conn.execute(
            "SELECT token, description, created FROM tokens ORDER BY created, token"
        ).fetchall()


# ── Auth middleware ───────────────────────────────────────────────────────────

class BearerAuthMiddleware:
    def __init__(self, app, token_file: Path):
        self.app = app
        self.token_file = token_file

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            auth = headers.get(b"authorization", b"").decode()
            if auth.startswith("Bearer "):
                token = auth[len("Bearer "):]
                if token_exists(self.token_file, token):
                    await self.app(scope, receive, send)
                    return
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "Unauthorized"}',
                "more_body": False,
            })
        else:
            await self.app(scope, receive, send)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get(path: str, params: dict = None) -> str:
    try:
        r = await _client.get(path, params=params)
        return r.text
    except Exception as e:
        return f"Error: {e}"


async def _post(path: str, body, params: dict = None) -> str:
    try:
        r = await _client.post(
            path,
            params=params,
            content=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return r.text
    except Exception as e:
        return f"Error: {e}"


# ── Discovery tools ───────────────────────────────────────────────────────────

@mcp.tool()
async def list_problems(category: str = "all") -> str:
    """List problems in the Redux system. Category: all (default), npc (NP-Complete), p (polynomial), or nphard."""
    paths = {
        "npc":    "/Navigation/NPC_ProblemsRefactor",
        "p":      "/Navigation/P_ProblemsRefactor",
        "nphard": "/Navigation/NPHard_ProblemsRefactor",
    }
    return await _get(paths.get(category.lower(), "/Navigation/ALL_ProblemsRefactor"))


@mcp.tool()
async def list_solvers(problem: str, problem_type: str) -> str:
    """List all solvers available for a given problem. problem_type: NPC, P, or NPHard."""
    return await _get("/Navigation/Problem_SolversRefactor",
                      {"chosenProblem": problem, "problemType": problem_type})


@mcp.tool()
async def list_verifiers(problem: str, problem_type: str) -> str:
    """List all verifiers available for a given problem. problem_type: NPC, P, or NPHard."""
    return await _get("/Navigation/Problem_VerifiersRefactor",
                      {"chosenProblem": problem, "problemType": problem_type})


@mcp.tool()
async def list_reductions(source: Optional[str] = None, target: Optional[str] = None) -> str:
    """Return the reduction graph as an adjacency map: from -> to -> [{className, endpoint, inputType, outputType}].
    Omit both source and target to get the full graph for multi-step planning.
    Pass source (e.g. "CLIQUE") to filter to edges originating there.
    Pass target to filter to edges ending there. Both filters compose."""
    params = {}
    if source is not None:
        params["source"] = source
    if target is not None:
        params["target"] = target
    return await _get("/Navigation/Reductions", params or None)


@mcp.tool()
async def list_visualizations(problem: str, problem_type: str) -> str:
    """List all visualizations available for a given problem. problem_type: NPC, P, or NPHard."""
    return await _get("/Navigation/Problem_VisualizationsRefactor",
                      {"chosenProblem": problem, "problemType": problem_type})


@mcp.tool()
async def find_reduction_path(reducing_from: str, reducing_to: str) -> str:
    """Find the chain of reductions between two NP-Complete problems (e.g. SAT3 -> CLIQUE)."""
    return await _get("/Navigation/NPC_NavGraph/reductionPath",
                      {"reducingFrom": reducing_from, "reducingTo": reducing_to})


@mcp.tool()
async def get_info(interface: str) -> str:
    """Get detailed info about any named object: problem (e.g. SAT3), solver, verifier, or reduction. For problems, the response includes `instanceFormat` and `certificateFormat` describing the exact input shapes the solver/verifier expect — read these before constructing an instance or certificate."""
    return await _get("/ProblemProvider/info", {"interface": interface})


# ── Generation tools ──────────────────────────────────────────────────────────

@mcp.tool()
async def generate_problem(
    problem_type: str = "undirected-graph",
    n: Optional[int] = None,
    density: Optional[int] = None,
    k: Optional[int] = None,
    c: Optional[int] = None,
) -> str:
    """Generate a random problem instance.
    problem_type: undirected-graph (default), directed-graph, or sat3.
    n: nodes (graphs) or variables (sat3). density: edge density 0-100 (graphs).
    k: NP-Complete k value, -1 for none (graphs). c: clause count (sat3).
    """
    t = problem_type.lower()
    if t == "sat3":
        return await _get("/ProblemGenerator/Sat3",
                          {"n": n or 3, "c": c or 3})
    elif t == "directed-graph":
        return await _get("/ProblemGenerator/DirectedGraph",
                          {"n": n or 5, "density": density or 50, "k": k if k is not None else -1})
    else:
        return await _get("/ProblemGenerator/UndirectedGraph",
                          {"n": n or 5, "density": density or 50, "k": k if k is not None else -1})


# ── Core operation tools ──────────────────────────────────────────────────────

@mcp.tool()
async def solve_problem(solver: str, instance: str) -> str:
    """Solve a problem instance using the named solver. Use list_solvers to find available solvers."""
    return await _post("/ProblemProvider/solve", instance, {"solver": solver})


@mcp.tool()
async def verify_solution(verifier: str, certificate: str, problem_instance: str) -> str:
    """Verify whether a solution certificate is valid for a problem instance. Returns true or false."""
    return await _post("/ProblemProvider/verify",
                       {"certificate": certificate, "problemInstance": problem_instance},
                       {"verifier": verifier})


@mcp.tool()
async def reduce_problem(reduction: str, instance: str) -> str:
    """Reduce a problem instance to another problem. Use list_reductions to find available reductions."""
    return await _post("/ProblemProvider/reduce", instance, {"reduction": reduction})


@mcp.tool()
async def map_solution(reduction: str, solution: str, instance: str) -> str:
    """Map a solution from the reduced problem back to the original problem."""
    return await _post("/ProblemProvider/mapSolution", instance,
                       {"reduction": reduction, "solution": solution})


@mcp.tool()
async def visualize_problem(visualization: str, instance: str) -> str:
    """Get the visualization of a problem instance. Use list_visualizations to find available visualizations."""
    return await _post("/ProblemProvider/visualize", instance, {"visualization": visualization})


# ── Proxy mode ───────────────────────────────────────────────────────────────

async def _proxy_main(url: str, token: str) -> None:
    """Read JSON-RPC from stdin, forward to HTTP MCP server, write responses to stdout."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    session_id = None

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin.buffer,
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            hdrs = {**headers}
            if session_id:
                hdrs["Mcp-Session-Id"] = session_id

            try:
                async with client.stream("POST", url, content=line, headers=hdrs) as resp:
                    if sid := resp.headers.get("Mcp-Session-Id"):
                        session_id = sid

                    if resp.status_code == 202:
                        continue  # notification accepted, no response body

                    ct = resp.headers.get("content-type", "")
                    if "text/event-stream" in ct:
                        async for event_line in resp.aiter_lines():
                            if event_line.startswith("data: "):
                                data = event_line[6:].strip()
                                if data and data != "[DONE]":
                                    sys.stdout.buffer.write(data.encode() + b"\n")
                                    sys.stdout.buffer.flush()
                    else:
                        body = (await resp.aread()).strip()
                        if body:
                            sys.stdout.buffer.write(body + b"\n")
                            sys.stdout.buffer.flush()
            except Exception as e:
                err = {"jsonrpc": "2.0", "id": None,
                       "error": {"code": -32603, "message": f"Proxy error: {e}"}}
                sys.stdout.buffer.write(json.dumps(err).encode() + b"\n")
                sys.stdout.buffer.flush()


# ── Argument parsing ──────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redux algorithms MCP server")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        metavar="URL",
        help="Redux API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--mode",
        choices=["stdio", "http", "proxy"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--proxy-url",
        metavar="URL",
        help="MCP HTTP endpoint to proxy to (proxy mode)",
    )
    parser.add_argument(
        "--proxy-token",
        metavar="TOKEN",
        help="Bearer token for the remote MCP server (proxy mode)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help="HTTP listen address (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        metavar="PORT",
        help="HTTP listen port (default: %(default)s)",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        metavar="FILE",
        help="Bearer token store (default: %(default)s)",
    )

    sub = parser.add_subparsers(dest="subcommand")
    tokens = sub.add_parser("tokens", help="Manage bearer tokens")
    tok_sub = tokens.add_subparsers(dest="token_cmd")

    gen = tok_sub.add_parser("generate", help="Generate and save a new token")
    gen.add_argument("--description", default="", metavar="TEXT")

    add = tok_sub.add_parser("add", help="Add an existing token")
    add.add_argument("token")
    add.add_argument("--description", default="", metavar="TEXT")

    rm = tok_sub.add_parser("remove", help="Revoke a token")
    rm.add_argument("token")

    tok_sub.add_parser("list", help="List all tokens")

    return parser


# ── Token subcommand handler ──────────────────────────────────────────────────

def handle_tokens(args):
    path: Path = args.token_file
    if args.token_cmd == "generate":
        token = secrets.token_urlsafe(32)
        token_add(path, token, args.description)
        print(token)

    elif args.token_cmd == "add":
        token_add(path, args.token, args.description)
        print("Token added.")

    elif args.token_cmd == "remove":
        if not token_remove(path, args.token):
            print("Token not found.", file=sys.stderr)
            sys.exit(1)
        print("Token removed.")

    elif args.token_cmd == "list":
        rows = token_list(path)
        if not rows:
            print("No tokens.")
            return
        for tok, desc, created in rows:
            print(f"{tok[:12]}…  {created}  {desc or '(no description)'}")

    else:
        print("Usage: server.py tokens {generate|add|remove|list}", file=sys.stderr)
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _client

    args = build_parser().parse_args()

    if args.subcommand == "tokens":
        handle_tokens(args)
        return

    if args.mode == "proxy":
        if not args.proxy_url:
            build_parser().error("--proxy-url is required in proxy mode")
        if not args.proxy_token:
            build_parser().error("--proxy-token is required in proxy mode")
        asyncio.run(_proxy_main(args.proxy_url, args.proxy_token))
        return

    _client = httpx.AsyncClient(base_url=args.base_url, timeout=30.0)

    if args.mode == "http":
        app = BearerAuthMiddleware(mcp.streamable_http_app(), args.token_file)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
