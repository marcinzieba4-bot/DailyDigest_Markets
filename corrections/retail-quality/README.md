# Retail narrative selection and review

The reviewed revision covers 158 reconstructed editions: 118 have editorial
changes and 40 retain their supported selections. All 145 live editions,
including August 2026, and the live Lambda are protected. The export contains
121 reports because three unchanged editions remain in the month bundles.
All 372 origin artifacts and 130 public artifacts passed verification. All 145
protected live HTML editions, the latest report and archive index passed
independent full-body SHA checks. Every live HTML/JSON/PDF key was excluded from
publication. Native rechecks completed for 3 of 435 untouched live variants; the
remaining 432 checks are explicitly pending because the managed gateway
intermittently fails before reaching AWS. Ordinary configured AWS access
completed the revised publication without changing credentials or network
policy. Source metadata and public delivery recovery used read-only public CI
jobs.

[Open the local review index](review.html). `Retrospective_Retail_Revisions.zip`
is an ignored local review bundle with all 121 HTML/PDF/JSON exports. The exact
publication status and its verification scope are recorded in
`audit/final_validation.json` and `audit/delivery_verification.json`.

The recurring problem was selection without editorial memory. The generator
favoured rising assets, repeatedly offered metals/AI/Tesla as examples, called
its lead the “#1” trade, and supplied no previous retail editions. Day-by-day
source and numerical checks could pass while the month repeated the same angle.

The solution is chronological selection, evidence for a changed story and a
review across editions. It is not a quota of different tickers. A real trend can
persist; a changed price alone does not justify republishing its full essay.

## Select before writing

For each report, use only its eligible dated feed/card and earlier editions:

1. Build a shortlist from concrete catalysts and actual discussion evidence.
   Include reversals and failed narratives, not just strong price performers.
2. Compare each candidate with its prior appearance. Record what changed: a
   result, product/customer event, regulatory development, reversal or a dated
   attention observation. Do not treat a new wrapper or subtitle as a new story.
3. Choose the best-supported lead and distinct supported secondary narratives.
   There is no reserved daily metals, AI, crypto or comeback slot. Keep a repeat
   when its new evidence warrants it. An unchanged theme becomes a short
   carryover; it should not occupy the full lead essay again.
4. Attribute observed discussion to its source. A price rise or news headline
   does not establish a measured ranking of retail trading or social activity.
   Counts and rankings require an explicit dated population and measurement.
5. Review the rolling sequence before publication. The full-month frequency
   table is diagnostic and must not become future knowledge used to select an
   earlier historical report's assets.

## Canonical report preflight

Run from the repository root after writing the specs:

```sh
python corrections/retail-quality/retail_quality.py corrections/2025-09 \
  --output corrections/2025-09/checks/retail_quality.json
```

The audit resolves asset aliases and broader families separately. For example,
GLD and SLV remain distinct instruments but share a precious-metals family;
IONQ and RGTI share a quantum family. Review signals include:

- The same basket, or three of four names carried to the next report.
- The same lead for three reports.
- One family present in at least four of the trailing five reports.
- Repeated assets without a newly cited source published since their prior
  appearance's cutoff. URLs, not date-local citation IDs, identify reused stories.
- High similarity after removing prices, dates, citations and common words.
- Unsubstantiated ranking or numerical social-activity phrasing.

These flags require editorial judgment; they do not prove that a theme is wrong.
The text score is lexical, not an embedding-based semantic or factual verdict.
Index timestamps also do not establish the original article body's vintage.

Citation membership and timestamps are hard checks. Every cited item must be in
that report's own feed and strictly before its cutoff; missing, malformed,
timezone-free and at/after-cutoff timestamps fail. The existing month validator
still owns age windows, complete market figures, structure and report length.

## Record dispositions and require review

Use the exact IDs emitted by the preflight in
`checks/retail_editorial_decisions.json`:

```json
{
  "decisions": [
    {
      "flag_id": "2025-09-02:GLD:family_concentration",
      "disposition": "material_update",
      "changed_angle": "Explain the specific new development and why it changes this asset's previous narrative.",
      "evidence_ids": ["n1234"],
      "reviewer": "independent-editor"
    }
  ]
}
```

`material_update` requires eligible evidence cited in that entry, newly published
since the asset's prior report cutoff and not merely the same story with another
date-local ID. `brief_carryover` permits old evidence for a side item of at most
160 words, with a specific rationale; it cannot clear an unchanged full lead.
`reviewed_selection` can clear a concentration/basket diagnostic when the editor
explains the selection; it cannot clear stale/recycled/repeated-lead warnings.
A ranking claim additionally requires `measurement_scope`. The explanation is
review evidence, not machine proof that a catalyst matters.

