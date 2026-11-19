"""
Config B as a LangGraph state graph (see docs/DESIGN_CONFIG_B.md).
"""
import traceback
from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from log import log
from repair import router
from repair.magis_adapter import MagisTeam
from repair.reproducer import write_reproduction

logger = log(__name__).get_log_obj()


class RepairState(TypedDict, total=False):
    candidate_files: list
    reproduced: bool
    fresh_team: bool # the team was (re)built and has not worked yet
    round: int # verification rounds done
    route: str
    reason: str
    critique: Optional[str]
    signature: Optional[str]
    target_files: list
    new_files: list
    patch: str
    last_applied_patch: str
    resolved: Optional[bool] # None = unknown (no reproduction test)
    history: list


class RepairSession:
    """One SWE-bench instance. `runner` is a sandbox runner bound to this instance."""
    def __init__(self, issue, repo_path, runner, model_name, version, candidate_files=None,
                 max_feedback_rounds=3, hints_text=False, bm_top_k=20):
        self.issue = issue
        self.runner = runner
        self.model_name = model_name
        self.oracle_files = candidate_files
        self.max_feedback_rounds = max_feedback_rounds
        self.team = MagisTeam(repo_path, issue, model_name, version, hints_text=hints_text, bm_top_k=bm_top_k)
        self.script = None
        self.reproduction_attempts = []

    # nodes
    def localize(self, state):
        files = list(self.oracle_files) if self.oracle_files is not None else self.team.localize()
        logger.info(f"Candidate files: {files}")
        return {"candidate_files": files, "round": 0, "history": [], "signature": None, "critique": None}

    def reproduce(self, state):
        script, reproduced, attempts = write_reproduction(self.issue, state["candidate_files"], self.runner, self.model_name)
        self.script = script if reproduced else None
        self.reproduction_attempts = attempts
        logger.info(f"Issue reproduced: {reproduced} ({len(attempts)} attempts)")
        return {"reproduced": reproduced}

    def plan(self, state):
        feedback = state.get("critique") if state.get("round", 0) > 0 else None
        try:
            self.team.plan(state["candidate_files"], feedback=feedback)
        except Exception:
            logger.error(f"Planning failed:\n{traceback.format_exc()}")
        return {"fresh_team": True}

    def develop(self, state):
        try:
            if self.team.manager is None:
                pass # planning failed; verify sees an empty patch
            elif state.get("fresh_team"):
                self.team.develop()
            else:
                self.team.develop_with_feedback(state["critique"], state.get("target_files", []))
        except Exception:
            logger.error(f"Development failed:\n{traceback.format_exc()}")
        return {"fresh_team": False}

    def verify(self, state):
        patch = self.team.patch()
        round_index = state.get("round", 0)
        history = list(state.get("history", []))
        update = {"patch": patch, "round": round_index + 1}
        if self.script is None:
            # no reproduction test: nothing to verify against, keep MAGIS's result (Config A behavior)
            history.append({"round": round_index, "route": router.END, "reason": "no reproduction test",
                            "patch_lines": len(patch.splitlines())})
            update.update({"route": router.END, "reason": "no reproduction test", "resolved": None, "history": history,
                           "last_applied_patch": patch})
            return update
        run = self.runner.run(patch, self.script)
        verdict = router.decide(run, patch, state["candidate_files"], state.get("signature"), round_index, self.max_feedback_rounds)
        if patch.strip():
            verdict.critique += f"\n\n## The current change (all files)\n```diff\n{router.truncate(patch, 4000)}\n```"
        logger.info(f"Round {round_index}: {verdict.route} ({verdict.reason})")
        history.append({"round": round_index, "route": verdict.route, "reason": verdict.reason,
                        "signature": verdict.signature, "apply_ok": run.apply_ok, "timed_out": run.timed_out,
                        "patch_lines": len(patch.splitlines())})
        update.update({"route": verdict.route, "reason": verdict.reason, "resolved": verdict.resolved,
                       "critique": verdict.critique, "signature": verdict.signature,
                       "target_files": verdict.target_files, "new_files": verdict.new_files, "history": history})
        if run.apply_ok and patch.strip():
            update["last_applied_patch"] = patch
        return update

    def relocalize(self, state):
        files = list(state["candidate_files"]) + [f for f in state.get("new_files", []) if f not in state["candidate_files"]]
        logger.info(f"Relocalize: candidate files now {files}")
        return {"candidate_files": files}

    # edges
    def next_step(self, state):
        route = state["route"]
        if route == router.DEVELOP and self.team.manager is None:
            return router.PLAN # no team to send the feedback to: plan again
        return route

    def build(self):
        graph = StateGraph(RepairState)
        for name in ["localize", "reproduce", "plan", "develop", "verify", "relocalize"]:
            graph.add_node(name, getattr(self, name))
        graph.add_edge(START, "localize")
        graph.add_edge("localize", "reproduce")
        graph.add_edge("reproduce", "plan")
        graph.add_edge("plan", "develop")
        graph.add_edge("develop", "verify")
        graph.add_conditional_edges("verify", self.next_step, {router.END: END, router.DEVELOP: "develop",
                                                               router.PLAN: "plan", router.RELOCALIZE: "relocalize"})
        graph.add_edge("relocalize", "plan")
        return graph.compile()

    def run(self):
        final_state = self.build().invoke({}, config={"recursion_limit": 100})
        final_patch = final_state.get("patch", "")
        if not final_state.get("resolved"):
            # prefer a patch that at least applies
            final_patch = final_state.get("last_applied_patch") or final_patch
        return final_patch, final_state
