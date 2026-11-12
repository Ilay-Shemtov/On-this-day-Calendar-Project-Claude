# Test data

`cache/` has the same layout the real build uses (`cache/feed/MM-DD.json`, `cache/sitelinks.json`).

- `12-01.json`: events, births and deaths from a real snapshot of
  [December 1](https://en.wikipedia.org/wiki/December_1) (Wikimedia's own wikifeeds test fixture;
  text CC BY-SA 4.0), with short descriptions added by hand for the main articles.
- The other dates are hand-written in Wikipedia's style to cover the filter's key cases
  (Columbine, the O. J. Simpson verdict and robbery case, 9/11, Ted Bundy, a leap day).
- Fame numbers (sitelinks) and Wikidata IDs are estimates/placeholders, not real values.
