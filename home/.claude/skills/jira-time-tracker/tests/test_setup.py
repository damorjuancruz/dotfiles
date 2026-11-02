import unittest

import setup


class TestSetup(unittest.TestCase):
    def test_propose_config_uses_only_own_email(self):
        local = {"timezone": "America/Argentina/Buenos_Aires", "git_emails": ["yo@empresa.com"],
                 "recent_commit_emails": [["companero@x.com", 50], ["yo@empresa.com", 10]],
                 "github_user": "yo", "github_orgs": ["org"], "git_roots": ["~/code"]}
        cfg = setup.propose_config(local, {"account_id": "acc"}, ["SUP"], "yo@empresa.com", "https://x.atlassian.net")
        self.assertEqual(cfg["identity"]["git_emails"], ["yo@empresa.com"])
        self.assertEqual(cfg["jira"]["account_id"], "acc")
        self.assertEqual(cfg["projects"]["SUP"]["excluded_status_categories"], ["Done"])
        self.assertTrue(cfg["sources"]["chrome"]["deny_domains"])

    def test_check_runs(self):
        rows = setup.check()
        self.assertTrue(any(name == "python" for _, name, _ in rows))


if __name__ == "__main__":
    unittest.main()
