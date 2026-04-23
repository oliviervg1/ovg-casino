import csv

with open('/home/admin_/ces/data/processed/games_catalog.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    games = list(reader)

themes = {}
for g in games:
    theme = g['theme']
    if theme not in themes:
        themes[theme] = []
    themes[theme].append(g)

out = []
out.append("# OVG Casino Games Catalog\n")
out.append("The OVG Casino offers three premier game types, each available in 8 distinct, highly detailed themes. This provides a total of 24 unique gaming experiences.\n")
out.append("## Game Types\n")
out.append("### 1. Roulette\nA classic casino thrill. Players gather around a themed roulette wheel, placing bets and guessing where the ball will land.\n")
out.append("### 2. Slots\nFast-paced, visually exciting, and easy to play. Players spin the themed digital reels hoping to align symbols in a winning combination.\n")
out.append("### 3. Bingo\nA community favorite built on anticipation. Players receive themed cards and mark off called numbers to try and complete a winning pattern first.\n")
out.append("---\n\n## Themes & Variations\n")

for theme, theme_games in themes.items():
    out.append(f"### Theme: {theme.capitalize()}")
    for g in theme_games:
        sym_text = f" Symbols include {g['symbols']}." if g['symbols'] else ""
        out.append(f"*   **{g['title']}** ({g['game_type']}): {g['detailed_description']}.{sym_text} *({g['short_description']})*")
    out.append("\n")

with open('/home/admin_/ces/data/raw/games.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

