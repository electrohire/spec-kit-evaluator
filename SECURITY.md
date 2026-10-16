# Security policy

## Supported versions

Security fixes are provided for the latest 1.x release.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/electrohire/spec-kit-evaluator/security/advisories/new).
Do not publish suspected vulnerabilities, credentials, personal data, or private
evaluation artifacts in public issues. Include affected versions, impact,
reproduction steps, and any known mitigation.

ElectroHire will acknowledge reports within three business days, provide a
status update within seven business days, and coordinate disclosure after a fix
is available. Confirmed exploitable vulnerabilities of medium or higher severity
must be fixed promptly and within 60 days of public disclosure; critical issues
receive immediate priority. Release notes identify publicly known fixed CVEs.

## Trust boundaries

Evaluator results are untrusted input. Composition validates the result schema
and fails closed on invalid inputs. A composed pass is a policy decision, not a
truth, safety, compliance, or correctness certificate. The composers do not
execute instructions in result text or implement cryptographic protocols.
Do not commit credentials or confidential assessment data. Secret scanning and
push protection supplement maintainer review; neither proves secrets are absent.
