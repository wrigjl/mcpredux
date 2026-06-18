#!/usr/bin/env python3
from mcp.server.fastmcp import FastMCP
from typing import Optional
from pathlib import Path
import argparse
import asyncio
import httpx
import json
import sys
import uvicorn

DEFAULT_BASE_URL = "http://redux.portneuf.cose.isu.edu:27000"

# Set by main() before the server starts.
_client: httpx.AsyncClient = None

mcp = FastMCP("redux")


# ── HTTP helpers ──────────────────────────────────────────────────────────────

async def _get(path: str, params: dict = None) -> str:
    r = await _client.get(path, params=params)
    if r.is_error:
        raise RuntimeError(r.text)
    return r.text


async def _post(path: str, body, params: dict = None) -> str:
    r = await _client.post(
        path,
        params=params,
        content=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    if r.is_error:
        raise RuntimeError(r.text)
    return r.text


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
async def reduce_certificate(reduction: str, certificate: str, instance: str) -> str:
    """Apply the reduction's forward direction to a source-problem certificate, returning a target-problem certificate. Mirrors `reduce_problem` on the certificate side: both apply the named reduction in its source→target direction. To go target→source, use the inverse reduction (e.g. SipserReduceToSAT3 instead of SipserReduceToCliqueStandard); call `list_reductions(source=..., target=...)` to find it."""
    return await _post("/ProblemProvider/mapSolution", instance,
                       {"reduction": reduction, "solution": certificate})


@mcp.tool()
async def visualize_problem(visualization: str, instance: str) -> str:
    """Get the visualization of a problem instance. Use list_visualizations to find available visualizations."""
    return await _post("/ProblemProvider/visualize", instance, {"visualization": visualization})


# ── Proxy mode ───────────────────────────────────────────────────────────────

async def _proxy_main(url: str) -> None:
    """Read JSON-RPC from stdin, forward to HTTP MCP server, write responses to stdout."""
    headers = {
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
    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _client

    args = build_parser().parse_args()

    if args.mode == "proxy":
        if not args.proxy_url:
            build_parser().error("--proxy-url is required in proxy mode")
        asyncio.run(_proxy_main(args.proxy_url))
        return

    _client = httpx.AsyncClient(base_url=args.base_url, timeout=30.0)

    if args.mode == "http":
        uvicorn.run(mcp.streamable_http_app(), host=args.host, port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
