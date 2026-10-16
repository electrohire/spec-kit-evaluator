# Development setup and dependency map

This repository uses Spec Kit **1.2.0**, the latest published CLI at this audit,
with AEE extension **1.5.1** and evaluator extension **1.1.1** installed into its
own `.specify/` tree. The compatible published engine tested is **1.5.2**.
These are installed releases, not unreleased copies of this repository's code.

| Component | Distribution / access | Dependency boundary |
| --- | --- | --- |
| Spec Kit | PyPI `specify-cli`; CLI `specify` | Scaffolds project templates and installs extensions |
| Python engine | PyPI `applied-epistemic-engineering`; import/CLI `aee` | Usable standalone; no required runtime dependencies, Spec Kit, or evaluator extension |
| AEE adapter | GitHub `electrohire/spec-kit-aee`; extension ID `aee` | Requires Python >=3.11, Spec Kit >=1.0.0,<2, engine >=1.5.0,<2 and evaluator >=1.0.0,<2; provisions engine, `jsonschema>=4.0`, and pinned evaluator 1.1.1 on first use |
| Evaluator | GitHub `electrohire/spec-kit-evaluator`; extension ID `evaluator` | Shared schema/composition, not an engine; standalone Python composer needs `jsonschema>=4.0`, Bash composer needs `jq`, PowerShell composer has no extra package dependency |

`rtk`, `headroom`, `token-router`, and `ollama` are optional routing/token-economy
tools. They are not required to install or run deterministic AEE operations.
The engine's `[dev]` and `[docs]` extras are development dependencies, not extra
requirements for the standalone engine. Neither extension is a pip package.

## Refresh the project's tools

Install `specify-cli==1.2.0` in a dedicated Python environment and put its scripts
directory on PATH. From this repository's root:

```bash
specify init --here --force --non-interactive --integration copilot --script sh --ignore-agent-tools
specify extension add aee
specify extension list
```

Review local template changes before refreshing; `--force` can overwrite
generated files. Existing project constitution content is retained by Spec Kit.

## Troubleshooting older installations

Earlier tested installations (Spec Kit 1.2.0 with AEE 1.5.1) used a discovery-only
default community catalog. If one of those installations refuses installation by
ID, use the known release archives below or follow the installer version's own
catalog guidance. Do not change catalog trust silently. This is a fallback for
older setups, not the primary installation workflow for the upcoming update.

```bash
specify extension add aee --from https://github.com/electrohire/spec-kit-aee/archive/refs/tags/v1.5.1.zip --force
specify extension add evaluator --from https://github.com/electrohire/spec-kit-evaluator/archive/refs/tags/v1.1.1.zip --force
```

Review and accept the CLI's source-trust prompt for these project-owned archives.
The explicit evaluator install refreshes an existing companion; a first AEE
`assess` installs it automatically if missing. AEE reuses an in-range engine,
so installation alone does not upgrade every existing Python environment. To
refresh a previously provisioned private runtime to the current compatible engine:

```bash
# macOS/Linux; on Windows use .runtime/venv/Scripts/python.exe below instead
.specify/extensions/aee/.runtime/venv/bin/python -m pip install --upgrade 'applied-epistemic-engineering>=1.5.0,<2' 'jsonschema>=4.0'
```

Do not commit `.runtime`, local assessments, ledgers, caches, or credentials.
Committed framework and generated skills are development tooling. The extension
repositories ignore their installed extension copies to avoid nesting their own
release archives; restore them using the setup commands above. Root
commands, scripts, and manifests remain the extension's product source. Do not
edit installed copies to implement product changes. Test product source using a
disposable project's `specify extension add --dev <source-path>` installation.

## Verification limits and documentation publishing

See the engine's [names and assurance boundaries](https://applied-epistemic-engineering.readthedocs.io/en/latest/names-and-assurance/).
Schema validity, a valid ledger, composed `pass`, and human acceptance establish
different things; none is an unrestricted truth certificate.

GitHub `main` and RTD `latest` can contain unreleased corrections. PyPI's README
is embedded in the uploaded engine distribution; RTD `stable` follows the last
release tag. Documentation-only changes are queued under Unreleased, without
moving tags or publishing a package solely to refresh those surfaces.

## Agent skills

The engine's [three-interface guide](https://applied-epistemic-engineering.readthedocs.io/en/latest/agent/)
explains standalone Python/CLI use, the direct agent skill, and Spec Kit operation
skills. Users can ask the agent in ordinary language; the agent handles command
syntax and reports the actual checks and unresolved evidence. Source onboarding
skills added under Unreleased do not silently appear in already published packages.
