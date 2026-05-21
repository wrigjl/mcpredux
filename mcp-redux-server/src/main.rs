use rmcp::{handler::server::wrapper::Parameters, schemars, tool, tool_router, ServiceExt, transport::stdio};
use serde::{Deserialize, Serialize};
use urlencoding::encode;

const REDUX_BASE: &str = "http://redux.portneuf.cose.isu.edu:27000";

// ── Service ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ReduxService {
    client: reqwest::Client,
}

impl ReduxService {
    fn new() -> Self {
        Self { client: reqwest::Client::new() }
    }
}

// ── Request types ─────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct ListProblemsRequest {
    #[schemars(description = "Category: all (default), npc, p, or nphard")]
    pub category: Option<String>,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct ProblemLookupRequest {
    #[schemars(description = "Problem name, e.g. SAT3 or CLIQUE")]
    pub problem: String,
    #[schemars(description = "Complexity class: NPC, P, or NPHard")]
    pub problem_type: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct ReductionPathRequest {
    #[schemars(description = "Problem to reduce from, e.g. SAT3")]
    pub reducing_from: String,
    #[schemars(description = "Problem to reduce to, e.g. CLIQUE")]
    pub reducing_to: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct GetInfoRequest {
    #[schemars(description = "Name of any object to inspect: problem (e.g. SAT3), solver, verifier, or reduction")]
    pub interface: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct GenerateProblemRequest {
    #[schemars(description = "Instance type: undirected-graph (default), directed-graph, or sat3")]
    pub problem_type: String,
    #[schemars(description = "Number of nodes (graphs) or variables (sat3); default 5")]
    pub n: Option<i32>,
    #[schemars(description = "Edge density 0-100, graphs only; default 50")]
    pub density: Option<i32>,
    #[schemars(description = "k value for NP-Complete problems, -1 for none, graphs only; default -1")]
    pub k: Option<i32>,
    #[schemars(description = "Clause count, sat3 only; default 3")]
    pub c: Option<i32>,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct SolveProblemRequest {
    #[schemars(description = "Solver name, e.g. Sat3BacktrackingSolver. Use list-solvers to discover options.")]
    pub solver: String,
    #[schemars(description = "Problem instance string")]
    pub instance: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct VerifySolutionRequest {
    #[schemars(description = "Verifier name, e.g. cliqueverifier. Use list-verifiers to discover options.")]
    pub verifier: String,
    #[schemars(description = "Solution certificate string")]
    pub certificate: String,
    #[schemars(description = "Problem instance string")]
    pub problem_instance: String,
}

#[derive(Serialize)]
struct VerifyBody {
    certificate: String,
    #[serde(rename = "problemInstance")]
    problem_instance: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct ReduceProblemRequest {
    #[schemars(description = "Reduction name, e.g. SipserReduceToCliqueStandard. Use list-reductions to discover options.")]
    pub reduction: String,
    #[schemars(description = "Problem instance string")]
    pub instance: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct MapSolutionRequest {
    #[schemars(description = "Reduction name used when the problem was reduced")]
    pub reduction: String,
    #[schemars(description = "Solution certificate for the reduced problem")]
    pub solution: String,
    #[schemars(description = "Original problem instance string")]
    pub instance: String,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
pub struct VisualizeProblemRequest {
    #[schemars(description = "Visualization name, e.g. Sat3DefaultVisualization. Use list-visualizations to discover options.")]
    pub visualization: String,
    #[schemars(description = "Problem instance string")]
    pub instance: String,
}

// ── Tool implementations ──────────────────────────────────────────────────────

#[tool_router(server_handler)]
impl ReduxService {
    #[tool(description = "List problems in the Redux system. Category: all (default), npc (NP-Complete), p (polynomial), or nphard.")]
    async fn list_problems(
        &self,
        Parameters(ListProblemsRequest { category }): Parameters<ListProblemsRequest>,
    ) -> String {
        let path = match category.as_deref().unwrap_or("all").to_lowercase().as_str() {
            "npc"    => "NPC_ProblemsRefactor",
            "p"      => "P_ProblemsRefactor",
            "nphard" => "NPHard_ProblemsRefactor",
            _        => "ALL_ProblemsRefactor",
        };
        api_get(&self.client, &format!("{}/Navigation/{}", REDUX_BASE, path)).await
    }

    #[tool(description = "List all solvers available for a given problem.")]
    async fn list_solvers(
        &self,
        Parameters(ProblemLookupRequest { problem, problem_type }): Parameters<ProblemLookupRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/Navigation/Problem_SolversRefactor?chosenProblem={}&problemType={}",
            REDUX_BASE, encode(&problem), encode(&problem_type)
        )).await
    }

    #[tool(description = "List all verifiers available for a given problem.")]
    async fn list_verifiers(
        &self,
        Parameters(ProblemLookupRequest { problem, problem_type }): Parameters<ProblemLookupRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/Navigation/Problem_VerifiersRefactor?chosenProblem={}&problemType={}",
            REDUX_BASE, encode(&problem), encode(&problem_type)
        )).await
    }

    #[tool(description = "List all reductions available from a given problem.")]
    async fn list_reductions(
        &self,
        Parameters(ProblemLookupRequest { problem, problem_type }): Parameters<ProblemLookupRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/Navigation/Problem_ReductionsRefactor?chosenProblem={}&problemType={}",
            REDUX_BASE, encode(&problem), encode(&problem_type)
        )).await
    }

    #[tool(description = "List all visualizations available for a given problem.")]
    async fn list_visualizations(
        &self,
        Parameters(ProblemLookupRequest { problem, problem_type }): Parameters<ProblemLookupRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/Navigation/Problem_VisualizationsRefactor?chosenProblem={}&problemType={}",
            REDUX_BASE, encode(&problem), encode(&problem_type)
        )).await
    }

    #[tool(description = "Find the chain of reductions between two NP-Complete problems.")]
    async fn find_reduction_path(
        &self,
        Parameters(ReductionPathRequest { reducing_from, reducing_to }): Parameters<ReductionPathRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/Navigation/NPC_NavGraph/reductionPath?reducingFrom={}&reducingTo={}",
            REDUX_BASE, encode(&reducing_from), encode(&reducing_to)
        )).await
    }

    #[tool(description = "Get detailed info about any named object: problem, solver, verifier, or reduction.")]
    async fn get_info(
        &self,
        Parameters(GetInfoRequest { interface }): Parameters<GetInfoRequest>,
    ) -> String {
        api_get(&self.client, &format!(
            "{}/ProblemProvider/info?interface={}",
            REDUX_BASE, encode(&interface)
        )).await
    }

    #[tool(description = "Generate a random problem instance. Types: undirected-graph (default), directed-graph, sat3. Use n/density/k for graphs; n/c for sat3.")]
    async fn generate_problem(
        &self,
        Parameters(GenerateProblemRequest { problem_type, n, density, k, c }): Parameters<GenerateProblemRequest>,
    ) -> String {
        let url = match problem_type.to_lowercase().as_str() {
            "directed-graph" => format!(
                "{}/ProblemGenerator/DirectedGraph?n={}&density={}&k={}",
                REDUX_BASE, n.unwrap_or(5), density.unwrap_or(50), k.unwrap_or(-1)
            ),
            "sat3" => format!(
                "{}/ProblemGenerator/Sat3?n={}&c={}",
                REDUX_BASE, n.unwrap_or(3), c.unwrap_or(3)
            ),
            _ => format!(
                "{}/ProblemGenerator/UndirectedGraph?n={}&density={}&k={}",
                REDUX_BASE, n.unwrap_or(5), density.unwrap_or(50), k.unwrap_or(-1)
            ),
        };
        api_get(&self.client, &url).await
    }

    #[tool(description = "Solve a problem instance using the specified solver. Use list-solvers to find available solvers for a problem.")]
    async fn solve_problem(
        &self,
        Parameters(SolveProblemRequest { solver, instance }): Parameters<SolveProblemRequest>,
    ) -> String {
        api_post_json(&self.client, &format!(
            "{}/ProblemProvider/solve?solver={}",
            REDUX_BASE, encode(&solver)
        ), &instance).await
    }

    #[tool(description = "Verify whether a solution certificate is valid for a problem instance. Returns true or false.")]
    async fn verify_solution(
        &self,
        Parameters(VerifySolutionRequest { verifier, certificate, problem_instance }): Parameters<VerifySolutionRequest>,
    ) -> String {
        api_post_json(
            &self.client,
            &format!("{}/ProblemProvider/verify?verifier={}", REDUX_BASE, encode(&verifier)),
            &VerifyBody { certificate, problem_instance },
        ).await
    }

    #[tool(description = "Reduce a problem instance to another problem using the specified reduction. Use list-reductions to find available reductions.")]
    async fn reduce_problem(
        &self,
        Parameters(ReduceProblemRequest { reduction, instance }): Parameters<ReduceProblemRequest>,
    ) -> String {
        api_post_json(&self.client, &format!(
            "{}/ProblemProvider/reduce?reduction={}",
            REDUX_BASE, encode(&reduction)
        ), &instance).await
    }

    #[tool(description = "Map a solution from the reduced problem back to the original problem.")]
    async fn map_solution(
        &self,
        Parameters(MapSolutionRequest { reduction, solution, instance }): Parameters<MapSolutionRequest>,
    ) -> String {
        api_post_json(&self.client, &format!(
            "{}/ProblemProvider/mapSolution?reduction={}&solution={}",
            REDUX_BASE, encode(&reduction), encode(&solution)
        ), &instance).await
    }

    #[tool(description = "Get the visualization of a problem instance. Use list-visualizations to find available visualizations.")]
    async fn visualize_problem(
        &self,
        Parameters(VisualizeProblemRequest { visualization, instance }): Parameters<VisualizeProblemRequest>,
    ) -> String {
        api_post_json(&self.client, &format!(
            "{}/ProblemProvider/visualize?visualization={}",
            REDUX_BASE, encode(&visualization)
        ), &instance).await
    }
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────

async fn api_get(client: &reqwest::Client, url: &str) -> String {
    match client.get(url).send().await {
        Ok(r)  => r.text().await.unwrap_or_else(|e| format!("Error reading response: {e}")),
        Err(e) => format!("Error calling API: {e}"),
    }
}

async fn api_post_json<T: Serialize>(client: &reqwest::Client, url: &str, body: &T) -> String {
    match client.post(url).json(body).send().await {
        Ok(r)  => r.text().await.unwrap_or_else(|e| format!("Error reading response: {e}")),
        Err(e) => format!("Error calling API: {e}"),
    }
}

// ── Entry point ───────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let service = ReduxService::new().serve(stdio()).await?;
    service.waiting().await?;
    Ok(())
}
