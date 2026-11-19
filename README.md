# Awwal (أوّل) — frontend prototype

A private first step for men's reproductive health. Prototype with synthetic data. Not a diagnosis.

## Run

```bash
npm install
npm run dev      # http://localhost:3000
```

English only, built as a desktop web app. Pages use a split layout: the heading and main action sit on the left and stay in place, and the content is on the right. Narrow windows stack the two columns. Arabic strings are still in `lib/strings.ts` and `lib/intake.ts` but aren't shown; the language is fixed in `lib/store.tsx`.

## Screens

| Route | Screen |
| --- | --- |
| `/` | Welcome |
| `/consent` | Four separate permissions, none pre-ticked |
| `/intake` | Seven short topics; every question has "Not sure" and "Rather not say"; blanks become `skipped` |
| `/results` | Flags in three states (filled, dashed, hollow marker plus text) and the workflow trace sheet |
| `/next` | One route on the care-path line; urgent gets a static full-screen message |
| `/booking` | Video call, blood test or sample; language and clinician filters; phone asked only here |
| `/status` | Referral stages, simulated reminders, outcome; demo button stands in for the navigator |
| `/privacy` | Permissions, shares with expiry and revoke, activity log, download, delete |
| `/clinician` | Review queue, brief, change route, sign off |

The "Hide" button in the header covers the app with a neutral "Notes" screen. Click "Notes" or press Esc to return.

## Demo paths

- **Urgent:** answer Yes to any question in "Right now". You skip results and land on the static urgent screen.
- **Incomplete:** leave "Told you have a varicocele" or "Semen analysis" blank. You get "A few answers are missing" with the list.
- **Specialist through sign-off:** answer Yes to testicular surgery, book, then open the clinician view from the status page and sign off. The status moves to Confirmed and then Booked.

## For Person A (engine/API)

`lib/types.ts` is the contract. `lib/engine.ts` is a **mock** that returns the same `Assessment` shape using three-valued logic (true / false / unknown → `NOT_ASSESSABLE`). Swap `assess()` and the store actions in `lib/store.tsx` for API calls when endpoints are live.

## Design notes

- Tokens live in `app/globals.css`. Saffron `#C8902E` is reserved for the user's path (progress bar, route line, status line) and is used nowhere else.
- Type: Readex Pro, light weight for headings.
- The care path on the next-step screen is horizontal, from self-care to urgent, and the line draws to the user's stop.
- Motion: one entrance per screen, the route line drawing to the user's stop, and responses to taps (chips, toggles, expanding rows, sheets). Reduced-motion settings are respected.
- All clinical content needs clinician review.
