# On This Day calendar

A free, self-hosted calendar feed with history for every day of the year: a handful of events, births and
deaths from Wikipedia's "On this day" pages, with sensitive topics filtered out. Each date is one all-day
entry that repeats every year, so the feed keeps working even if you never rebuild it.

- **Costs nothing:** GitHub Actions builds it and GitHub Pages hosts it.
- **Curated:** Wikipedia editors' "selected anniversaries" come first, then the most famous other items,
  measured by how many Wikipedia language editions cover them.
- **Filtered:** history, not true crime (see [How the filter works](#how-the-filter-works)).

An entry looks like this (one per day; the title is the day's top event):

```
📜 1990 · German reunification: The German Democratic Republic joins the Federal Republic…

EVENTS
• 1932 – Iraq gains independence from the United Kingdom.
  https://en.wikipedia.org/wiki/Kingdom_of_Iraq
• 1990 – German reunification: The German Democratic Republic joins the Federal Republic of Germany.
  https://en.wikipedia.org/wiki/German_reunification
• 1995 – O. J. Simpson is acquitted of the murders of Nicole Brown Simpson and Ronald Goldman.
  …
BORN
• 1941 – Chubby Checker, American singer-songwriter
DIED
• 1226 – Francis of Assisi, Italian saint, founded the Franciscan Order (b. 1181)
```

## Setup (about 10 minutes, plus a 15–30 minute first build)

1. **Create a repository.** Sign in at github.com → **New repository** → name it e.g. `on-this-day`
   → choose **Public** (free GitHub Pages needs a public repository) → **Create repository**.

2. **Upload these files.** From a terminal in this folder:

   ```sh
   git init -b main
   git add .
   git commit -m "On This Day calendar"
   git remote add origin https://github.com/YOUR-USERNAME/on-this-day.git
   git push -u origin main
   ```

   Or use the web page's **uploading an existing file** link and drag in the *contents* of this folder.
   Include the hidden `.github` folder (on a Mac, press Cmd+Shift+. in Finder to show it), or the
   automatic builds won't exist.

3. **Turn on Pages.** In the repository: **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.

4. **Run the first build.** **Actions** tab → **Build calendar** → **Run workflow**. (Pushing the files
   may already have started one; that's fine.) The first run downloads all 366 days from Wikipedia and
   takes roughly 15–30 minutes. If it stopped at the deploy step because Pages wasn't on yet, click
   **Re-run jobs**; the data is cached, so it finishes in about a minute.

5. **Subscribe.** Open `https://YOUR-USERNAME.github.io/on-this-day/`. The page has subscribe buttons,
   the feed URL, and a preview of today's entry.

## Subscribing

The feed URL is `https://YOUR-USERNAME.github.io/on-this-day/on-this-day.ics`.

- **Google Calendar:** on a computer, **Other calendars → + → From URL** → paste the feed URL. (The
  mobile app can't add calendars by URL; once added on the web it shows up on your phone too.) Google
  refreshes subscriptions on its own schedule, roughly once a day.
- **Apple Calendar:** tap or click the *webcal* button on the site. Or, on a Mac, **File → New Calendar
  Subscription**; on iPhone, **Settings → Apps → Calendar → Calendar Accounts → Add Account → Other →
  Add Subscribed Calendar**.
- **Outlook.com / Outlook on the web:** **Add calendar → Subscribe from web** → paste the feed URL.

Entries are marked as "free" time, so they never block meetings.

## Adjusting it

Everything is in two small files. Edit them on github.com (pencil icon) or locally, then commit. The
calendar rebuilds automatically within a few minutes (calendar apps pick up changes on their next refresh).

- **`config.toml`**: items per day, title emoji, links, how strict the filter is.
- **`overrides.toml`**: fix individual mistakes by Wikipedia article title (always include / always
  exclude), or exclude by phrase.

After every build, `https://YOUR-USERNAME.github.io/on-this-day/report.html` lists:
- every item the filter removed that would otherwise have appeared, with the reason, and
- every sensitive item it allowed (famous trials, disasters, war atrocities…).

Skim it once after the first build; that's the fastest way to see whether the rules suit you.

**Fresh picks each year:** Wikipedia's editors update their selections over time. Click **Run workflow**
once a year (e.g. in January) to rebuild with the latest data. If you never do, the calendar keeps
repeating the current entries, which is fine too.

## How the filter works

Each item is judged from its text plus the short descriptions of the Wikipedia articles it links to
(e.g. "American serial killer", "1999 school shooting in Colorado"). Rules live in `otd/sensitive.py`.

| Outcome | What | Examples |
|---|---|---|
| Always removed | sexual crimes; violence against children; anything about a serial killer, mass murderer or similar; torture, lynching and other graphic violence; massacres and mass shootings outside a war; ordinary murders; suicides | Columbine, Ted Bundy's execution, Jonestown, the St. Valentine's Day Massacre |
| Kept | wars, battles, revolutions, coups and anything in a war context; assassinations of political figures; state forces firing on protesters | D-Day, Hiroshima, JFK, Franz Ferdinand, Sharpeville |
| Kept by default (`war_atrocities`) | massacres and genocide that are part of a war | My Lai, the Holocaust, the Boston Massacre |
| Kept only if famous (`famous_threshold`) | crimes that aren't gruesome and court cases, disasters and accidents, criminals in the births/deaths lists | O. J. Simpson's 1995 verdict (yes), his 2008 robbery case (no), the Titanic, Watergate, Al Capone |
| Kept only if very famous (`terrorism_threshold`) | terrorist attacks outside a war | 9/11 (yes), most others (no) |

Fame is measured on the event's own article when there is one, so a minor episode isn't let in just
because a famous person was involved. When unsure, the rules lean towards removing. If an entry
you'd want is missing (e.g. John Lennon's murder; his death still appears under "Died"), add it to
`overrides.toml`.

To test a line yourself:

```sh
python -m otd check "Columbine High School massacre: two students kill 13 people."
python -m otd check "Ted Bundy, American serial killer (d. 1989)" --person
```

## Running it on your own computer (optional)

Requires Python 3.11 or newer; no extra packages.

```sh
# put your email in config.toml → [fetch] contact = "you@example.com"  (Wikimedia asks for it)
python -m otd all                       # downloads into cache/, builds site/
python -m otd build --days 07-20,10-03  # rebuild just a few dates from the cache, for quick checks
python -m unittest discover -s tests -t .
```

Then import `site/on-this-day.ics` into any calendar app, or open `site/report.html`.

## Troubleshooting

- **New changes don't show in Google Calendar.** Google re-reads subscribed feeds roughly once a day, and
  you can't force it. Apple Calendar lets you choose the refresh interval.
- **The build failed while fetching.** Wikipedia occasionally rate-limits or is slow, and each run stops
  downloading after 100 minutes. Click **Re-run jobs**: everything already downloaded is cached and the
  run continues where it stopped.
- **"Fame scores were not available" in the report.** The Wikidata service was down. Re-run the workflow;
  until then the filter errs on the side of removing items.

## Credits

Content: Wikipedia's "On this day" pages, via the Wikimedia REST API, under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Every calendar entry carries that
attribution and a link to the date's Wikipedia page. Fame scores: Wikidata (CC0).
