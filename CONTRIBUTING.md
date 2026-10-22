# Contributing to IntegrityWatch

Thanks for your interest! Bug reports, ideas and pull requests are welcome.

## Set up
```bash
git clone https://github.com/kd3army/IntegrityWatch.git
cd IntegrityWatch
python3 -m venv .venv && source .venv/bin/activate
pip install -e . pytest
python3 -m pytest
```

## Making a change
1. Open an issue first for anything bigger than a small fix.
2. Create a branch: `git checkout -b my-change`.
3. Keep the change focused and add or update tests.
4. Run `python3 -m pytest` and make sure everything passes.
5. Update the README or CHANGELOG if behaviour changes.
6. Open a pull request and describe what and why.

## Guidelines
- Standard library only. New dependencies need a strong reason.
- Keep exit codes stable: 0 = no changes, 1 = changes, 2 = error.
- Comment the "why", not the "what".
