# Literature and novelty

_Survey of 2026-11-19. Most entries were checked through abstracts or search summaries only; read the
closest papers in full before writing the paper, and re-check for new work (the field moves monthly)._

## Base papers
- **MAGIS** (NeurIPS 2024, [2403.17927](https://arxiv.org/abs/2403.17927)): Manager, Custodian (BM25 + LLM
  filter + file-summary memory), Developer (line-range edits), QA (LLM review, Developer ↔ QA loop).
  13.94% on a 25% SWE-bench subset with GPT-4 (likely the oracle-retrieval setting; the code defaults to
  oracle files), 25.33% on Lite. Uses `hints_text` in the headline setting. No token numbers reported.
  Code: [co-evolve-lab/magis](https://github.com/co-evolve-lab/magis).
- **SWE-Pruner** ([2601.16746](https://arxiv.org/abs/2601.16746)): 0.6B skimmer (Qwen3-Reranker-0.6B + CRF
  head) as middleware on tool outputs, goal hint written by the agent, line-level, τ = 0.5. 23–54% fewer
  tokens; e.g. Claude Sonnet 4.5 70.6% → 72.0% on Verified with 23% fewer tokens. AST correctness drops
  (92.3% → 87.3% on Function RAG). Code: [Ayanami1314/swe-pruner](https://github.com/Ayanami1314/swe-pruner).

## Novelty by direction
| Direction | Novelty | Closest work | Open gap |
|---|---|---|---|
| Prune-Verify-Expand | Medium | ContextSniper, Object-Centric Env. Modeling, progressive disclosure, SWE-Doctor | context expansion triggered by test-failure tracebacks + routing in a multi-agent pipeline |
| **Budget allocation (chosen)** | **High** | CodeMonkeys (serial vs parallel, Claude, no context axis), CUDABeaver (sampling vs iteration, CUDA) | context × rounds × samples × execution under one matched budget, small models |
| Empirical multi- vs single-agent | Medium | Failures study 2509.13941 (strong models), MAST, leaderboard dissection | controlled comparison with small open models |
| Per-role context/model | Low–Med | SWE-Edit, SWE-Router, timeout cascades, MasRouter, AgentPrune | per-role allocation inside a MAGIS-style pipeline, small models only |
| Localization / fine-tuning | Low | SweRank, LocAgent, CoSIL; SWE-smith, SWE-Gym, SWE-Lego | crowded |

## Key papers
**Context pruning / management**
- SWE-Pruner Pro ([2607.18213](https://arxiv.org/abs/2607.18213)): line labels from the coder LLM's hidden states; up to 39% fewer tokens, +3.8% on Verified.
- LaMR ([2605.15315](https://arxiv.org/abs/2605.15315)): semantic + dependency rubrics, AST-derived labels; single agent.
- The Complexity Trap ([2508.21433](https://arxiv.org/abs/2508.21433)): observation masking ≈ LLM summarization at half the cost. Mandatory baseline.
- ContextSniper ([2607.01916](https://arxiv.org/abs/2607.01916)): compact evidence, full source on demand; 40–52% fewer tokens.
- Object-Centric Environment Modeling ([2607.02846](https://arxiv.org/pdf/2607.02846)); Progressive disclosure ([2607.17598](https://arxiv.org/pdf/2607.17598)).
- Beyond Token Savings ([2609.32961](https://arxiv.org/html/2609.32961v1)): similar token counts, ~12-point spread in resolve rate.
- Fault localization context ([2604.05481](https://arxiv.org/abs/2604.05481)): file-level dominates; line-level expansion often hurts.

**Execution feedback**
- To Run or Not to Run ([2606.26978](https://arxiv.org/abs/2606.26978), ISSTA 2026): banning execution changes strong agents' resolve rate by 1.25 points (n.s.). Small models untested.
- SWE-Doctor ([2607.00990](https://arxiv.org/pdf/2607.00990)): runtime diagnosis from reproduction tests.
- CodePilot ([2602.00129](https://arxiv.org/html/2602.00129v1)): MCTS with execution reward, Qwen3-8B 24.67% on Lite.
- Meta, Agentic Program Repair from Test Failures ([2507.18755](https://arxiv.org/pdf/2507.18755)).

**Test-time scaling**
- CodeMonkeys ([2501.14723](https://arxiv.org/abs/2501.14723)); CUDABeaver ([2605.08455](https://arxiv.org/pdf/2605.08455)); Satori-SWE ([2505.23604](https://arxiv.org/pdf/2505.23604)); SWE-Replay ([2601.22129](https://arxiv.org/pdf/2601.22129)).

**Empirical / multi-agent**
- Failures in Automated Issue Solving ([2509.13941](https://arxiv.org/html/2509.13941v1)); trajectories ([2511.00197](https://arxiv.org/html/2511.00197v1)); MAST ([2503.13657](https://arxiv.org/abs/2503.13657)); leaderboard dissection ([2506.17208](https://arxiv.org/html/2506.17208v2)).
- SWE-Edit ([2604.26102](https://arxiv.org/abs/2604.26102)); SWE-Router ([2607.00053](https://arxiv.org/html/2607.00053v1)); timeout cascades ([2611.24324](https://arxiv.org/html/2611.24324)); MasRouter ([2502.11133](https://arxiv.org/abs/2502.11133)); AgentPrune ([2410.02506](https://arxiv.org/abs/2410.02506)).

**Benchmarks and validity**
- SWE-Bench Illusion ([2506.12286](https://arxiv.org/abs/2506.12286)): file paths memorized (up to 76%).
- SWE-rebench ([2505.20411](https://arxiv.org/abs/2505.20411)): fresh monthly tasks.
- OpenAI (Feb 2026, reported): many hard Verified tasks have flawed tests.

**Small-model reference points**
- 7–8B on Verified: SWE-agent-LM-7B 15.2%, SWE-Dev-7B 23.4%, SWE-Lego-Qwen3-8B 42.2% (fine-tuned).
- Qwen2.5-7B-Instruct in a generic agent: 2.67% on Lite. SWE-Fixer (fine-tuned): 24.7% on Lite.
- Localization: SweRank ([2505.07849](https://arxiv.org/abs/2505.07849), ICLR 2026).
