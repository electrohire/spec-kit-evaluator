# Compose multiple evaluator results with deterministic precedence.
#
# Usage:
#   .\compose-results.ps1 -ResultsDir <path> -Phase <phase> [-Strategy strict|majority|optimistic] [-Output <path>]
#
# Composition contract (Spec 003 FR-6), at parity with the Python and
# Bash composers on outcomes and exit codes:
#   * Empty composition fails closed: outcome "block", exit 2, with an
#     explicit no-results finding — never "pass".
#   * Every input is validated against the same minimum contract
#     (required keys incl. phase, outcome/finding enums, evaluator
#     id+version, payload phase equal to the requested phase).
#     Malformed or invalid files are wrapped as blocking
#     schema_violation findings that vote "block" under every
#     strategy — never skipped toward pass, never a crash.
#   * Dedup/counting use payload evaluator.id+version (greatest
#     filename wins); finding ids are namespaced "<evaluator>:<id>".
#   * Lane pairing (Spec 004 P5): a result carrying the AEE lane pair
#     in metadata.lanes is carried through verbatim per evaluator as
#     metadata.lane_states — never merged, averaged, or scored — and
#     the composed summary states lane-2 lag whenever present,
#     including on a pass. Lane-less inputs compose exactly as before.
#   * majority/optimistic results are marked non-gating in metadata.
#   * Exit codes: 0 pass/warn, 1 iterate/clarify/gather_evidence,
#     2 block or hard error.
#
# Note: the script ends with `exit <code>`; invoke it as a child
# process (pwsh -File ...) when the caller needs to keep running.

param(
    [Parameter(Mandatory=$true)]
    [string]$ResultsDir,

    [Parameter(Mandatory=$true)]
    [string]$Phase,

    [ValidateSet("strict", "majority", "optimistic")]
    [string]$Strategy = "strict",

    [string]$Output
)

$ErrorActionPreference = "Stop"

$script:ValidOutcomes = @("pass", "warn", "iterate", "clarify", "gather_evidence", "block")
$script:ValidSeverities = @("critical", "high", "medium", "low", "info")
$script:ValidKinds = @(
    "unsupported_claim", "contradiction", "missing_evidence",
    "ambiguous_requirement", "unverified_assertion", "provenance_gap",
    "schema_violation", "policy_violation", "security_concern",
    "coverage_gap", "traceability_gap", "risk_unaddressed",
    "assumption_unvalidated", "other"
)
$script:Precedence = @("block", "gather_evidence", "iterate", "clarify", "warn", "pass")
$script:SeverityOrder = @{ critical = 0; high = 1; medium = 2; low = 3; info = 4 }

function Get-GateExitCode([string]$Outcome) {
    switch ($Outcome) {
        "pass" { return 0 }
        "warn" { return 0 }
        "block" { return 2 }
        default { return 1 }
    }
}

