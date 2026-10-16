# Contributing

Use issues and pull requests. Add or update tests for changed composition or
evaluator behavior, keep the Python, Bash, and PowerShell composers at parity
(`tests/test_compose_parity.py`), and disclose AI assistance in commits
(`Assisted-by:` trailer) and pull requests.

## Reproduce CI

See [development setup](DEVELOPMENT.md) for this repository's own Spec Kit/AEE
installation and the shared component/dependency names. Runtime requirements
for a standalone composer differ from the AEE adapter's managed runtime.

CI runs on Ubuntu, Windows, and macOS with Python 3.11, 3.12, and 3.13, the
same targets as applied-epistemic-engineering and spec-kit-aee. Code must parse
on Python 3.11 (for example, no same-quote nesting inside f-strings).

```bash
python -m pip install -r requirements.txt pyyaml
python -m unittest discover -s tests -v
python -m pip install ruff==0.17.0
python -m ruff check scripts tests
```

The Bash composer legs need `bash` and `jq` (not run on Windows); the
PowerShell legs need `pwsh`. CI fails when a required tool is missing instead
of skipping the leg.

The suite includes reproducible malformed-input fuzzing across all composition
strategies. It checks fail-closed outcomes, output schema validity, and input
immutability. Run the full suite, lint, and CodeQL before major releases; retain
minimized regression cases for any discovered issue. Confirmed exploitable
static/dynamic-analysis findings must be fixed according to [SECURITY.md](SECURITY.md).

## Release and catalog submission checklist

Follow Spec Kit's current
[Extension Publishing Guide](https://github.com/github/spec-kit/blob/main/extensions/EXTENSION-PUBLISHING-GUIDE.md)
and [CONTRIBUTING](https://github.com/github/spec-kit/blob/main/CONTRIBUTING.md).
Not following them means a new submission issue has to be filed.

1. On a branch and PR: set `extension.version` in `extension.yml`, date the
   `CHANGELOG.md` entry, and update the README install URL to the new tag.
   Merge only with every CI target green.
2. Tag the merge commit `vX.Y.Z` (matching `extension.yml` exactly) and
   **publish** the GitHub release (not a draft; #4516 failed on a draft
   release). Never move or reuse a published tag; fix forward with a new
   version.
3. Test the exact public archive in a disposable project:
   `specify extension add evaluator --from https://github.com/electrohire/spec-kit-evaluator/archive/refs/tags/vX.Y.Z.zip`,
   then run the commands. Record the archive SHA-256.
4. File a **new**
   [Extension Submission](https://github.com/github/spec-kit/issues/new?template=extension_submission.yml)
   issue stating that it updates the existing `evaluator` entry. Use the
   current form unchanged and fill in every section, including Testing Checklist,
   Submission Requirements, and Proposed Catalog Entry (#4403 failed on missing
   sections). Version, download URL, and Proposed Catalog Entry must name the
   same version (#4447 failed on a mismatch). Commands and hooks counts must
   match `extension.yml` (currently 4 commands, 4 hook events). Name the AI
   tool used in the issue.
5. Do not open a pull request against `extensions/catalog.community.json`. A
   maintainer applies the `extension-submission` label during triage (you
   cannot), which runs validation and opens the draft catalog PR. If
   validation fails only because its runner could not fetch the archive,
   say so on the issue rather than refiling.

Prior cases: original submission
[#4414](https://github.com/github/spec-kit/issues/4414) (catalog PR
[#4420](https://github.com/github/spec-kit/pull/4420)), after
[#4403](https://github.com/github/spec-kit/issues/4403) failed validation.
The evaluator 1.1.1 catalog update was submitted through
[#4979](https://github.com/github/spec-kit/issues/4979) and merged in
[#4980](https://github.com/github/spec-kit/pull/4980). The 1.1.0 release was never submitted.

By contributing, you agree to the MIT license.
