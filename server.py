#!/usr/bin/env python3
from mcp.server.fastmcp import FastMCP
from typing import Optional
import httpx

REDUX_BASE = "http://redux.portneuf.cose.isu.edu:27000"

mcp = FastMCP("redux")
_client = httpx.AsyncClient(base_url=REDUX_BASE, timeout=30.0)


async def _get(path: str, params: dict = None) -> str:
    try:
        r = await _client.get(path, params=params)
        return r.text
    except Exception as e:
        return f"Error: {e}"


async def _post(path: str, body, params: dict = None) -> str:
    try:
        r = await _client.post(path, params=params, json=body)
        return r.text
    except Exception as e:
        return f"Error: {e}"


# ── Discovery ─────────────────────────────────────────────────────────────────

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
async def list_reductions(problem: str, problem_type: str) -> str:
    """List all reductions available from a given problem. problem_type: NPC, P, or NPHard."""
    return await _get("/Navigation/Problem_ReductionsRefactor",
                      {"chosenProblem": problem, "problemType": problem_type})


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
    """Get detailed info about any named object: problem (e.g. SAT3), solver, verifier, or reduction."""
    return await _get("/ProblemProvider/info", {"interface": interface})


# ── Generation ────────────────────────────────────────────────────────────────

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


# ── Core operations ───────────────────────────────────────────────────────────

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


if __name__ == "__main__":
    mcp.run()
