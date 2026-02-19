# Project Guidelines

Read `ARCHITECTURE.md` for the full module map — classes, method signatures, dependencies, and data flow.
Only read code files when info needed is not contained in `ARCHITECTURE,md`.

## Commands
- Build: `python3 -m build`
- Test all: `python3 -m pytest kalshi_trading/tests/`
- Test single: `python3 -m pytest kalshi_trading/tests/test_<module>.py -v`
- Lint: `python3 -m flake8 kalshi_trading/`
- Type check: `python3 -m mypy kalshi_trading/`

## Code Style
- Python 3.9+ — use type hints on all public function signatures
- Use f-strings over .format() or % formatting
- Imports: stdlib first, third-party second, local third — separated by blank lines
- Use pathlib over os.path for filesystem operations
- Prefer dataclasses or NamedTuples over raw dicts for structured data

## Architecture
- All monetary values in cents internally; format to dollars only at display time
- Dependency injection: classes accept optional dependencies, create defaults internally
- Custom exceptions inherit from a base project error — never raise bare Exception
- Pagination: loop with cursor, safety break on empty results + MAX_PAGES limit

## Error Handling
- Validate at system boundaries (user input, API responses) — trust internal code
- Log errors with context (relevant IDs, input values) before re-raising
- Never silently swallow exceptions — always log or re-raise

## Testing
- Run relevant tests after every code change — do not skip verification
- Use unittest.mock — avoid hitting real APIs in tests
- Each test should be independent — no shared mutable state between tests
- Name tests descriptively: `test_<function>_<scenario>_<expected_result>`

## Git
- Commit messages: imperative mood, under 72 chars, explain "why" not "what"
- Do not commit secrets, .env files, or credentials
- Do not push to main/master without explicit approval

## Security
- Never hardcode secrets — use environment variables or config files excluded from git
- Sanitize all external input before use
- Pin dependency versions in requirements files

## Workflow
- Read existing code before modifying it — understand context first
- Prefer editing existing files over creating new ones
- Keep changes minimal and focused — do not refactor unrelated code
- When fixing a bug, write a failing test first, then fix
- After implementation, run tests and type checks to verify
- If you see issues, leave TODO notes for later (and write a message that you did)
