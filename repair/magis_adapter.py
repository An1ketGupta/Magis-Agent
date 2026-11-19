"""
The original MAGIS agents (Custodian, Manager, Developers with their LLM review), driven step by step, so
that Config B differs from Config A only in the feedback loop. Mirrors process.main.
"""
import os
import shutil

import config
from custodian import Custodian
from log import log
from manager import Manager
from process import Meeting
from repair.router import normalize

logger = log(__name__).get_log_obj()

# same objective as process.main
KICK_OFF_MEETING_TARGET = ("1. Verify if the combination of instructions received by all team members is sufficient to resolve the Issue."
                           "2. Evaluate whether the tasks assigned to each member can be executed simultaneously."
                           " If concurrent execution is not feasible, determine the sequence in which they should be completed.")


class MagisTeam:
    def __init__(self, repo_path, issue, model_name, version, hints_text=False, bm_top_k=20):
        self.repo_path = os.path.abspath(repo_path)
        self.project_name = os.path.basename(self.repo_path)
        self.issue = issue
        self.model_name = model_name
        self.version = version
        self.hints_text = hints_text
        self.bm_top_k = bm_top_k
        self.manager = None
        self.requirement_file_path = os.path.join(self.repo_path, "issue_description.md")

    def localize(self):
        repo_full_name, issue_number = self.project_name.rsplit('-', 1)
        custodian = Custodian(repo_full_name, issue_number, self.issue, model_name=self.model_name, use_cache=True,
                              repository_directory=self.repo_path, bm_top_k=self.bm_top_k)
        return custodian.get_candidate_file_list()

    def plan(self, candidate_files, feedback=None):
        """Build the team (MAGIS Manager), hold the kick-off meeting, decide the work order.
        `feedback`: report of the failed attempt, appended to the issue for a re-plan."""
        requirement = self.issue
        if feedback:
            requirement += f"\n\n## Feedback from a Previous Attempt to Resolve This Issue\n{feedback}"
        with open(self.requirement_file_path, "w") as f:
            f.write(requirement)
        # patches of an earlier team must not be merged into this team's result
        shutil.rmtree(os.path.join(config.exp_result_save_path, self.project_name), ignore_errors=True)
        self.manager = None
        manager = Manager(self.requirement_file_path, self.repo_path, model_name=self.model_name,
                          candidate_file_path_list=list(candidate_files), granularity="file",
                          prepare_member_folder=False, version=self.version, hints_text=self.hints_text)
        recording_file_path = os.path.join(config.virtual_env_path, str(self.version), self.project_name, "kick_off_meeting.md")
        Meeting(recording_file_path, [manager]+manager.team_member_list, max_round_num=10, target=KICK_OFF_MEETING_TARGET)
        with open(recording_file_path) as f:
            manager.get_member_order(f.read())
        self.manager = manager

    def develop(self):
        # first attempt of a new team: the Manager's work order (as in MAGIS)
        self.manager.implement()

    def develop_with_feedback(self, feedback, target_files):
        # later attempts: the Developers of the files in the failure work again, with the test feedback
        target_files = {normalize(file_path) for file_path in target_files}
        member_list = [member for member in self.manager.team_member_list if normalize(member.file_path) in target_files]
        for member in member_list or self.manager.team_member_list:
            member.work(feedback=feedback)

    def patch(self):
        if self.manager is None:
            return ""
        patch, _ = self.manager.merge_code_change()
        return patch
