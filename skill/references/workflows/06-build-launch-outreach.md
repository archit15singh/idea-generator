# 06 / Build MVP + launch + outreach + interview

Runs only on wedges that graduated from stage 05. The MVP is a survey of demand, not a product. Uninstrumented MVP is a useless row.

## 6.1 Build (instrumented from line one)

For each surviving wedge, build the minimal landing-page / proof-slice:

- One page, one headline, one CTA (waitlist or buy-button).
- Analytics firing on day 1: sources, scroll, CTA conversion.
- 2+ pricing-test variants (or two price anchors if A/B infra isn't worth it).
- Every form writes to a `waitlist` table, capturing source, referrer, ICP-attributed fields from the validated persona.

Code that does not instrument is not an MVP. It's a tech demo. Skip those.

## 6.2 Launch

Publish the landing page. Mirror the headline + CTA in social/outbound message.

## 6.3 Outreach

30 personalized messages per wedge per cohort. Reuse the validation-stage copy. The cohort is already warmed. Do not regenerate from scratch; that breaks measurement. Append every send/reply to `outreach_log`, extending stage 05's rows.

## 6.4 Interview

For every reply indicating pain, schedule a 20-minute call. Capture:

- pain frequency (weekly/monthly)
- tools already tried
- willingness to pay (offer a test price)
- referral willingness

Write findings back as `customer_complaint` edges on the Problem Graph. These feed pattern detection in stage 07.

## Output

- one `waitlist` row per signup
- `outreach_log` rows extending the validation cohort
- Problem Graph edges from each interview (writes happen in stage 07 cluster; this stage stages the raw notes)

## Refs

- `references/design/structural-problems.md`: MVP-as-survey argument
- `references/design/factory.md`: the per-wedge stages
- `references/design/analysis.md`: the open questions on failure-mode and instrumentation