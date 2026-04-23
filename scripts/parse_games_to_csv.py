import re
import urllib.request
import csv

response = urllib.request.urlopen('https://casino.oliviervg.com/assets/index-iiihX4Vt.js')
html = response.read().decode('utf-8')

match = re.search(r'eU=\{(.*?)\}', html)
if match:
    content = match.group(1)
    pairs = re.findall(r'([a-zA-Z0-9_]+):`([^`]+)`', content)
    data = dict(pairs)
    
    themes = ['sweets', 'egypt', 'space', 'ocean', 'jungle', 'ninja', 'vampire', 'west']
    
    with open('/home/admin_/ces/games_catalog.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'title', 'game_type', 'theme', 'description', 'symbols'])
        
        for idx, theme in enumerate(themes):
            r_full = data.get(f"bg_roulette_{theme}", "")
            s_full = data.get(f"bg_slots_{theme}", "")
            b_full = data.get(f"bg_bingo_{theme}", "")
            
            raw_symbols = [data.get(f"{theme}_{i}", "") for i in range(1,5) if f"{theme}_{i}" in data]
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

            writer.writerow([f"r_{theme}", f"{theme.capitalize()} Roulette", "Roulette", theme.capitalize(), clean_bg(r_full), ""])
            writer.writerow([f"s_{theme}", f"{theme.capitalize()} Slots", "Slots", theme.capitalize(), clean_bg(s_full), sym_str])
            writer.writerow([f"b_{theme}", f"{theme.capitalize()} Bingo", "Bingo", theme.capitalize(), clean_bg(b_full), ""])
