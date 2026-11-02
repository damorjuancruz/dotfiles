import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors import git_local, github
from lib import common

CFG = common.load_config(Path(__file__).resolve().parent.parent / "config.example.json")
TZ = ZoneInfo(CFG["timezone"])
RX = common.issue_key_regex(["SUP", "ENG"])
S = git_local.SEP


class TestGitParsing(unittest.TestCase):
    def test_parse_log(self):
        out = f"abc{S}2026-10-05T09:00:00-03:00{S}2026-10-05T09:01:00-03:00{S}refs/heads/feat/SUP-12{S}fix x\nbasura\n"
        c = git_local.parse_log(out)
        self.assertEqual(len(c), 1)
        self.assertEqual(git_local.clean_ref(c[0]["source"]), "feat/SUP-12")

    def reflog(self, *lines):
        # git reflog lista de la más nueva a la más vieja
        return "\n".join(f"HEAD@{{2026-10-05T{t}:00-03:00}}{S}{subj}" for t, subj in reversed(lines))

    def test_parse_reflog_ops(self):
        e = git_local.parse_reflog(self.reflog(("09:00", "commit: a"), ("09:05", "commit (amend): a"),
                                               ("09:10", "rebase -i (pick): b"), ("09:11", "Branch: renamed x")))
        self.assertEqual([x["op"] for x in e], ["commit", "amend", "rebase", "branch"])
        self.assertEqual(e[0]["ts"], "2026-10-05T09:00:00-03:00")

    def test_track_branches_through_rebase(self):
        e = git_local.parse_reflog(self.reflog(
            ("09:00", "commit (amend): a"),
            ("09:10", "checkout: moving from main to feat/sup-3"),
            ("09:20", "rebase (start): checkout 1a2b3c4d"),
            ("09:21", "rebase (pick): b"),
            ("09:22", "rebase (finish): returning to refs/heads/feat/sup-3"),
            ("09:30", "checkout: moving from feat/sup-3 to 1a2b3c4d"),
        ))
        git_local.track_branches(e, git_local.initial_branch(e, "otra"))
        self.assertEqual([x["branch"] for x in e],
                         ["main", "feat/sup-3", "feat/sup-3", "feat/sup-3", "feat/sup-3", "(detached)"])

    def test_initial_branch_without_checkout_uses_current(self):
        e = git_local.parse_reflog(self.reflog(("09:00", "commit: a")))
        self.assertEqual(git_local.initial_branch(e, "main"), "main")

    def test_sessions_split_by_branch_and_gap(self):
        e = git_local.parse_reflog(self.reflog(
            ("09:00", "commit (amend): a"),
            ("09:14", "commit (amend): a"),
            ("09:40", "commit (amend): a"),
            ("09:45", "checkout: moving from main to feat/x"),
            ("09:46", "commit: b"),
        ))
        git_local.track_branches(e, "main")
        ses = git_local.sessions(e, 15, TZ)
        self.assertEqual([(x["branch"], x["start"].strftime("%H:%M"), x["end"].strftime("%H:%M"), x["ops"]) for x in ses], [
            ("main", "09:00", "09:14", {"amend": 2}),
            ("main", "09:40", "09:40", {"amend": 1}),
            ("feat/x", "09:45", "09:46", {"checkout": 1, "commit": 1}),
        ])

    def test_discover_and_collect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "proj"
            (root / "proj" / "node_modules" / "dep").mkdir(parents=True)
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            (repo / "node_modules" / "dep" / ".git").mkdir()  # se ignora
            env = {"GIT_AUTHOR_NAME": "Yo", "GIT_AUTHOR_EMAIL": "you@company.com",
                   "GIT_COMMITTER_NAME": "Yo", "GIT_COMMITTER_EMAIL": "you@company.com",
                   "GIT_AUTHOR_DATE": "2026-10-05T10:00:00-03:00", "GIT_COMMITTER_DATE": "2026-10-05T10:00:00-03:00",
                   "PATH": "/usr/bin:/bin", "HOME": tmp}
            subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "feat/SUP-7-algo"], check=True, env=env)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "primer commit"], check=True, env=env)
            env2 = {**env, "GIT_AUTHOR_EMAIL": "otro@x.com", "GIT_COMMITTER_EMAIL": "otro@x.com"}
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "ajeno"], check=True, env=env2)

            self.assertEqual(git_local.discover_repos([tmp], 5), [repo])
            cfg = {**CFG, "sources": {**CFG["sources"], "git_local": {**CFG["sources"]["git_local"], "roots": [tmp]}}}
            res = git_local.collect(cfg, {}, date(2026, 10, 5))
            commits = [e for e in res["events"] if e["title"].startswith("commit")]
            self.assertEqual(len(commits), 1)
            self.assertIn("primer commit", commits[0]["title"])
            self.assertEqual(commits[0]["hints"]["issue_keys"], ["SUP-7"])
            self.assertEqual(commits[0]["start"], "2026-10-05T10:00:00-03:00")
            activity = [e for e in res["events"] if e["title"].startswith("actividad git")]
            self.assertEqual(len(activity), 1)
            self.assertEqual(activity[0]["hints"]["branch"], "feat/SUP-7-algo")
            self.assertEqual(activity[0]["hints"]["issue_keys"], ["SUP-7"])

    def test_rewritten_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "proj"
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            base = {"GIT_AUTHOR_NAME": "Yo", "GIT_AUTHOR_EMAIL": "you@company.com", "GIT_COMMITTER_NAME": "Yo",
                    "GIT_COMMITTER_EMAIL": "you@company.com", "PATH": "/usr/bin:/bin", "HOME": tmp}
            old = {**base, "GIT_AUTHOR_DATE": "2026-10-01T10:00:00-03:00", "GIT_COMMITTER_DATE": "2026-10-01T10:00:00-03:00"}
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "viejo"], check=True, env=old)
            amend = {**base, "GIT_COMMITTER_DATE": "2026-10-05T11:00:00-03:00"}
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--amend", "--allow-empty", "--no-edit"], check=True, env=amend)
            cfg = {**CFG, "sources": {**CFG["sources"], "git_local": {**CFG["sources"]["git_local"], "roots": [tmp]}}}
            res = git_local.collect(cfg, {}, date(2026, 10, 5))
            ev = [e for e in res["events"] if "viejo" in e["title"]]
            self.assertEqual(len(ev), 1)
            self.assertTrue(ev[0]["title"].startswith("reescrito (amend/rebase)"))
            self.assertEqual(ev[0]["weight"], "normal")


