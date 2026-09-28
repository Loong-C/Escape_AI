# Tutorial simplification and total distance hints

Removed the floating/anchored icon legend, all tutorial tables and board-display
explanations. Applied the requested instructions and removed the extra movement,
winner and AI-difficulty clauses. Tutorial success text, homepage and rule dialog
now use total first-direction escape length, including the first step. The shared
board renderer adds one to internal neighbor distances for both visible and
accessible output; infinity and minimum highlighting retain their meaning.
Rules simulation and champion inference are unchanged.

The boundary lesson now starts at the top-right cell (0,16). Up and right both
have total length 1. An unrelated placement leaves the ball still. Placing the
target at (0,17), next to the existing white post (0,16), closes the upper exit;
right becomes uniquely shortest and the ball escapes for white's victory.

Validation before publishing: all 37 Vitest tests, TypeScript and production Vite
builds, Ruff and whitespace checks. Tests cover boundary causality, total-distance
rendering, infinity and highlighting. Chromium at 390 × 844 completed all seven
lessons and checked unchanged pre-move numbers on hover, removed content, no
horizontal overflow, local-match center values 9/9/9/9 and updated rule text.
The boundary screenshot was visually inspected. Artifacts are under
`E:/Escape/_AI/deploy/champion-20260928/website-tutorial-v2`.
