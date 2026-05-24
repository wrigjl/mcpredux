# TODO — Redux API self-documentation

Goal: keep the MCP server (`server.py`) a thin HTTP wrapper. Push
direction-awareness, shape-awareness, examples, and error semantics into the
Redux API itself so any client — MCP, the GUI, a curl invocation, or a future
LLM — gets the same legible surface.

Working order is roughly cheapest → deepest. Each item names the file(s) in
`~/Documents/CS6680/Redux/` (and occasionally `Redux_GUI/`).

---

## 1. Make `IReduction` self-describing

`Interfaces/ReductionInterface.cs` currently declares only `mapSolutions`.
Concrete reductions hold richer information (`reductionFrom`, `reductionTo`,
`reductionName`, `reductionDefinition`, `source`) but the interface doesn't
require it. The LLM sees a name like `SipserReduceToSAT3` and can't tell from
the API alone what its input/output shapes are.

- [ ] Promote to `IReduction`:
  - `string sourceProblem` (e.g. `"CLIQUE"`)
  - `string targetProblem` (e.g. `"SAT3"`)
  - `string sourceInstanceExample`
  - `string targetInstanceExample`
  - `string sourceSolutionExample` (e.g. `"{x1_0,x2_1,!x3_3}"`)
  - `string targetSolutionExample` (e.g. `"(x1:True,x2:False,x3:False)"`)
- [ ] Backfill these on every concrete reduction under
  `Problems/NPComplete/*/ReduceTo/*/`. Use existing controller XML
  `example=` attributes as the seed values — they already exist for the SAT3
  controllers.
- [ ] Have `ProblemProvider/info?interface=<reductionName>` serialize this
  block verbatim. The LLM (or anyone) calls `get_info` once and learns the
  full contract.

## 1.5. Make `IProblem` declare its instance and certificate formats

Distinct from §1 (which puts examples on each *reduction*): the canonical
instance and certificate formats are properties of the *problem* — its
verifier defines what a valid certificate is. Per-reduction examples may
still be useful when a reduction's output is a constrained subset, but the
authoritative format lives with the problem.

Observed failure (gut-check transcript): LLM submitted SAT3 certificate
as `x1=true,x2=true,x3=false,x4=true`. The verifier silently dropped the
malformed lowercase booleans and returned `false` with no hint — the LLM
had no way to know `True`/`False` casing was required. See paper-stuff
catalog entry `problem-format-undeclared`.

- [x] Add `string instanceFormat` and `string certificateFormat` to
  `IProblem` (`Interfaces/ProblemInterface.cs`) with default impl `""`
  so backfill can be incremental.
- [x] Populate on SAT3 and CLIQUE as the pilot.
- [x] Add `ProblemParseException` / `CertificateParseException` and
  wire SAT3 + CLIQUE constructors and verifiers to throw on malformed
  input. `/verify` and `/problemInstance` now return HTTP 400 with a
  structured body `{error, problem, expected, received, detail}` where
  `expected` is the matching `instanceFormat`/`certificateFormat`.
  Verified live against the original gut-check certificate.
- [ ] Backfill the remaining ~41 `Problems/NPComplete/*/*_Class.cs`
  classes. Mechanical: read each problem's verifier to determine the
  exact format, then write a short descriptive sentence with an embedded
  example. Quantum problems may need extra care (qasm strings,
  measurement outcomes).
- [ ] Extend the validate-and-throw pattern to the remaining verifiers
  and constructors. Same shape as SAT3/CLIQUE; once §5's
  `ReductionInputException` lands the patterns align across all three
  parse sites (problem, certificate, reduction input).

## 2. Decide what `mapSolution` means, in one place

There are currently two overlapping forward-map surfaces:

| Route | Body shape | Notes |
|---|---|---|
| `POST /ProblemProvider/mapSolution?reduction=&solution=` | body = instance | Generic, reflection-dispatched |
| `POST /<ReductionName>/mapSolution` | `{problemFrom, problemTo, problemFromSolution}` | Per-reduction, only on a few controllers (SAT3's children) |

The GUI used to use a third (`reverseMappedSolution`) — now removed in
`Redux_GUI/components/redux/index.js`.

- [ ] Pick the generic `/ProblemProvider/mapSolution` as the canonical
  forward-map route. With `SipserReduceToSAT3` registered, both directions
  are now forward maps under different reduction names, so there is no
  remaining reason to keep per-reduction map routes.
- [ ] Mark the per-reduction `mapSolution` endpoints in
  `SipserReduceToCliqueStandardController`, `KarpReduceGRAPHCOLORINGController`,
  `KarpIntProgStandardController`, `GareyJohnsonController` (all in
  `Problems/NPComplete/NPC_SAT3/SAT3_Controller.cs`) deprecated, then remove
  in a follow-up once any remaining GUI callers are converted.
- [ ] Audit `Redux_GUI/components/redux/index.js` `requestMappedSolution`
  (line ~336) which still calls `${url}${reduction}/mapSolution`. Switch to
  the generic route. Same body-shape difference as the recent
  `reverseMappedSolution` fix.

## 3. Delete the dead reverse-map code (already de-referenced)

The `reverseMappedSolution` endpoint and method are no longer called by
anything (GUI now uses `SipserReduceToSAT3` via the generic forward path).

- [ ] Remove `[HttpPost("reverseMappedSolution")]` block in
  `Problems/NPComplete/NPC_SAT3/SAT3_Controller.cs:80-93`.
- [ ] Remove `reverseMapSolutions(...)` in
  `Problems/NPComplete/NPC_SAT3/ReduceTo/NPC_CLIQUE/SipserReduceToCliqueStandard.cs:391-...`
  once the endpoint is gone — orphan otherwise.
- [ ] Remove the orphaned `using API.Problems.NPComplete.NPC_CLIQUE.Inherited`
  import in `SAT3_Controller.cs` if it becomes unused.

## 4. Audit reductions for inverse coverage

For each reduction with a `<Source>To<Target>` class, check whether a
matching `<Target>To<Source>` inverse exists. Where it doesn't, the LLM can
forward-reduce but cannot map a target-solution back to a source-solution —
the entire point of a reduction as a solver.

- [ ] `NPC_SAT3/ReduceTo/NPC_DM3/GareyJohnson` — inverse?
- [ ] `NPC_SAT3/ReduceTo/NPC_GRAPHCOLORING/KarpReduceGRAPHCOLORING` — inverse?
- [ ] `NPC_SAT3/ReduceTo/NPC_INTPROGRAMMING01/KarpIntProgStandard` — inverse?
- [ ] `NPC_CLIQUE/ReduceTo/NPC_VertexCover/sipserReductionVertexCover` — inverse?
- [ ] `NPC_INDEPENDENTSET/ReduceTo/NPC_CLIQUE/reduceToCLIQUE` — inverse?
- [ ] `NPC_DIRECTEDHAMILTONIAN/ReduceTo/NPC_HAMILTONIAN/KarpDirectedHamiltonianToUndirectedHamiltonian` — inverse?
- [ ] `NPC_PARTITION/ReduceTo/NPC_WEIGHTEDCUT/WEIGHTEDCUTReduction` — inverse?
- [ ] `NPC_SAT/ReduceTo/NPC_SAT3/KarpSATToSAT3` — inverse?
- [ ] `NPC_EXACTCOVER/ReduceTo/NPC_SUBSETSUM/KarpExactCoverToSubsetSum` — inverse?
- [ ] `NPC_VERTEXCOVER/ReduceTo/NPC_NODESET/KarpVertexCoverToNodeSet` — inverse?
- [ ] `NPC_SUBSETSUM/ReduceTo/NPC_PARTITION/SubsetSumToPartitionReduction` — inverse?
- [ ] `NPC_VERTEXCOVER/ReduceTo/NPC_ARCSET/LawlerKarp` — inverse?
- [ ] `NPC_VERTEXCOVER/ReduceTo/NPC_SETCOVER/KarpVertexCoverToSetCover` — inverse?
- [ ] `NPC_GRAPHCOLORING/ReduceTo/NPC_CLIQUECOVER/GraphColoringToCliqueCover` — inverse?
- [ ] `NPC_GRAPHCOLORING/ReduceTo/NPC_ExactCover/KarpGraphColorToExactCover` — inverse?
- [ ] `NPC_SUBSETSUM/ReduceTo/NPC_KNAPSACK/FengReduction` — inverse?
- [ ] `NPC_GRAPHCOLORING/ReduceTo/NPC_SAT/KarpReduceSAT` — inverse?
- [ ] `NPC_HITTINGSET/ReduceTo/NPC_EXACTCOVER/reduceToEXACTCOVER` — inverse?

For any inverse that isn't pedagogically meaningful, leave it out — but say
so explicitly in the forward reduction's `reductionDefinition` so the LLM
doesn't waste turns hunting for it.

## 5. Validate at the controller boundary, fail with 400 + hint

`SipserReduceToCliqueStandard.mapSolutions` threw `IndexOutOfRangeException`
on a clique-shaped certificate because `Split(":")` returned a single
element. That became HTTP 500 with a stack trace. Any client (MCP, GUI,
curl) gets opaque output.

- [ ] Add input validation in each `mapSolutions` implementation (or wrap
  the controller call). On bad shape, throw a typed
  `ReductionInputException` carrying the expected example and the offending
  input.
- [ ] Have `ProblemProvider.mapSolution` (and friends) catch that exception
  and return HTTP 400 with a JSON body:
  ```json
  {
    "error": "input_shape_mismatch",
    "reduction": "SipserReduceToCliqueStandard",
    "expected_example": "(x1:True,x2:False,...)",
    "received": "{x1_0,x2_1,!x3_3}",
    "hint": "This input looks like a CLIQUE certificate. Use reduction=SipserReduceToSAT3 to map in that direction."
  }
  ```
- [ ] Once 400 + structured body lands, the MCP server no longer needs to
  sniff response bodies for hidden errors. `is_error=true` becomes truthful.

## 7. OpenAPI exposure

Swagger comments are already attached to controllers (`<param example=...>`,
`<response>`). Make sure they survive into the served OpenAPI spec at
`/swagger/v1/swagger.json`.

- [ ] Confirm OpenAPI spec includes `example` fields on
  `ProblemProvider/mapSolution`'s `solution` and body parameters.
- [ ] Once examples are reliable, consider having the MCP server fetch the
  spec at startup and use the descriptions/examples as authoritative — so
  Python tool docstrings can stay one-liners and not duplicate API docs.

## 8. Purge dead pre-`Refactor` Navigation controllers

Every `AdditionalControllers/Navigation/Nav_*.cs` file ships a pair: an old
controller and its `*Refactor` replacement. The GUI, MCP server, and paper
harness all call only the `*Refactor` variants. The old ones are uncalled
dead code that still appears in the OpenAPI surface, making the API noisier
than it needs to be.

Confirmed uncalled (grep'd across Redux, Redux_GUI, mcpredux, mcpreduxpaper):

- `Nav_Visualizations.cs`
  - `All_VisualizationsController`
  - `Problem_VisualizationsController` (superseded by `Problem_VisualizationsRefactor`)
- `Nav_Verifiers.cs`
  - `All_VerifiersController`
  - `Problem_VerifiersController` (superseded by `Problem_VerifiersRefactor`)
- `Nav_Solvers.cs`
  - `All_SolversController`
  - `Problem_SolversController` (superseded by `Problem_SolversRefactor`)

Action items:

- [ ] Delete the controllers above.
- [ ] Once removed, rename the `*Refactor` controllers to drop the suffix
  (`Problem_VisualizationsRefactorController` → `Problem_VisualizationsController`,
  etc.) so the OpenAPI surface stops advertising a refactor that's complete.
  Update GUI and MCP call sites in the same commit:
  - `Redux_GUI/components/redux/index.js` lines 461, 472, 512, plus the
    `*Refactor` URLs in `list_solvers` / `list_verifiers` /
    `list_visualizations` in `server.py`.
- [ ] Audit `Nav_Problems.cs` — its controllers are already `*Refactor`-only
  (no pre-refactor pair), so just drop the suffix to match.

## 9. Naming legibility (lower priority, paper-relevant)

`SipserReduceToSAT3` doesn't say what it reduces *from*. A reader has to
look up the directory or read `reductionFrom`. Optional rename pass once §1
makes the metadata first-class:

- [ ] Adopt `<Source>To<Target>` style class names project-wide
  (e.g. `SipserCliqueToSAT3`, `SipserSAT3ToClique`), or leave the names
  alone and rely on `sourceProblem`/`targetProblem` being on the interface.
  Worth a one-line decision in `CLAUDE.md`/`Readme.md` either way.

---

## Out of scope (covered elsewhere)

- MCP-layer `map_forward`/`map_reverse` split — superseded by
  `SipserReduceToSAT3` existing. The MCP `map_solution` tool stays single,
  with the docstring pointing at `get_info(<reduction>)` for the contract.
  Update `redux-todo.md` in `~/Documents/mcpreduxpaper/` to reflect this.
- The paper harness itself (`~/Documents/mcpreduxpaper/`).
