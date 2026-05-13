# AI Memory Benchmark Results

This directory is the citable result namespace for external AI memory benchmark
artifacts. Files here should be full result records, not headline summaries.

Current committed artifacts:

- `longmemeval_sibyl_raw_20260513.json`
- `longmemeval_sibyl_hybrid_20260513.json`

Each citable artifact must include overall metrics, per-slice metrics, full
per-case records, dataset provenance, command, commit, runtime mode, and
caveats. Gate new artifacts before citing them:

```bash
moon run bench-gate -- benchmarks/results/ai-memory/<artifact>.json --profile ai-memory
```

Suites without full artifacts in this directory or in a named external archive
manifest are planned coverage only.
