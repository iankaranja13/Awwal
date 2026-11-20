# Awwal — demo video script (3 presenters, ~4 minutes)

Live site: https://awwal-dun.vercel.app. Record at 1080p, quiet room,
browser zoom 110–125%. Reload the page right before recording for a
fresh anonymous user. Captions on when you export.

## Part 1 — The problem and the assessment (Speaker A, ~80s)

*[Homepage.]* "Men facing fertility worries usually enter care late —
after months of difficulty, or after their partner has been through
assessment. Awwal moves that first step upstream: a private,
bilingual front door that turns early signals into the right care."

*[Click Start. On consent, toggle all four on.]* "Everything starts
with explicit consent — four separate permissions, none pre-ticked.
No account, no name. Your answers stay encrypted and under your
control."

*[Intake: answer a few yes/no, mark one Not sure, skip one with Continue.]*
"The intake takes about four minutes. Anything you're unsure about or
skip is never treated as a no — missing answers can only raise caution,
never lower it."

*[Finish intake → Results. Expand one flag; open the trace sheet.]*
"Results are screening signals, not a diagnosis. The engine behind them
is deterministic rules — the same rules for everyone — and this trace
shows exactly how each decision was made. Over to you for what happens
next."

## Part 2 — Safe triage and the clinical loop (Speaker B, ~90s)

*[Next step page showing the route.]* "Thanks. Every assessment ends in
exactly one safe next step. Ours points to a urology specialist — and
notice the guardrail: anything beyond self-care needs a clinician's
sign-off before it can be confirmed."

*[Booking: pick teleconsult, filter language and clinician, choose a
provider and slot, enter a phone, request booking.]* "Booking stays
low-friction: video call, blood test, sample collection or in person,
with language and clinician filters, and home sampling where offered.
Your phone number is asked only here, only for this booking."

*[Status page: referral waiting in clinician review. Go to Clinician
view, open the case, sign off.]* "Now the human oversight. The case
waits in a clinician queue with a one-page brief. Only a signed-off
referral can proceed — the system enforces that; no one can click past
it."

*[Back on Status: advance through Booked, Attended, Results explained;
write an outcome note; close.]* "And the loop closes properly: booked,
attended, results explained, and a documented outcome — tracked the
whole way. One more thing: if anyone reports an urgent symptom, there
is no booking and no AI text — just a static emergency screen that says
get care today."

## Part 3 — Privacy, engineering, close (Speaker C, ~70s)

*[Privacy page: show a share, revoke it, scroll activity, download data.]*
"Finally, privacy by design. You see every share and can revoke it,
every access is logged for you to inspect, and you can download or
permanently delete everything with one tap."

*[Optional: API docs page in a second tab, benchmark report screenshot.]*
"Under the hood: rules decide, AI only explains, clinicians validate.
Every AI sentence passes a safety validator or falls back to fixed
templates. Ten synthetic benchmark cases plus a hundred variants check
routing, urgent escalation, missing-data handling and Arabic–English
parity on every change — currently ten out of ten with zero
under-triage."

*[Back to homepage.]* "Awwal: earlier signals, a trusted private path,
and the right care before infertility is ever diagnosed. Thank you —
we're happy to take questions."

## Emergency fallbacks (don't record these)

- If the site is slow: the trace sheet and results pages are static
  after loading; pause, then continue talking over them.
- If anything errors live: cut to the pre-recorded full run
  (record one clean pass first and keep it).
- Keep one browser tab on the API docs as proof the backend is real.
