#!/usr/bin/env python3
"""Negative controls for scripts/check-runs-on-labels.py, executed in CI. Each case writes ONE workflow into a scratch repo, runs the real
checker as a subprocess and asserts its exit status: the valid selector passes, every bypass or malformed form fails.
Run from the repo root: python3 scripts/test_check_runs_on_labels.py"""
import os, subprocess, sys, tempfile, textwrap, unittest
CHECKER = os.path.abspath(os.path.join(os.path.dirname(__file__), "check-runs-on-labels.py"))
GOOD = "${{ vars.CI_RUNNER_BACKEND == 'runs-on' && format('runs-on={0}-{1}-JOB-{2}/runner=2cpu-linux-x64', github.run_id, github.run_attempt, strategy.job-index) || 'ubuntu-latest' }}"
def run_checker(jobs):
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".github", "workflows"))
        body = "name: t\non: push\njobs:\n" + "".join(f"  {k}:\n    runs-on: {v}\n    steps:\n      - run: true\n" for k, v in jobs.items())
        open(os.path.join(d, ".github", "workflows", "w.yml"), "w").write(body)
        r = subprocess.run([sys.executable, CHECKER], cwd=d, capture_output=True, text=True)
        # the summary line proves the checker ran to its verdict; a crash or traceback must never count as a failing control
        assert "check-runs-on-labels:" in r.stdout and "Traceback" not in r.stderr, (r.stdout, r.stderr)
        return r.returncode
def q(s): return '"' + s.replace('"', '\\"') + '"'
class Labels(unittest.TestCase):
    def test_valid_selector_passes(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a")), "b": q(GOOD.replace("JOB", "b"))}), 0)
    def test_s3_cache_extra_is_allowed(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a").replace("cpu-linux-x64'", "cpu-linux-x64/extras=s3-cache'"))}), 0)
    def test_unknown_extra_is_rejected(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a").replace("cpu-linux-x64'", "cpu-linux-x64/extras=other'"))}), 1)
    def test_plain_hosted_job_is_ignored(self): self.assertEqual(run_checker({"a": "ubuntu-latest"}), 0)
    def test_missing_index_placeholder(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a").replace("-{2}/", "/"))}), 1)
    def test_index_argument_dropped(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a").replace(", strategy.job-index", ""))}), 1)
    def test_wrong_binding(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a").replace("github.run_id, github.run_attempt, strategy.job-index", "strategy.job-index, github.run_attempt, github.run_id"))}), 1)
    def test_duplicate_job_key(self): self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "x")), "b": q(GOOD.replace("JOB", "x"))}), 1)
    def test_shared_label_bypass_after_a_valid_format_call(self):
        bad = GOOD.replace("JOB", "a").replace("format(", "(format(").replace(") || 'ubuntu-latest'", ") && 'runs-on=shared/runner=2cpu-linux-x64') || 'ubuntu-latest'")
        self.assertEqual(run_checker({"a": q(bad)}), 1)
    def test_extra_text_around_a_valid_expression(self):
        # a valid-looking expression with a second runs-on= label appended: GitHub treats the whole string as the label set
        self.assertEqual(run_checker({"a": q(GOOD.replace("JOB", "a") + " runs-on=shared/runner=2cpu-linux-x64")}), 1)
        self.assertEqual(run_checker({"a": q("runs-on=shared " + GOOD.replace("JOB", "a"))}), 1)
    def test_list_form_rejected(self): self.assertEqual(run_checker({"a": '[self-hosted, "runs-on=x"]'}), 1)
    def test_mapping_form_rejected(self): self.assertEqual(run_checker({"a": '{group: g, labels: ["runs-on=x"]}'}), 1)
if __name__ == "__main__":
    unittest.main()
