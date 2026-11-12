# "Would you like it?" — personal verdict on shoe pages

Agreed 2026-11-12. Every decision below came from the user interview; no open questions remain.

## What the user sees

On `/catalog/[id]`, in the top section **under the price, above Save and the buy button**:

```
Would you like it?
● Great fit for you
✓ 9.1 traction — your top priority
✓ Standard fit matches your feet
✓ Built for guards
! Narrow-fitting for wide feet
? No cushion rating yet
```

- **Verdict** — one of three labels, no score or rank number shown:
  - **Great fit for you** — shoe is in the user's top 5% of the catalog (~33 of 660)
  - **Worth a look** — top 30% (~next 165)
  - **Probably not for you** — everything else
- **Reasons** (✓) — up to 3 matches with the user's answers, most relevant first.
- **Caveats** (!) — up to 2 places it works against their answers.
- **Unknowns** (?) — a neutral line when the shoe has no data for something they ranked as a priority.
- Deterministic, no LLM call, no AI paragraph.

### Other states

| Visitor | Box shows |
|---|---|
| Logged out | Teaser: "See if this shoe fits your game" → Sign in |
| Logged in, no saved preferences | Teaser → Take the quiz |
| Logged in, preferences saved | The verdict |

Catalog grid cards get **no** badges in this version (shoe page only).

## How the verdict is computed

- **Same scoring as the recommender** (`app/services/ranking.py` boosts on top of retrieval similarity), so a shoe the quiz recommends always reads "Great fit".
- The user's saved answers are scored against **every shoe in the catalog**; the verdict comes from where this shoe's rank falls (top 5% / top 30%).
- **Price is ignored entirely**: no budget filter, no over-budget caveat, and no unpriced penalty, so verdicts judge fit to the player only. The page already shows the price.
- The saved free-text note (e.g. "recovering from an ankle sprain") feeds the similarity half, just as it does in the quiz.
- Reasons, caveats and unknowns come from the same per-boost values the ranker computes; a caveat is a boost that counted against the shoe (e.g. width mismatch, position mismatch, low outdoor score for an outdoor player).

## Saving preferences

- New per-user preferences record holding the quiz answers: position/playstyle, court, priorities (≤2), foot width, preferred brand, preferred cut, budget, and the free-text note. Plus the profile embedding, refreshed whenever answers change, so page views need no embedding API call.
- **Saved automatically** when a signed-in user finishes the quiz; the latest quiz wins.
- **Carry-over**: if someone takes the quiz logged out and then signs in, those answers are saved when they have no saved preferences yet.
- **Profile page**: an editable form showing every saved answer, including the free-text note, which they can edit or clear. Saving the form updates the embedding.

## Out of scope for this version

- Verdict badges on catalog cards (same backend can serve them later)
- AI-written explanation
- Showing a rank number or match %
