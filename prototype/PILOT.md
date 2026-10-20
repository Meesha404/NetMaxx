# Small live attendee pilot

Status on 2 October 2026: offline validation complete; live validation blocked by a real attendee list and local API setup. No paid provider was called. Default event objective remains provisional until confirmed by the founder.

## Prepare the inputs

Use 20–30 real attendees from the event. Save the list as `private/attendees.csv` (or JSON); this directory is ignored by Git. Required columns/keys are exactly `Attendee Name`, `Current Company`, `Job Title`. JSON is an array of objects. Do not put secrets in the data.

Review `icp.json` before spending credits. Its current target is B2B SaaS founders and investors interested in AI developer tools. The requester's goal is design partners and relevant investors, with former GE / enterprise product and strategy background. Change these only to the actual event objective and supported background.

From the project directory:

```sh
mkdir -p private runs
chmod 700 private runs
python3 pilot.py preflight private/attendees.csv --icp icp.json
```

Preflight makes no network requests. It reports valid unique attendee count, invalid rows, configured objective, and credential presence only. `pilot_size_ok` accepts 2–30 unique attendees (including the requested 10-person test) and should be true, and invalid rows should be zero before the pilot. Presence does not prove account access or credit balance.

## Set up APIs exactly when ready for the two-person smoke test

PDL enrichment access and an OpenAI API project with usable credit/model access are required. Keep credentials in a local secret manager or set them in the terminal running the command. Do not send them in chat. `.env` is not automatically loaded. This zsh example prompts without echoing keys or putting their values into command history:

```sh
read -rs 'PDL_API_KEY?PDL API key: '
echo
export PDL_API_KEY
read -rs 'OPENAI_API_KEY?OpenAI API key: '
echo
export OPENAI_API_KEY
python3 pilot.py preflight private/attendees.csv --icp icp.json
```

Variables set in a separate terminal do not automatically reach an already-running Codex process; either run the following commands in that same terminal or use the application's secure environment setup. Do not print the environment to check it.

Agree a provider budget before executing live work. The limits below bound unique input records, not a dollar amount: retries can repeat paid requests. Configure account spending controls as appropriate. No financial cost has been estimated or measured here.

## Smoke test: two attendees, posts disabled

```sh
python3 event_router.py private/attendees.csv --icp icp.json --limit 2 --top-k 10 --cache private/pilot-cache.sqlite3 --output runs/smoke.json
python3 pilot.py review runs/smoke.json --output runs/smoke-review.json
python3 pilot.py summarize runs/smoke.json --output runs/smoke-metrics.json
```

Exit 1 is expected when the file contains more than two unique attendees: the rest are marked `not_processed_limit`. Inspect `run_status`, `fatal_error`, timestamps, per-row errors and warnings. Exit 2 needs investigation; a configuration error can leave an older file untouched.

Check each resolved LinkedIn identity and its current company against the attendee record. Inspect evidence for the reason and icebreaker. If both are unresolved, review the data and provider access before increasing volume. If any identity is wrong, stop expansion and investigate rather than lowering the identity threshold.

## Pilot: first 20 attendees

After the smoke results and budget are acceptable:

```sh
python3 event_router.py private/attendees.csv --icp icp.json --limit 20 --top-k 10 --cache private/pilot-cache.sqlite3 --output runs/pilot.json
python3 pilot.py review runs/pilot.json --output runs/pilot-review.json
```

Reuse the same cache to avoid repeating successful smoke work within its TTL. This version changes normalization and cache keys from 1.0.0; old-version cache entries are not reused. Do not remove the limit for the first pilot. Expanding to 30 attendees or enabling posts requires an explicit scope/budget decision.

Apify is optional and requires `APIFY_TOKEN`, actor access, and an agreed budget before adding `--posts`. An uncertain paid actor call retains a guard; inspect its console before any retry. The synchronous adapter can time out before usable posts arrive. Posts are not a prerequisite for the first identity/relevance pilot.

## Founder review

Edit `runs/pilot-review.json`. For each attendee set these to `true`, `false`, or `null`:

- `identity_correct`: the provider profile is the intended attendee. Null means not yet established.
- `useful_to_meet`: a worthwhile conversation for the actual event objective.
- `icebreaker_supported`: the hook's factual premise is supported by the supplied evidence; an unsupported claim is false.

Fill `reviewer` and `notes` for judgments. Keep unknown labels null. Review all shortlisted candidates and uncertain identities; spot-check low-scoring profiles for sparse-data bias. The export includes identity, source evidence, reason, hook, errors and data gaps. It never replaces an existing review file. Re-export a new file if the pipeline output changes: the digest prevents old labels being silently applied to new results.

```sh
python3 pilot.py summarize runs/pilot.json --review runs/pilot-review.json --output runs/pilot-metrics-reviewed.json
```

The metrics define all denominators. Coverage uses attempted unique input triples, including a row stopped by a fatal API error, excluding invalid and unprocessed rows. Resolved identity and scoring error can overlap. Top-five/ten metrics use the distinct identities actually available on the shortlist, showing reviewed and unreviewed counts separately. Identity accuracy and unsupported-hook rates use only explicit human judgments. Zero denominators produce null, not a success rate.

`provider_usage` counts HTTP attempts (including retries) and parsed successful responses during this invocation. `openai_tokens_observed_this_run` sums only token usage returned during this invocation, including a refusal or malformed assessment if usage was returned. Cached assessment token metadata is historical and is not new consumption. Unknown usage after transport failures, PDL credit consumption and Apify billing must be checked in provider dashboards. No monetary costs are inferred.

## Decision after the pilot

Do not claim validated matching or networking usefulness until the real results and judgments exist. Record counts of wrong identities, ambiguous company matches, sparse profiles, unsupported hooks and API errors. Fix the most consequential observed failure next. Company aliases or manual overrides need provenance; neither is implemented in this milestone. Do not add a frontend or increase to 3,000 attendees until this review is convincing.

Keep cache, input, output and reviews local; remove them when no longer needed. Cache expiry prevents reuse but does not erase stored data. Use only one process per cache/output file. The local Git repository has no remote configured; nothing has been pushed or published.
