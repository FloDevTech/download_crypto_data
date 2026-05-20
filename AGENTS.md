# AGENTS.md — Essential guidance for OpenCode agents

## Before starting work
- Run `./init.sh` and verify exit code 0 (checks Python version, files, specs, tests)
- Work on only one feature at a time (see `feature_list.json` `in_progress` count)

## Core workflow (Spec Driven Development)
For features with `"sdd": true` in `feature_list.json`:
1. Implementer creates spec files in `specs/<name>/` (requirements.md, design.md, tasks.md)
2. **Pause for human approval** (leader stops flow at `spec_ready`)
3. After approval, implement tasks in `tasks.md`
4. Verify with `./init.sh` before marking `done`

## Project-specific commands
- Download data: `python -m src.binance_fetcher`
- Validate data: `python -m src.validator`
- Run tests: `python3 -m unittest discover -s tests -v` (also run by `init.sh`)
- Edit configuration: `config.yaml` in project root (symbols, date range)

## Data storage
- OHLCV data saved to `data/<symbol>/year=<YYYY>/month=<MM>/day=<DD>/data.parquet`
- Symbol format in paths: Use hyphens (e.g., `BTC-USDT` for `BTC/USDT`)
- Partitioned by year/month/day for efficient querying

## Key constraints
- No more than one feature in `in_progress` at a time
- No declaring tasks `done` without passing tests (verified via `./init.sh`)
- No skipping spec approval for `"sdd": true` features
- Keep `progress/current.md` updated with session activity
- Leave repository clean: no debug `print()`, temporary files, or unresolved TODOs

## When stuck
- Re-read relevant docs in `docs/` before inventing solutions
- If tools behave unexpectedly, document the issue in `progress/current.md` and pause session