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
