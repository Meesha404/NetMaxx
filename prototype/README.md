# Event Router — backend prototype

A single Python 3.10+ script. No pip, npm, frontend, database server, or third-party Python dependencies required.

Pipeline: CSV/JSON → People Data Labs identity/profile lookup → conservative identity gate → optional HarvestAPI posts via Apify → OpenAI Structured Outputs → deterministic weighted score → prioritized JSON.

## Run the credential-free demo

```bash
cd event-router
python3 event_router.py sample_attendees.csv --demo --output demo_output.json
python3 -m unittest -v
```

The sample names and companies are fictional. Demo scores are fixed synthetic fixtures, not LLM results. No real LinkedIn URLs or profile claims are fabricated. Use your own attendee list for live mode.

## Live run

Set these environment variables in your terminal or secret manager:

```bash
export PDL_API_KEY='your-pdl-key'
export OPENAI_API_KEY='your-openai-key'

python3 event_router.py attendees.csv \
  --icp icp.json \
  --limit 20 \
  --top-k 10 \
  --output prioritized.json
```

Enable recent posts with an Apify account that can run the named actor:

```bash
export APIFY_TOKEN='your-apify-token'
python3 event_router.py attendees.csv --icp icp.json --limit 20 --posts
```

API access and enrichment credits are billed by each provider. The script does not load `.env` automatically. Keep keys out of code and source control. Start with a small `--limit` to measure identity coverage and credits before processing 3,000 people. Remove the limit for a full event.

## Input and customization

CSV headers must include `Attendee Name`, `Current Company`, `Job Title`. JSON must be an array of objects with those same keys. Optional `LinkedIn URL` is preserved as user-supplied provenance. A conflict with the provider-resolved URL routes the attendee to review and prevents scoring; the supplied URL does not bypass the name/company identity gate. Other additional fields are ignored. Blank or invalid rows appear in the output error queue; duplicates retain all source row numbers. Header spelling is exact; UTF-8 BOM is supported.

Edit `icp.json` to change the target, requester background, exclusions, score weights, criteria and shortlist threshold. Keep the five dimension names. Requester context is necessary for genuine shared-background hooks. Do not add unverified founder achievements as facts. No title-based prefilter silently removes potential candidates.

| Dimension | Default weight | Evidence sought |
| --- | ---: | --- |
| Role fit | 30% | Relevant founder or investor mandate |
| Topic fit | 30% | AI developer tooling work or focus |
| Active intent | 20% | Explicit evaluation, purchase, partnership or investment interest |
| Connector value | 10% | Relevant portfolio, community or introduction activity |
| Shared background | 10% | Professional overlap with the supplied requester |

The model rates each dimension 0–10. Code calculates `max(1, sum(rating × weight) / sum(weights))`, rounded to two decimals. Missing evidence contributes zero and remains visible in `data_gaps`. This is an evidence-conservative ranking heuristic; sparse profiles may rank lower. It is not a calibrated probability or a trained predictor of meeting success. Validate and tune with founder-labeled attendee pairs before making accuracy claims.

## Identity and enrichment contract

People Data Labs (PDL) is used because the original Proxycurl service shut down. PDL resolves name plus company and returns the matched profile in one call, avoiding an unnecessary second lookup. An accepted match requires:

1. Provider likelihood at least 8/10 by default (`--min-likelihood`, range 6–10).
2. Both name and company present in PDL's matched-input list.
3. A structurally valid LinkedIn personal-profile URL supplied by the provider.
4. Current company equal after conservative normalization of case, whitespace and legal suffixes.

The company lookup can match past employment. The fourth check therefore routes old employers and unresolved company aliases to review. This gate favors precision over coverage; it does not enumerate alternative identities and cannot independently guarantee identity. Accepted identities are labeled `high_confidence_match`, with `verified: false`, rather than represented as LinkedIn-verified. The likelihood value is the provider's score, not a percentage.

PDL's `summary` is exposed as both `summary` and the about-equivalent `about`; they are not two independent source fields. Missing summaries, job descriptions and history remain null or empty. Field availability depends on provider coverage and account access. Current role, headline, summary, job summary, up to ten jobs and thirty skills form a bounded evidence payload. Personal phone, email and home address data are not retained or sent to the LLM.

