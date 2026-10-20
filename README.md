# NetMaxx product demo

A self-contained, browser-local presentation of the event-to-conversation flow, built from the uploaded NetMaxx prototype. The original Python source is retained under `prototype/`. No Python server or API credentials are required for the new demo.

## What works

- Edit a profile or extract text from a PDF/TXT résumé in the browser.
- Switch among collaboration, career, learning, hiring, and friendship intentions.
- Change a custom goal and recalculate the ranking.
- Explore a ranked shortlist and a room map.
- Inspect input evidence, score components, gaps, and conversation openers.
- Import Excel or CSV, including the original NetMaxx.xlsx column names.
- Load the ten supplied attendees using “Use my 10-person spreadsheet”.
- Save people, mark meetings, and export a printable HTML conversation plan.
- Use the five-step Walkthrough for a short screen recording.

## A 60–90 second demo

1. Start at the sample event. “NetMaxx helps me decide who to talk to before I enter a room.”
2. Point to the profile and intention. “It combines my background with what I want from this specific event.”
3. Switch Collaborate to Career. “The same room produces a different shortlist.”
4. Open a person and the evidence. “I can see why this person is relevant and how to start the conversation.”
5. Switch to Room map. “I can explore the people around my goal.”
6. Save a person and open My shortlist. “I leave with a conversation plan.”
7. Optional: load the supplied spreadsheet. Explain that it contains basic details and links, while enriched bios make the recommendations more informative.

The Walkthrough button steps through an equivalent sequence. It resets to the fictional sample so it is replayable.

## Data and behavior boundaries

The 12 sample attendee profiles and event are fictional and labeled as illustrative. The requester profile is based on the supplied user context. `dist/imported.json` contains only rows from the attached spreadsheet; their facts have not been independently verified. This deployed version is owner-private.

The ZIP omitted `private/netmaxx_public_review.json` and `private/netmaxx_attendees.json`, which the original local server requires for sample loading and ranking. Those files were not reconstructed or invented. The new demo does not invoke that incomplete path. Original backend files remain available unchanged under `prototype/`.

The demo uses deterministic theme matching, adapted from the local prototype. It is not the PDL/OpenAI/Apify pipeline, live research, or automated LinkedIn enrichment. Scores are evidence fit on a 0–10 heuristic scale, not probabilities. Goal overlap contributes up to 5, background overlap up to 3, and supplied intent up to 2. Hiring recommendations require an explicit `Open To Work` value, and use role/skills for fit. Career networking uses supplied `Hiring For` details. Friendship uses only supplied interests. Unknowns remain unknown.

The map is a visualization of recommendations to the requester, not a social graph of actual attendee relationships. At most 24 people appear in the map at once; searching narrows larger lists. The list handles up to 500 imported rows.

Session changes, uploaded files, saved contacts, and meeting marks remain in browser memory and reset on refresh. Export a conversation plan to retain the result. No uploaded file contents are sent to a server. Bundled PDF.js and JSZip perform local extraction. Fonts can be requested from Google Fonts, with local font fallbacks.

## Spreadsheet columns

Required: `Name` or `Attendee Name`.

Supported: `Job Title`, `Current Company / School`, `Current Company`, `Company`, `Linkedin`, `LinkedIn URL`, `Event`, `Bio`, `About`, `Summary`, `Skills`, `Interests`, `Hobbies`, `Looking For`, `Seeking`, `Hiring For`, `Open To Work`, `Source URL`.

Use `Yes`, `True`, `Open`, or `Open To Work` in the `Open To Work` column when explicitly supplied by the person. A recruiter looking for candidates does not establish that the recruiter wants a role.

The first workbook sheet is read, with a header row. Maximum file size is 5 MB, with additional expansion and sheet-size checks. Scanned PDFs need pasted text because OCR is not included.

## Development and verification

This is a buildless static site. Serve `dist/` over HTTP, not `file://`, because ES modules and PDF workers require an origin.

Run `npm test` for ranking and input-contract tests. `node --check dist/app.js` and `node --check dist/engine.js` validate JavaScript syntax. The Python prototype can be run independently with its original dependencies and private research files.

Browser QA was unavailable in the build environment. Automated checks cover ranking behavior, imported records, quoted CSV, duplicate identities, links, and missing evidence. UI layout, browser PDF extraction, and the browser Excel upload need a final hands-on review before recording a submission.

## Next integration step

Connect the evidence view to the existing backend's structured output through a server API, preserving identity gates and source references. Keep provider keys on the server. The current source retains those adapters but does not publish secrets or pretend the live pipeline has run.
