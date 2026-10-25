#!/usr/bin/env python3
"""Fail if a workflow job that opts into RunsOn could share a routing label with a concurrent execution.

A RunsOn job must declare its runner as exactly this whole expression (full match, no other operands or alternatives):
    ${{ vars.CI_RUNNER_BACKEND == 'runs-on' && format('runs-on={0}-{1}-<job-key>-{2}/runner=<N>cpu-linux-x64[/extras=s3-cache]', github.run_id, github.run_attempt, strategy.job-index) || 'ubuntu-latest' }}
so (1) every placeholder {0},{1},{2} is present and bound to run id, run attempt and matrix-leg index in that order, nothing can
substitute a different label, and (2) two jobs of one file never share a <job-key>. Any other representation that mentions 'runs-on=' (a list, a mapping,
a different string) is REJECTED, not skipped: this check cannot verify it. Run from the repo root.
Fails closed: unreadable YAML, a missing PyYAML, or no workflow files is an error, never a pass."""
import glob, json, re, sys
try:
    import yaml
except ImportError:
    sys.exit("check-runs-on-labels: PyYAML is not installed; cannot verify labels")
FORM = re.compile(r"\$\{\{ vars\.CI_RUNNER_BACKEND == 'runs-on' && format\('runs-on=\{0\}-\{1\}-([A-Za-z0-9_.-]+)-\{2\}/runner=[0-9]+cpu-linux-x64(?:/extras=s3-cache)?', github\.run_id, github\.run_attempt, strategy\.job-index\) \|\| 'ubuntu-latest' \}\}")
bad = []; checked = 0
files = sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
if not files:
    sys.exit("check-runs-on-labels: no workflow files found; run from the repo root")
for f in files:
    jobs = (yaml.safe_load(open(f)) or {}).get("jobs") or {}
    seen = {}
    for key, job in jobs.items():
        ro = (job or {}).get("runs-on")
        if "runs-on=" not in json.dumps(ro):
            continue
        checked += 1
        if not isinstance(ro, str):
            bad.append(f"{f}:{key}: runs-on is a {type(ro).__name__}, not a string; this check cannot verify a RunsOn label inside it")
            continue
        m = FORM.fullmatch(ro.strip())
        if not m:
            bad.append(f"{f}:{key}: RunsOn label is not the supported selector expression (see scripts/check-runs-on-labels.py docstring)")
        elif m.group(1) in seen:
            bad.append(f"{f}:{key}: RunsOn label key {m.group(1)!r} already used by job {seen[m.group(1)]!r}")
        else:
            seen[m.group(1)] = key
print(f"check-runs-on-labels: {checked} RunsOn job(s) checked, {len(bad)} problem(s)")
for b in bad: print("  " + b)
sys.exit(1 if bad else 0)