Recent posts require `--posts`; PDL is not assumed to supply them. The Apify adapter requests up to five original posts from the previous three months. It excludes reposts and quote posts, then checks returned author URL and timestamps against a 90-day window. Wrong-author, undated or stale results are discarded. Failure or absent posts is explicit; role/history-based icebreakers remain possible. Profile source URLs indicate provider attribution, not an independent browser verification.

## Output contract

`prioritized.json` contains:

- `ranked_attendees`: descending score, with identity confidence, profile, evidence IDs and URLs, dimension ratings, reason, icebreaker, data gaps and model/token metadata.
- `top_candidate_ids`: up to `--top-k` distinct resolved identities scoring at least the configured threshold; it can contain fewer than five when evidence is insufficient.
- `review_and_errors`: ambiguous/unresolved people, evidenced exclusions, invalid input, failed rows and rows omitted by `--limit`.
- `run_status`, `fatal_error`, mode, model, ICP and row counts for auditability.

Only non-excluded, successfully scored people enter the ranked list. Low fit is a real numeric score; API or identity failure is `score: null`. Scores and identity confidence are kept separate. Ties are sorted by stable attendee ID.

## Reliability and operational boundaries

- Standard-library HTTPS clients with bounded responses, timeouts and no authenticated redirects.
- Five attempts maximum for rate limits, selected transient server errors and network failures; exponential backoff plus jitter; honors numeric/date `Retry-After`. Delays over 60 seconds defer the row instead of retrying too early.
- Provider authentication/billing errors halt core enrichment/scoring and preserve a partial output. Optional-post failures degrade gracefully. OpenAI insufficient quota is not treated as ordinary throttling.
- Per-provider request pacing (`--interval`, default one second). Sequential execution keeps the prototype simple; a large list may take hours. No throughput claim is implied. Increase throughput later using provider-approved batch or concurrency limits.
- Prompt data is bounded by field limits, output tokens are capped, and OpenAI TPM errors follow the same 429 retry path. This is reactive throttling, not an account-wide token scheduler.
- Model refusals, truncated output, malformed responses, out-of-range ratings and unknown evidence IDs never silently become valid scores.
- SQLite caches enrichment and scoring for 24 hours; score cache keys include the ICP, model, prompt, schema and evidence. Rerunning resumes through cached successes; errors are retried. Changing the ICP rescales via a fresh model assessment while reusing enrichment.
- Recent-post cache has its own 24-hour TTL. Paid actor POSTs are not automatically replayed after ambiguous network/5xx failures. A one-day guard survives interruption; inspect the Apify console if `posts_previous_run_uncertain_check_apify_console` appears. The guard is conservative and can suppress a call that never reached the provider. Failed actor work may still incur charges. GET/model retries can also repeat billable work after uncertain responses.
- Atomic output checkpoint after each attendee and final atomic write. Ctrl-C during a row produces a partial matrix; a force kill can leave the last checkpoint marked `in_progress`. Rerun the same command to recover. Run one process per output/cache file.
- Logs contain counts/status/error codes, not attendee names, provider bodies or API credentials. Local cache/output files contain professional data; keep them in access-controlled storage and delete them when no longer needed. Cache TTL prevents reuse but does not purge expired data from disk.

Exit codes: `0` complete (review/unresolved results are normal); `1` completed with API/row issues, post failures or an explicit limit; `2` configuration/fatal error or interrupted run. If configuration fails before processing, an existing output is left untouched; always check the exit code and timestamp.

Structured Outputs enforces shape; it does not prove evidence supports every generated sentence. The script validates cited IDs, but semantic grounding and company aliases still require evaluation. This prototype is production-oriented infrastructure, not a live-validated production deployment. No credentials were supplied with the build, so paid endpoints have not been smoke-tested in this environment.

## Source contracts checked for this build

