# Data model

ScopeSnapshot1.0:repository_id, canonical explicit relativefile→SHA256 mapping, canonical tree_hash. Reject traversal/symlinks/nonregular/oversized files/duplicates. Freshness:fresh/stale/unknown plus changed/missing/unreadable paths.

ExecutionEvidence1.0:argv, scope_before/after, actual exit/timeout/start/end/duration, code revision metadata, bounded stdout/stderr and report hashes, requirement/test IDs, completeness and producer class. Observed local execution differs from externally verified CI. A pass requires applicable scope, complete actual verification, successful exit and allowed producer policy; an agent assertion is never sufficient.

VerificationLinks:accepted requirement IDs, discovered realtest IDs/files, many-to-many links or explicitly scoped human-approved non-test method. Distinguish broken requirement, missing test, orphan scoped test, incomplete discovery and invalid approval.

Preflight:explicit task/requirement scope, linked verification, assumptions, ambiguity and destructive authorization. Decisions proceed/clarify/block with stable reason IDs. No OS sandbox claim.

ContextHandoff:stable claims with unchanged status/stage/kind, assumptions/unknowns/contradictions, freshness/provenance pointers, ledger anchor, explicit omissions. Fail rather than silently truncate blockers.

Evaluator:existing1.0 result compatibility plus explicit new sub-contract/phase version. Rich engine state stays opaque namespaced; composer cannot rescore claims or silently promote unknown evidence.