Then require the completed gate before the ordinary build/publish pipeline:

```sh
python corrections/retail-quality/retail_quality.py corrections/2025-09 \
  --decisions corrections/2025-09/checks/retail_editorial_decisions.json \
  --output corrections/2025-09/checks/retail_quality.json --require-reviewed
```

This exits unsuccessfully for evidence failures, unresolved/invalid flags or
stale decisions. Receipts bind every spec by SHA256. Any later spec edit requires
rerunning the gate and binding the final publication manifest to the new receipt.
Do not fabricate dispositions to obtain a green status. An independent editor
must review the claimed changed angle and the scope of its supporting headline.

## Published legacy snapshot audit

The same tool can inspect the saved HTML/JSON snapshot without rewriting it:

```sh
python corrections/retail-quality/retail_quality.py \
  corrections/retail-quality/work/published --published-snapshot \
  --output corrections/retail-quality/audit/published_quality_before.json
```

The snapshot uses `html/YYYY-MM-DD.html` and optional `json/YYYY-MM-DD.json`.
Spec-bearing JSON retains `news_cutoff_utc`. Original live JSON retains its own
`generated_at`; no new midnight cutoff is imposed on those editions. When full
dated sources are unavailable, the audit explicitly reports source timing as
unverified and never declares the strict evidence gate passed. Frequency and
text diagnostics remain useful for attribution, shortening unchanged carryovers
and removing unsupported ranking claims. They do not authorize invented events
or new retrospective factual claims. Historical limits must remain visible in
the final revision audit.

## Retrospective workflow and live-report boundary

The user clarified that August was analyzed live. Recurring live themes may
faithfully reflect persistent attention; frequency alone is not an error.
All 145 same-day live editions are protected, including August. The 158
reconstructed editions are the correction scope; the exact allowlist is in
`audit/retrospective_scope.json`. The artifact builder and publisher reject live
dates. The live Lambda source, configuration and deployment remain unchanged.

`retrospective_context.py` can read up to five strictly earlier retail archive
excerpts with an explicitly configured read-only client. It never reads the
report date or later dates and surfaces real access errors. Prior selections
are editorial memory, not factual input. Each historical writer still needs
its own frozen feed/card. BRIEF/CRITIC instructions and the build/publish gates
require chronological comparison and evidence-bound review. No automatic
category slot or variety quota is introduced.

## Verification

```sh
python -m unittest discover -s corrections/retail-quality/tests -v
python -m py_compile corrections/retail-quality/retail_quality.py retrospective_context.py
```

The regression suite covers alias/family normalization, price-only rewrites,
date-local ID reuse, fresh-catalyst persistence, stale or uncited claimed evidence,
cutoff boundaries, missing timestamp timezone, unsupported rankings, chronological
isolation, legacy cutoffs/source limitations, HTML extraction and read-only prior
archive access. It never makes network calls or changes a published report.

## Build, publish and resume

System Python provides Playwright/pypdf; the AWS tools environment provides
boto3/BeautifulSoup. After the independent review and final source-date audit:

```sh
python corrections/retail-quality/build_revisions.py
python corrections/retail-quality/finalize_revisions.py
python corrections/retail-quality/package_review.py
/workspace/.report-tools/bin/python -I corrections/retail-quality/publish_revisions.py
/workspace/.report-tools/bin/python -I corrections/retail-quality/publish_revisions.py --go
/workspace/.report-tools/bin/python -I corrections/retail-quality/verify_revisions.py
```

The publisher requires unchanged reviewed input/artifact hashes and original
origin SHA256 proofs, backs up each replaced object, and uses conditional
writes. `--resume --go` retains the original receipt and backups. It updates
existing retrospective objects and three existing month collections only;
the archive index, latest report and live editions are never write targets.
The strict verifier also rechecks all 435 protected live format versions. Its
resumable checkpoint binds successful observations to the publication run,
target manifest and original snapshots. `import_verified_proofs.py` can ingest
independently verified public checks or complete native preservation checks;
it does not create observations. When the managed gateway blocks optional native
checks, `record_delivery_proof.py` records completed origin/public delivery and
independent live-HTML/latest/index preservation separately, with the exact native
pending count. It never declares the full preservation verifier passed.
Generated PDFs/ZIPs and original snapshots stay out of Git. Original snapshots
can be restored from the per-run S3 backups recorded in the receipt;
selected newly introduced legacy evidence is embedded in patch JSON and exports.