def gh_event(t, created, payload, repo="org/app", id_="1"):
    return {"id": id_, "type": t, "created_at": created, "repo": {"name": repo}, "payload": payload}


class TestGithub(unittest.TestCase):
    def setUp(self):
        self.titles = {("org/app", 5): {"title": "SUP-9 importador", "branch": "feat/x", "url": "u", "author": "otro"}}

    def api(self, path):
        if path.startswith("/users/"):
            return [
                gh_event("PullRequestReviewEvent", "2026-10-05T14:00:00Z",
                         {"action": "created", "pull_request": {"number": 5}, "review": {"state": "APPROVED", "body": "LGTM"}}, id_="a"),
                gh_event("PushEvent", "2026-10-05T13:00:00Z", {"ref": "refs/heads/feat/eng-4"}, id_="b"),
                gh_event("CreateEvent", "2026-10-05T12:00:00Z", {"ref_type": "tag", "ref": "v1"}, id_="c"),
                gh_event("WatchEvent", "2026-10-05T12:00:00Z", {}, id_="d"),
                gh_event("PushEvent", "2026-10-04T13:00:00Z", {"ref": "refs/heads/main"}, id_="e"),
                gh_event("PushEvent", "2026-10-05T15:00:00Z", {"ref": "refs/heads/main"}, repo="me/dotfiles", id_="f"),
            ]
        if path == "/repos/org/app/pulls/5":
            return {"title": "SUP-9 importador", "head": {"ref": "feat/x"}, "html_url": "u", "user": {"login": "otro"}}
        raise AssertionError(path)

    def cfg(self, orgs=("org",), only_orgs=True):
        return CFG | {"identity": {**CFG["identity"], "github_user": "me", "github_orgs": list(orgs)},
                      "sources": {**CFG["sources"], "github": {"enabled": True, "only_orgs": only_orgs}}}

    def test_personal_repos_filtered(self):
        res = github.collect(self.cfg(), {}, date(2026, 10, 5), api=self.api)
        self.assertNotIn("me/dotfiles", [e["hints"]["repo"] for e in res["events"]])
        self.assertIn("ignorados: me/dotfiles", res["messages"][0])

    def test_toggle_off_keeps_personal(self):
        res = github.collect(self.cfg(only_orgs=False), {}, date(2026, 10, 5), api=self.api)
        self.assertIn("me/dotfiles", [e["hints"]["repo"] for e in res["events"]])

    def test_no_orgs_configured(self):
        res = github.collect(self.cfg(orgs=()), {}, date(2026, 10, 5), api=self.api)
        self.assertEqual(len(res["events"]), 3)
        self.assertIn("github_orgs está vacío", res["messages"][0])

    def test_collect(self):
        res = github.collect(self.cfg(), {}, date(2026, 10, 5), api=self.api)
        self.assertEqual(res["status"], "ok")
        ev = res["events"]
        self.assertEqual(len(ev), 2)
        push, review = ev
        self.assertEqual(push["hints"]["issue_keys"], ["ENG-4"])
        self.assertEqual(push["weight"], "weak")
        self.assertEqual(review["title"], "review (approved) de PR #5 SUP-9 importador en org/app")
        self.assertEqual(review["hints"]["pr_author"], "otro")
        self.assertEqual(review["hints"]["issue_keys"], ["SUP-9"])
        self.assertEqual(review["start"], "2026-10-05T11:00:00-03:00")

    def test_api_error(self):
        def boom(path):
            raise RuntimeError("gh: not logged in")
        res = github.collect(CFG | {"identity": {**CFG["identity"], "github_user": "me"}}, {}, date(2026, 10, 5), api=boom)
        self.assertEqual(res["status"], "error")


if __name__ == "__main__":
    unittest.main()
