# Open clinical questions

Every drafted rule carries `requires_clinical_validation: true`. Nothing here
is clinical guidance. The advisor confirms or replaces each draft value.

## Thresholds (`rules/params.v0.1.yaml`)

- Is 12 months the right standard time-to-conceive threshold, and is a 6-month
  earlier threshold with an older partner appropriate at all?
- Which partner age band should count as "older" (draft: `35_plus`)?
- Is BMI >= 25.0 the right review threshold, or should the flag use a higher
  cut-off or a range?

## Flag scope and routes (`rules/flags.v0.1.yaml`)

- Should STI history route to primary care (draft) or to andrology/urology?
- Should anabolic steroid or testosterone product use route to andrology
  (draft) or start in primary care?
- Is a single chronic-conditions flag routing to primary care correct, or
  should specific conditions be listed?
- Should sexual-function changes route to andrology (draft) or to primary
  care first?
- Should family history route to andrology (draft), and is it correctly
  non-key (optional, never blocks self-care)?
- Is prior abnormal hormone result correctly non-key, and which result values
  should the intake offer?
- Are diabetes, hypertension and high cholesterol correctly flagged as
  modifiable, and is primary care the right route for each?
- Tobacco flags former or current use; alcohol flags occasional or regular
  use. Are these groupings and the draft option values
  (never/former/current, never/occasional/regular) acceptable?
- Is a boolean occupational heat/chemical exposure item sufficient, or should
  it capture frequency or type?

## Red flags (`rules/redflags.v0.1.yaml`)

- Is any testicular swelling urgent (draft), or only rapidly increasing
  swelling? Should the item distinguish the two?
- Is the draft red-flag list (sudden severe pain, new lump, rapid swelling,
  fever with pain, blood in semen) complete and correctly urgent?

## Triage behaviour

- Is it correct that unassessed red-flag symptoms force a provisional route
  rather than plain self-care?
- Are the key/non-key designations right: only family history, prior hormone
  result and partner age band are non-key?
- Is the route precedence (urgent, andrology/urology, fertility services,
  primary care, provisional, self-care) correct?

## Frontend intake mapping (`lib/intake.ts`, `lib/mapping.ts`)

- The UI asks combined screening questions: one for torsion/injury/surgery
  (mapped to `testicular_torsion` on "yes") and one for erection/desire
  changes (mapped to `low_desire_or_sexual_function_change` on "yes").
  Should these stay combined or split into separate questions?
- "Not currently trying" derives `months_trying = 0`, and duration bands
  map to representative months (under 6 -> 3, 6-12 -> 9, over 12 -> 18).
  Are these derivations acceptable for the time-to-conceive flag?
- A UI "yes" on tobacco maps to `current` (never/former/current), on
  alcohol to `regular` (never/occasional/regular), on steroids or other
  substances to `current`. Should the UI offer the middle options instead?
- The UI covers every key flag and red flag but never asks partner age,
  prior hormone result or family history (all non-key by design). Is that
  coverage the right trade-off for a short intake?

## Citation corpus (`app/content/excerpts.*.json`)

- The seed excerpts reuse draft snippet texts and are not verbatim
  guideline quotes. Which verbatim excerpts (document + section + exact
  wording) should replace them, one per flag?
- Until replacement, is it acceptable for explanations to cite these
  draft pointers, given every entry is flagged
  `requires_clinical_validation`?
