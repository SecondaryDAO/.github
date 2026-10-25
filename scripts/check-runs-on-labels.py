#!/usr/bin/env python3
"""Fail if a workflow job that opts into RunsOn could share a routing label with a concurrent execution.

A RunsOn job must declare its runner as exactly this whole expression (full match, no other operands or alternatives):
    ${{ vars.CI_RUNNER_BACKEND == 'runs-on' && format('runs-on={0}-{1}-<job-key>-{2}/runner=<N>cpu-linux-x64[/extras=s3-cache]', github.run_id, github.run_attempt, strategy.job-index) || 'ubuntu-latest' }}
so (1) every placeholder {0},{1},{2} is present and bound to run id, run attempt and matrix-leg index in that order, nothing can
substitute a different label, and (2) two jobs of one file never share a <job-key> (compared case-insensitively, as GitHub compares labels). Anything else is REJECTED, not skipped: only that expression or a plain hosted label
(ubuntu-latest, ubuntu-24.04, ubuntu-22.04) is accepted; markerless RunsOn forms such as `runs-on/runner=2cpu-linux-x64`, lists,
mappings and any other label cannot be verified here. Run from the repo root.
Fails closed: unreadable YAML, a missing PyYAML, or no workflow files is an error, never a pass."""
import glob, json, re, sys
try:
    import yaml
except ImportError:
    sys.exit("check-runs-on-labels: PyYAML is not installed; cannot verify labels")
FORM = re.compile(r"\$\{\{ vars\.CI_RUNNER_BACKEND == 'runs-on' && format\('runs-on=\{0\}-\{1\}-([A-Za-z0-9_.-]+)-\{2\}/runner=[0-9]+cpu-linux-x64(?:/extras=s3-cache)?', github\.run_id, github\.run_attempt, strategy\.job-index\) \|\| 'ubuntu-latest' \}\}")
HOSTED = {"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04"}   # plain GitHub-hosted labels; any other runner kind needs a deliberate edit here
bad = []; checked = 0
files = sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
if not files:
    sys.exit("check-runs-on-labels: no workflow files found; run from the repo root")
for f in files:
    jobs = (yaml.safe_load(open(f)) or {}).get("jobs") or {}
    seen = {}
    for key, job in jobs.items():
        ro = (job or {}).get("runs-on")
        if ro is None:
            continue   # a job that calls a reusable workflow (uses:) has no runs-on of its own
        checked += 1
        if isinstance(ro, str) and ro.strip() in HOSTED:
            continue   # plain GitHub-hosted label: not RunsOn, nothing to route
        # Everything else must be THE supported selector. This is an allowlist, not a search for 'runs-on=': the scalar form
        # `runs-on/runner=2cpu-linux-x64`, lists, mappings, other labels and text around the expression are all rejected.
        if not isinstance(ro, str):
            bad.append(f"{f}:{key}: runs-on is a {type(ro).__name__}; only the supported selector expression or a plain hosted label is verifiable")
            continue
        m = FORM.fullmatch(ro.strip())
        if not m:
            bad.append(f"{f}:{key}: runs-on is neither the supported selector expression nor a plain hosted label (see scripts/check-runs-on-labels.py docstring)")
            continue
        label_key = m.group(1).lower()   # GitHub compares labels case-insensitively
        if label_key in seen:
            bad.append(f"{f}:{key}: RunsOn label key {label_key!r} (case-insensitive) already used by job {seen[label_key]!r}")
        else:
            seen[label_key] = key
print(f"check-runs-on-labels: {checked} RunsOn job(s) checked, {len(bad)} problem(s)")
for b in bad: print("  " + b)
sys.exit(1 if bad else 0)
