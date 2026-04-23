import re
import urllib.request
import csv
import json

response = urllib.request.urlopen('https://casino.oliviervg.com/assets/index-iiihX4Vt.js')
html = response.read().decode('utf-8')

# Extract eU (backgrounds and symbols)
match_eU = re.search(r'eU=\{(.*?)\}', html)
bg_data = {}
if match_eU:
    content = match_eU.group(1)
    pairs = re.findall(r'([a-zA-Z0-9_]+):`([^`]+)`', content)
    bg_data = dict(pairs)

# Extract fU (game metadata)
match_fU = re.search(r'fU=\[(.*?)\]', html)
games = []
if match_fU:
    content = match_fU.group(1)
    # the format is {id:`...`,name:`...`,type:`...`,theme:`...`,description:`...`}
    # We can parse it using regex
    items = re.findall(r'\{id:`([^`]+)`,name:`([^`]+)`,type:`([^`]+)`,theme:`([^`]+)`,description:`([^`]+)`\}', content)
    for item in items:
        games.append({
            'id': item[0],
            'name': item[1],
            'type': item[2],
            'theme': item[3],
            'short_desc': item[4]
        })

with open('/home/admin_/ces/data/processed/games_catalog.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'title', 'game_type', 'theme', 'short_description', 'detailed_description', 'symbols'])
    
    for g in games:
        theme = g['theme']
        gtype = g['type']
        
        # bg key looks like bg_roulette_sweets
        bg_key = f"bg_{gtype}_{theme}"
        bg_full = bg_data.get(bg_key, "")
        
        raw_symbols = [bg_data.get(f"{theme}_{i}", "") for i in range(1,5) if f"{theme}_{i}" in bg_data]
        symbols = []
        for s in raw_symbols:
            s = s.replace("A vibrant 2D game asset of a ", "").replace("A vibrant 2D game asset of an ", "").replace("A vibrant 2D game asset of the ", "the ")
            s = s.split(',')[0].strip()
            symbols.append(s)
        sym_str = ', '.join(symbols)
        
        def clean_bg(text):
            if "temple. " in text: return text.split("temple. ")[-1].split(". Detailed")[0].strip().capitalize()
            elif "casino. " in text: return text.split("casino. ")[-1].split(". Detailed")[0].strip().capitalize()
            return text

        detailed_desc = clean_bg(bg_full)
        
        writer.writerow([
            g['id'],
            g['name'],
            gtype.capitalize(),
            theme.capitalize(),
            g['short_desc'],
            detailed_desc,
            sym_str if gtype == 'slots' else ""
        ])

print("CSV generated successfully with", len(games), "games.")
