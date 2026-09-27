# Tutorial display and examples

The previous tutorial unconditionally showed the target move's after-placement
distances before the user placed it. The deployment overlay now always renders
the actual board state's distances, including after hovering. After a move, a
separate before/after table compares placement distances at the original ball
position; the board follows the ball's actual position. Escaped balls have no
distance overlay. Each completed lesson can be replayed.

The distance lesson now starts at the center with four distances of 8. A single
wall blocks up; right/down/left remain tied at 8 and the ball stays still. The
movement lesson replaces long boundary walls with a single floating post near
the top/right corner: up/right are 3 and down/left are 4. Closing the upper wall
makes right uniquely shortest. The ball moves from (3,13) to (3,14), zero-based,
and its new board distances are 3/2/3/4. The before/after table remains
3/3/4/4 to infinity/3/4/4. Text defines distance to any exit, excluding the first
step from the ball to the adjacent cell, and explains 0, infinity and tie rules.

Other lessons retain their focused demonstrations of floating posts, walls,
replacement, opponent-colored boundary victory, and enclosure victory.

Validation: TypeScript and Vite builds; all 35 Vitest tests; Ruff build-script
check; all seven lessons completed in Chromium; hover invariance, reset/replay,
current-origin distances, boundary overlay removal and enclosure values checked.
390 × 844 mobile layout had no horizontal overflow and was visually inspected.
The seven-step progress list now uses seven columns. Browser artifacts and build
are under `E:/Escape/_AI/deploy/champion-20260927/website-tutorial-v1`.
All changes are overlays in Escape_AI; the Escape repository remains read-only.

Published frontend: `47af843336d93a8124886518b62253162958f3ca`, release directory
`/var/www/linkukai/escape/releases/champion-47af843`. The public www site passed
the same seven-lesson browser walkthrough, replay and mobile checks after cutover.
Upload size was 552,534 bytes; extracted files total 1,877,114 bytes. The archive
was removed after validation. Previous release `champion-77574d1` is retained for
atomic symlink rollback; no inference service or Nginx change was necessary.
