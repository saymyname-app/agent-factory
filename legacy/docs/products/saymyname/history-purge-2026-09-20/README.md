# History purge of 2026-09-20 — old-to-new commit SHAs

On 2026-09-20 the git history of `Say-my-name-back` and `Say-my-name-front` was
rewritten (see `DECISIONS.md`, 2026-09-20) and force-pushed. Every commit from the
first changed commit onwards has a new SHA.

- `commit-map-back.txt`, `commit-map-front.txt`: one `old new` pair per line
  (git-filter-repo `commit-map`; a `new` of all zeros means the commit became empty
  and was dropped). They contain only SHAs.
- First changed commits: back `ec69d4126dab0d23eff35c1b618b7845434d0e07`, front
  `fec807431d271b0e12a69ca2c73c845ea7dfe770`.
- Use these maps to translate any SHA cited before 2026-09-20 in a bead, a
  delivery proof, a PR body or a note. Pull-request numbers may stop resolving if
  GitHub Support dereferences the pull requests.

Never restore an old `.git`, an old remote ref or an old branch, and never push
from a clone made before the purge: that history contains the photos.
