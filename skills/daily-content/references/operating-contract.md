# Campaign operating contract

## Saved state

Keep records in the user-selected project/artifact destination. Use Markdown for briefs/review and JSON or a table for durable state; do not create duplicate stores without need.

- Brand context: dated sources for buyer, product claims, offers, destination, voice, exclusions, asset rights and account ownership. Record what is observed versus a hypothesis.
- Daily pack: campaign_id, pack_id, content_date, audience_timezone, audience_id, experiment_id, creative_id and revision; task, hook, proof and evidence references; per-channel copy, asset paths and CTA; proposed publication time; costs and authorization scope; readiness and missing inputs.
- Distribution ledger: account_id, channel, creative_id/revision, asset hash, destination, tracking parameters, requested timestamp/timezone, remote post/job ID, submission outcome, verified status and live URL when available.
- Results: source/report URL, retrieval time, reporting window, account/channel, remote post ID, creative_id, metric, value and unit; numerator/denominator for rates; attribution method/window; missing-data reason. Keep metric definitions alongside records.
- Feedback: creative/revision, rejection reason, requested correction, evidence and later decision. Human approval applies to the reviewed revision and named destination, not any later materially changed version.

Useful content states are `brief`, `needs_evidence`, `needs_capture`, `draft`, `ready_for_review`, `approved`, `scheduled`, `published`, `failed`, `rejected`. Track individual channel states: partial success is not whole-pack publication. Keep unknown outcomes explicit rather than assuming failure or success.

## Performing-post trends

Consume the report from separately installed `content-trend-research` in managed-skills. That package owns Treg discovery, watchlists, snapshots, freshness and momentum calculations. Retain its source/opportunity IDs and evidence references in each adapted creative; keep external attention signals separate from owned outcomes. If research access is missing, use supplied evidence with its date and limitation instead of implying a fresh trend feed.

## Metricool and distribution

Discover the actual granted tools or authorized UI. Inspect the brand/account identity, connected networks, timezone, supported media, link handling and scheduling capabilities before preparing connector payloads. Metricool availability in a different runtime is not access in this runtime. Do not invent endpoint names, authentication flows, API payloads or a compatible CSV format. If unavailable, export a connector-neutral local handoff with assets/copy/timing and identify the missing connection.

Check existing queued and published posts before creating a new one. Use a stable local key from account + creative revision + intended slot; use provider idempotency only if its schema supports it. Persist the returned remote ID. After a timeout, inspect that ID or reconcile the remote queue before retrying; never blindly resubmit. Cap recovery to one reconciled retry, then retain `unknown` or `failed` for the affected channel with the error and next action. Do not repeat successful channels.

Scheduling success requires verification in the remote queue. Publication success requires the provider's published state/live post. Local exports, accepted uploads and HTTP success alone are not publication. Respect existing scope for edits, sends and posts; do not expand a content task into paid ad activation or creator outreach.

## Measurement and learning

Use owned social reporting for reach, retention where available, saves, shares, comments, profile visits and outbound clicks. State the platform's denominator for each engagement rate. Separate paid from organic distribution and channel/format cohorts.

Use first-party product analytics for confirmed signup and activation events, and billing/commerce reporting for purchases, revenue and refunds. A landing click, checkout start or license activation is not automatically a new paid sale. Do not sum conversions from overlapping sources. Map a post to a sale only when the tracking/report supports that resolution; otherwise show aggregate sales beside content results and state the attribution gap.

Use consistent non-sensitive UTM values where the destination and reporting support them: source=channel, medium=organic_social (or the actual medium), campaign=campaign_id, content=creative_id. Validate redirect survival before claiming attribution. Never put customer identifiers in tracking URLs. Retain consent and collection coverage caveats.

Review at roughly 24 hours and 7 days after each post, with a weekly business-outcome review; adapt to actual latency and volume. Separate early hook/retention signals from mature sales results. Report sample sizes and inconclusive results; no sales access means unknown, not zero. Low-volume pilots can identify production and audience problems without establishing a winner.

If installed, `experiment-feedback` can join owned evidence to the creative hypotheses; preserve its evidence format and validate with its helper. `analytics-dashboard` is optional when a real data source and dashboard destination exist. Do not deploy a dashboard merely to complete a content run.

Feed back a concrete decision: repeat, change hook, improve demonstration, change CTA, retire, or collect more data, with evidence and the next test. A competitor's viral views cannot substitute for owned results.

## Recurring operation

A recurring run needs an actual scheduler, a persistent artifact destination, authenticated execution environment, channel scope and budget. If the user asks to activate recurrence, configure the available scheduler according to its real tools after resolving required schedule details. Default to draft production unless publication is already authorized. Record scheduler/run IDs and last successful run. Keep failed jobs visible. Do not imply that writing this skill activates an automation.