function Emit-Composed($Composed) {
    $json = $Composed | ConvertTo-Json -Depth 20
    if ($Output) {
        $parent = Split-Path $Output -Parent
        if ($parent -and -not (Test-Path $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        $json | Set-Content -Path $Output -Encoding UTF8
        Write-Host "Composed result written to $Output"
    } else {
        Write-Output $json
    }
    exit (Get-GateExitCode $Composed.outcome)
}

function New-NoResultsComposed([string]$Detail) {
    $summary = "No evaluator results for phase ${Phase}: composition requires at least one valid evaluator result and fails closed - absence of evidence is not a pass. $Detail"
    if ($summary.Length -gt 500) { $summary = $summary.Substring(0, 500) }
    return [ordered]@{
        schema_version = "1.0"
        evaluator = [ordered]@{ id = "composed"; version = "1.0"; name = "Composed ($Strategy)" }
        phase = $Phase
        outcome = "block"
        summary = $summary
        findings = @(
            [ordered]@{
                id = "composed:NO-RESULTS"
                severity = "critical"
                kind = "missing_evidence"
                subject = $Phase
                description = "No valid evaluator results were available to compose for this phase. A missing/crashed evaluator or a mistyped phase must never read downstream as a green gate."
                evidence_refs = @()
                provenance_refs = @()
                uncertainty = "insufficient_evidence"
                recommended_action = "block"
                rationale = "Fail-closed composition (Spec 003 FR-6.1)."
            }
        )
        next_action = [ordered]@{
            kind = "block"
            target_phase = $null
            message = "No evaluator results found for phase $Phase."
        }
        metadata = [ordered]@{
            timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
            duration_ms = 0
            artifacts_evaluated = @()
            deterministic = $true
            evaluator_count = 0
            contradictory_findings = @()
            composition_strategy = $Strategy
            evaluator_results = @()
            invalid_results = @()
            duplicate_results_ignored = @()
            gating = ($Strategy -eq "strict")
            no_results = $true
        }
        state = [ordered]@{}
    }
}

function Test-ResultContract($Data) {
    # Returns a problem string, or $null when the result satisfies the
    # minimum contract and its payload phase matches the request.
    if ($null -eq $Data -or $Data -isnot [System.Management.Automation.PSCustomObject]) {
        return "result is not a JSON object"
    }
    foreach ($key in @("schema_version", "evaluator", "phase", "outcome", "findings")) {
        if (-not $Data.PSObject.Properties[$key]) {
            return "missing required key '$key'"
        }
    }
    if ($Data.schema_version -isnot [string] -or -not $Data.schema_version) {
        return "missing or invalid schema_version"
    }
    if ($Data.evaluator -isnot [System.Management.Automation.PSCustomObject]) {
        return "missing or invalid evaluator object"
    }
    if ($Data.evaluator.id -isnot [string] -or -not $Data.evaluator.id) {
        return "evaluator.id missing or empty"
    }
    if ($Data.evaluator.version -isnot [string] -or -not $Data.evaluator.version) {
        return "evaluator.version missing or empty"
    }
    if ($Data.phase -isnot [string]) {
        return "missing or invalid phase"
    }
    if ($Data.phase -ne $Phase) {
        return "phase mismatch: payload phase $($Data.phase) != requested phase $Phase"
    }
    if ($script:ValidOutcomes -notcontains $Data.outcome) {
        return "invalid outcome '$($Data.outcome)'"
    }
    if ($Data.findings -isnot [System.Array]) {
        return "findings is not an array"
    }
    for ($i = 0; $i -lt $Data.findings.Count; $i++) {
        $f = $Data.findings[$i]
        if ($f -isnot [System.Management.Automation.PSCustomObject] -or
            $f.id -isnot [string] -or
            ($script:ValidSeverities -notcontains $f.severity) -or
            ($script:ValidKinds -notcontains $f.kind) -or
            $f.subject -isnot [string]) {
            return "finding at index $i violates the minimum contract (id/severity/kind/subject)"
        }
    }
    return $null
}

function Resolve-Outcome([string[]]$Outcomes, [string]$Strat) {
    switch ($Strat) {
        "optimistic" {
            for ($i = $script:Precedence.Count - 1; $i -ge 0; $i--) {
                if ($Outcomes -contains $script:Precedence[$i]) { return $script:Precedence[$i] }
            }
            return "pass"
        }
        "majority" {
            $grouped = $Outcomes | Group-Object | Sort-Object Count -Descending
            $maxCount = $grouped[0].Count
            $tied = @($grouped | Where-Object { $_.Count -eq $maxCount } | ForEach-Object { $_.Name })
            foreach ($c in $script:Precedence) {
                if ($tied -contains $c) { return $c }
            }
            return $grouped[0].Name
        }
        default {
            foreach ($c in $script:Precedence) {
                if ($Outcomes -contains $c) { return $c }
            }
            return "pass"
        }
    }
}

function Get-LaneLagSummary($LaneStates) {
    # Spec 004 P5-V2: one headline sentence naming lane-2 lag, or ""
    # when no carried lane state lags. Signals are read from the
    # carried records (lane_2.bundle, falling back to lane_2 itself
    # when no bundle object is present); counts are reported as the
    # records state them — nothing is scored or combined, and lane 2
    # contains no score to invent. Only integer counts signal (a
    # non-integer value states nothing), matching the Python
    # composer's isinstance(int) checks.
    $parts = @()
    foreach ($state in $LaneStates) {
        $lane2 = $state["lane_2"]
        $bundle = $null
        if ($null -ne $lane2 -and $lane2 -is [System.Management.Automation.PSCustomObject]) {
            if ($lane2.PSObject.Properties["bundle"] -and $lane2.bundle -is [System.Management.Automation.PSCustomObject]) {
                $bundle = $lane2.bundle
            } else {
                $bundle = $lane2
            }
        }
        $signals = @()
        if ($null -ne $bundle) {
            $below = $null
            if ($bundle.PSObject.Properties["below_explained"]) { $below = $bundle.below_explained }
            if (($below -is [int] -or $below -is [long]) -and $below -ne 0) {
                $signals += "$below claim(s) below the explained stage"
            }
            $unexplained = $null
            if ($bundle.PSObject.Properties["verified_unexplained"]) { $unexplained = $bundle.verified_unexplained }
            if (($unexplained -is [int] -or $unexplained -is [long]) -and $unexplained -ne 0) {
                $signals += "$unexplained verified-but-unexplained claim(s)"
            }
        }
        $unknowns = $state["not_understood"]
        $unknownCount = 0
        if ($null -ne $unknowns) {
            $unknownCount = if ($unknowns -is [System.Array]) { $unknowns.Count } else { 1 }
        }
        if ($unknownCount -gt 0) {
            $signals += "$unknownCount residual unknown(s) not understood"
        }
        if ($signals.Count -gt 0) {
            $eid = $state["evaluator_id"]
            $parts += "${eid}: $($signals -join ', ')"
        }
    }
    if ($parts.Count -eq 0) { return "" }
    # The separator is an em dash (U+2014), built from its code point
    # so this file stays ASCII-clean under any script encoding.
    $dash = [string][char]0x2014
    return "Lane 2 (human acceptance) lags lane 1 (machine verification) $dash $($parts -join '; '). A composed outcome is a checking-stage decision, not acceptance or digestion."
}

$timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

if (-not (Test-Path $ResultsDir -PathType Container)) {
    [Console]::Error.WriteLine("Error: no evaluator results found for phase '$Phase' in $ResultsDir (directory missing); composing a fail-closed block result.")
    Emit-Composed (New-NoResultsComposed "Results directory not found: $ResultsDir.")
}

# Collect result files for the phase (exclude previously composed files)
$resultFiles = @(Get-ChildItem -Path $ResultsDir -Filter "*-$Phase-*.json" |
    Where-Object { $_.Name -notlike "composed-*" } |
    Sort-Object Name)

if ($resultFiles.Count -eq 0) {
    [Console]::Error.WriteLine("Error: no evaluator results found for phase '$Phase' in $ResultsDir; composing a fail-closed block result.")
    Emit-Composed (New-NoResultsComposed "The results directory contains no result files for this phase.")
}

# Validate every file; invalid files are wrapped, never skipped.
$validByIdentity = [ordered]@{}
$validFileByIdentity = @{}
$duplicateFiles = @()
$invalid = @()

foreach ($file in $resultFiles) {
    $problem = $null
    $data = $null
    try {
        $data = Get-Content -Path $file.FullName -Raw | ConvertFrom-Json
    } catch {
        $problem = "malformed JSON: $($_.Exception.Message)"
    }
    if ($null -eq $problem) {
        $problem = Test-ResultContract $data
    }
    if ($null -ne $problem) {
        $invalid += @{ file = $file.Name; problem = $problem }
        [Console]::Error.WriteLine("Error: invalid evaluator result '$($file.Name)': $problem")
        continue
    }
    $identity = "$($data.evaluator.id)@$($data.evaluator.version)"
    if ($validByIdentity.Contains($identity)) {
        $duplicateFiles += $validFileByIdentity[$identity]
    }
    # Files are name-sorted; the later (greatest) filename wins.
    $validByIdentity[$identity] = $data
    $validFileByIdentity[$identity] = $file.Name
}

$results = @($validByIdentity.Values)

if ($results.Count -eq 0 -and $invalid.Count -eq 0) {
    Emit-Composed (New-NoResultsComposed "No result files remained after filtering.")
}

# Lane states (Spec 004 P5-V1/V2): an input result may carry the
# AEE lane pair in metadata.lanes (lane 1 machine verification,
# lane 2 human acceptance). Composition carries each pair through
# VERBATIM, per evaluator — the lanes are never merged, averaged,
# or reduced to a single figure (lane 2 contains no score, and
# none is invented here). Lane-less results get no lane_states key.
$laneStates = @()
foreach ($r in $results) {
    if (-not $r.PSObject.Properties["metadata"] -or $null -eq $r.metadata -or
        $r.metadata -isnot [System.Management.Automation.PSCustomObject]) {
        continue
    }
    $metadata = $r.metadata
    if (-not $metadata.PSObject.Properties["lanes"] -or $null -eq $metadata.lanes -or
        $metadata.lanes -isnot [System.Management.Automation.PSCustomObject]) {
        continue
    }
    $lanes = $metadata.lanes
    $lane1 = $null
    if ($lanes.PSObject.Properties["lane_1"]) { $lane1 = $lanes.lane_1 }
    $lane2 = $null
    if ($lanes.PSObject.Properties["lane_2"]) { $lane2 = $lanes.lane_2 }
    $notUnderstood = @()
    if ($metadata.PSObject.Properties["not_understood"] -and $null -ne $metadata.not_understood) {
        $notUnderstood = $metadata.not_understood
    }
    $laneStates += [ordered]@{
        evaluator_id = $r.evaluator.id
        lane_1 = $lane1
        lane_2 = $lane2
        not_understood = $notUnderstood
    }
}
$laneLag = Get-LaneLagSummary $laneStates

# Findings: namespaced per evaluator; invalid inputs wrapped as blocks.
$allFindings = @()
$evaluatorSummaries = @()
$evaluatorStates = [ordered]@{}
foreach ($r in $results) {
    $evaluatorSummaries += [ordered]@{
        evaluator_id = $r.evaluator.id
        outcome = $r.outcome
        findings_count = @($r.findings).Count
    }
    foreach ($f in @($r.findings)) {
        $f.id = "$($r.evaluator.id):$($f.id)"
        $allFindings += $f
    }
    if ($r.PSObject.Properties["state"] -and $null -ne $r.state) {
        $evaluatorStates[$r.evaluator.id] = $r.state
    }
}
foreach ($inv in $invalid) {
    $description = "Invalid evaluator result $($inv.file) was not composed: $($inv.problem). The invalid result is wrapped as a blocking finding; composition fails closed rather than skipping it toward pass."
    if ($description.Length -gt 500) { $description = $description.Substring(0, 500) }
    $allFindings += [PSCustomObject][ordered]@{
        id = "invalid:$($inv.file)"
        severity = "critical"
        kind = "schema_violation"
        subject = $inv.file
        description = $description
        evidence_refs = @([ordered]@{ ref = $inv.file; kind = "observed"; description = $inv.problem })
        provenance_refs = @($inv.file)
        uncertainty = "none"
        recommended_action = "block"
        rationale = "An evaluator result that cannot be validated cannot certify anything; it blocks composition (Spec 003 FR-6.2)."
    }
    $evaluatorSummaries += [ordered]@{
        evaluator_id = "invalid:$($inv.file)"
        outcome = "block"
        findings_count = 1
        invalid = $true
        file = $inv.file
        reason = $inv.problem
    }
}

$allFindings = @($allFindings | Sort-Object {
    $sev = if ($_.PSObject.Properties["severity"]) { $_.severity } else { "info" }
    if ($script:SeverityOrder.ContainsKey($sev)) { $script:SeverityOrder[$sev] } else { 99 }
}, { if ($_.PSObject.Properties["id"]) { $_.id } else { "" } })

# Outcome: invalid inputs vote block under every strategy.
$outcomes = @($results | ForEach-Object { $_.outcome }) + @($invalid | ForEach-Object { "block" })
$composedOutcome = Resolve-Outcome -Outcomes $outcomes -Strat $Strategy
$gating = ($Strategy -eq "strict")
$blockOverridden = ($outcomes -contains "block") -and ($composedOutcome -ne "block")

# Iterate target: most common target_phase among iterate results,
# deterministic tie-break (frequency, then alphabetical).
$iterateTarget = $null
if ($composedOutcome -eq "iterate") {
    $targets = @($results | Where-Object { $_.outcome -eq "iterate" -and $_.PSObject.Properties["next_action"] -and $_.next_action -and $_.next_action.target_phase } | ForEach-Object { $_.next_action.target_phase })
    if ($targets.Count -gt 0) {
        $iterateTarget = ($targets | Group-Object | Sort-Object @{ Expression = { $_.Count }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false } | Select-Object -First 1).Name
    }
}

# Contradictions (findings on one subject with opposing kinds).
$negativeKinds = @("unsupported_claim", "contradiction", "missing_evidence", "unverified_assertion", "provenance_gap", "coverage_gap", "traceability_gap")
$contradictions = @()
$bySubject = @{}
foreach ($f in $allFindings) {
    $subj = if ($f.PSObject.Properties["subject"]) { $f.subject } else { "" }
    if (-not $bySubject.ContainsKey($subj)) { $bySubject[$subj] = @() }
    $bySubject[$subj] += $f
}
foreach ($subj in $bySubject.Keys) {
    $group = $bySubject[$subj]
    if ($group.Count -ge 2) {
        $kinds = @($group | ForEach-Object { $_.kind })
        $hasNegative = ($kinds | Where-Object { $negativeKinds -contains $_ }).Count -gt 0
        $hasPositive = ($kinds | Where-Object { $negativeKinds -notcontains $_ }).Count -gt 0
        if ($hasPositive -and $hasNegative) {
            $contradictions += [ordered]@{
                subject = $subj
                finding_ids = @($group | ForEach-Object { $_.id })
                description = "Conflicting findings on subject '$subj'"
            }
        }
    }
}

$summaryParts = "$($results.Count) evaluator(s) ran. Outcomes: $(($evaluatorSummaries | ForEach-Object { "$($_.evaluator_id)=$($_.outcome)" }) -join ', '). $($allFindings.Count) finding(s) total."
if ($invalid.Count -gt 0) {
    $summaryParts += " $($invalid.Count) invalid result file(s) were wrapped as blocking findings."
}
if (-not $gating) {
    $summaryParts += " Strategy '$Strategy' is non-gating (advisory)."
}
if ($laneLag -ne "") {
    # P5-V2: lag is stated in the headline itself, pass or not — a
    # lane-1-green composed outcome must never read as settled,
    # accepted, or digested work.
    $summaryParts += " $laneLag"
}
if ($summaryParts.Length -gt 500) { $summaryParts = $summaryParts.Substring(0, 500) }

$metadata = [ordered]@{
    timestamp = $timestamp
    duration_ms = 0
    artifacts_evaluated = @()
    deterministic = $true
    evaluator_count = $results.Count
    contradictory_findings = $contradictions
    composition_strategy = $Strategy
    evaluator_results = $evaluatorSummaries
    invalid_results = @($invalid | ForEach-Object { [ordered]@{ file = $_.file; reason = $_.problem } })
    duplicate_results_ignored = $duplicateFiles
    gating = $gating
}
if ($laneStates.Count -gt 0) {
    $metadata["lane_states"] = $laneStates
}
if (-not $gating) {
    $metadata["non_gating_reason"] = "Strategy '$Strategy' composes advisory outcomes; the result is marked non-gating and must not be used as a release gate (Spec 003 FR-6.6)."
}
if ($blockOverridden) {
    $metadata["block_overridden"] = $true
}

$composed = [ordered]@{
    schema_version = "1.0"
    evaluator = [ordered]@{
        id = "composed"
        version = "1.0"
        name = "Composed ($Strategy)"
    }
    phase = $Phase
    outcome = $composedOutcome
    summary = $summaryParts
    findings = $allFindings
    next_action = [ordered]@{
        kind = $composedOutcome
        target_phase = $iterateTarget
        message = "Composed outcome: $composedOutcome."
    }
    metadata = $metadata
    state = $evaluatorStates
}

Emit-Composed $composed
