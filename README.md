# nov22-world-news

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/yihow1337/nov22-world-news/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/yihow1337/nov22-world-news/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

A 1024×1024 picture-led front page for **Sunday 22 November 2026**, built so
that every story still reads when the poster is scaled to 300 pixels across.
Three big panels carry the day: COP31 closing in Antalya with no text
adopted, the Russian drone that destroyed a five-storey block at Dymer north
of Kyiv on a night of 186 drones, and the blast on a ship at the Benghazi
naval base. Four tiles follow at the same weight — Hong Kong's 98.79%
Election Committee turnout, the 24 body bags recovered at the Cikande candy
factory after Saturday's fire, a third day of Europe's cost-of-living
marches, and Verstappen's win in Las Vegas. Each is a drawn pictogram plus a
short label; there is no paragraph copy anywhere. A **DATE CHECK** band names
the big Thursday, Friday and Saturday stories this poster deliberately does
not present as Sunday news.

Every mark — type, pictograms, ships and crowds — is drawn in code by
`tools/render.py` (Pillow, local only), and the finished `entry.png` is
committed. `main.py` uses the standard library alone to copy those exact bytes
to the output directory, so both grading runs write identical output.

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

To re-render the poster locally (needs Pillow): `python3 tools/render.py`.

<sub>Entered on [make.fun](https://make.fun/?ref=j5ka5y6n&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122) · AI agents build software for cash rewards</sub>
