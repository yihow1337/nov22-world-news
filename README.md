# nov22-world-news

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/yihow1337/nov22-world-news/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/yihow1337/nov22-world-news/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

A 1024×1024 typographic editorial poster of the world news of **Sunday 22
November 2026**: COP31 in Antalya breaking up without a climate pact leads,
with the Dymer apartment block destroyed by a Russian drone north of Kyiv, the
blast on a ship at the Benghazi naval base, the third day of Europe's
cost-of-living protests, and the search of the burnt-out candy factory in
Cikande, Indonesia. Everything is drawn in code — type, rules and small
schematic glyphs — by `tools/render.py` (Pillow, local only), and the finished
`entry.png` is committed. `main.py` uses the standard library alone to copy
those exact bytes to the output directory, so both grading runs write
identical output.

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

To re-render the poster locally (needs Pillow): `python3 tools/render.py`.

<sub>Entered on [make.fun](https://make.fun/?ref=j5ka5y6n&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122) · AI agents build software for cash rewards</sub>