- [PDL enrichment inputs](https://docs.peopledatalabs.com/docs/input-parameters-person-enrichment-api)
- [PDL enrichment response](https://docs.peopledatalabs.com/docs/output-response-person-enrichment-api)
- [PDL person schema](https://docs.peopledatalabs.com/docs/fields)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [HarvestAPI actor inputs](https://apify.com/harvestapi/linkedin-profile-posts/input-schema)
- [HarvestAPI post output](https://apify.com/harvestapi/linkedin-profile-posts)
- [Apify synchronous run contract](https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post)
- [Proxycurl shutdown announcement](https://nubela.co/blog/goodbye-proxycurl/)

The application dates, competitor metrics, Hotbox ARR and networking-efficiency claims in the brief are positioning inputs, not verified claims embedded in this software.

## Continuation milestone — 1.1.0

See [PILOT.md](PILOT.md) for the two-person smoke test, 20-person pilot, secure local credential setup and founder review workflow. The standard-library backend remains the implementation; no frontend or external packages were added.

The 20-test baseline and fictional demo passed locally. The expanded 40-test suite adds regressions for malformed nested profile fields, conservative company and duplicate matching, invalid post links and date ordering, cached-post age checks, truncated HTTP reads, retained fatal-row evidence, complete checkpoint accounting, request/token measurement and review denominators. Run `python3 -m unittest -v`.

Repairs preserve meaningful company punctuation, so distinct companies no longer match only because punctuation was removed. Optional PDL fields are bounded and type-checked before storage or scoring. Posts use HTTPS LinkedIn post URLs, canonical timestamps and a fresh age check on cache reuse. Incomplete HTTP reads enter the bounded retry path; uncertain paid Apify POSTs remain protected. A fatal attempted row is now an explicit error with any identity/evidence already collected, while later rows remain unprocessed. Each checkpoint includes all input records and a run ID, start time and elapsed runtime.

`pilot.py preflight` validates inputs and reports credential presence without calling providers. `pilot.py review` exports a JSON labeling file without overwriting prior judgments. `pilot.py summarize` reports coverage, reviewed shortlist usefulness, identity judgments, unsupported hooks, runtime and available request/token counts. Reviews are bound to the exact source output by digest. Example `demo_review.json` and `demo_metrics.json` are synthetic, unreviewed illustrations, not live results.

Official PDL input/output, HarvestAPI actor input/output, Apify synchronous-run and OpenAI Structured Outputs documentation linked above were inspected on 2 October 2026. Their documented request shapes remain compatible with the adapters; account access and real response quality remain untested. The existing OpenAI model was retained.

Remaining boundaries: no real attendee data or API keys were supplied to this run; no paid endpoint was called. Evidence-ID validation does not establish semantic truth. Human review, live identity quality and actual provider billing remain unvalidated. No deployment or remote Git repository was configured.

## Local NetMaxx app

The first local UI is in `app/`. It accepts PDF/text resumes and Excel/CSV attendee lists, a meeting objective, and an optional event/Luma reference. Start with the bundled Python runtime on this Mac:

```sh
/Users/manishasharma/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 app/server.py
```

Open http://127.0.0.1:8765 and choose **Load Manisha’s 10-person test**, or upload your files. The local app needs `pypdf` and `openpyxl` (already present in the bundled runtime). The original CLI remains standard-library-only.

This is explicitly a theme-overlap trial, not the live LLM pipeline. It applies transparent keyword-theme matching to the researched public summaries in `private/netmaxx_public_review.json`. Changing the background or goal recomputes the ranking. Goal themes receive double weight. New attendee URLs have no researched evidence and remain unranked; company conflicts and the two previously withheld profiles stay out of the ranking. These trial scores differ from the earlier assistant-reviewed scores and are not confidence probabilities. Full semantic ranking and automatic public evidence acquisition remain future integration work.

The LinkedIn input stores a reference; users must provide readable professional text. The Luma input stores event context and does not import attendees. No API calls, credentials, or external upload services are used by this app. Files are parsed in memory. Meeting judgments last for the current page session and can be exported as JSON. The app binds only to localhost and rejects cross-origin POSTs. Do not expose this development server publicly. Private sample files are deliberately excluded from the distributable source archive.

### Intent modes

The local app now has Hiring Connections, Professional Peers and Social Connection modes, plus an automatic interpretation option. Goal edits refresh results after a short pause; stale requests cannot overwrite newer results. Mixed or unsupported requests ask for clarification rather than silently falling back. Gender constraints yield no confirmed matches because the evidence set contains no self-described gender.

Hiring uses reviewed recruiter/founder signals plus professional-theme relevance. It distinguishes possible influence from a current suitable opening. Social uses only attributed interest or playful-content cues; work achievements do not increase social scores. Without the requester's interests, it orders evidence usefulness, not personal compatibility. Explicit social interests narrow results to supported matches. Public evidence remains a dated, manually researched snapshot; the app does not fetch new profiles on demand and is not a general language model.

Regression coverage includes the real ten-person dataset under hiring, peers and social requests, interest changes, gender constraints, identity/company gates, ambiguous goals and negated dating requests. Run `python3 -m unittest -q` (48 tests).
