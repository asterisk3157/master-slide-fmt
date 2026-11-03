"""
資料のフォルダを作る: <名前>.src.html（ひな形）・slides.config.json（使うプロファイル）・build.sh・figs/

使い方: python3 new_deck.py <資料のフォルダ> [--profile 名前] [--name 資料の名前] [--title タイトル]
  --profile が無ければ，フォルダの場所から選ぶ（profile.py which と同じ）．決まらなければ候補を出して止まる
"""
import argparse, datetime, json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config

ap = argparse.ArgumentParser()
ap.add_argument('dir'); ap.add_argument('--profile'); ap.add_argument('--name'); ap.add_argument('--title')
a = ap.parse_args()
d = Path(a.dir).expanduser().resolve()
name = a.profile
why = '--profile の指定'
if not name:
    probe = d if d.exists() else d.parent
    name, why = config.which(probe)
    if not name:
        print(json.dumps({'profile': None, 'candidates': why}, ensure_ascii=False, indent=1))
        sys.exit('プロファイルが決まらない．--profile で指定する（一覧: profile.py list）')
prof = config.load_profile(name)
deck = a.name or d.name
src = d / f'{deck}.src.html'
if src.exists(): sys.exit(f'もうある: {src}')
d.mkdir(parents=True, exist_ok=True); (d / 'figs').mkdir(exist_ok=True)
today = datetime.date.today()
nd = prof.get('new_deck', {})
title = a.title or nd.get('cover_title', '（タイトル）')
sub = nd.get('cover_sub', '{date}').replace('{date}', f'{today.year}/{today.month:02d}/{today.day:02d}')
s = (HERE.parent / 'template' / 'slides.src.html').read_text(encoding='utf-8')
s = s.replace('{{TITLE}}', title).replace('{{COVER_TITLE}}', title).replace('{{COVER_SUB}}', sub).replace('{{DATE}}', today.isoformat())
src.write_text(s, encoding='utf-8')
cfg = d / config.DECK_CONFIG
if not cfg.exists(): cfg.write_text(json.dumps({'profile': name}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
shutil.copy2(HERE.parent / 'template' / 'build.sh', d / 'build.sh')
ph = d / 'figs' / 'placeholder.svg'                   # まだ無い図の代わり（本物の図ができたら差し替える）
if not ph.exists():
    ph.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">'
                  '<rect x="4" y="4" width="632" height="352" fill="#fafafa" stroke="#999" stroke-width="4" stroke-dasharray="14 10"/>'
                  '<text x="320" y="190" font-size="32" text-anchor="middle" fill="#777" font-family="sans-serif">（仮）図</text></svg>', encoding='utf-8')
gi = d / '.gitignore'
if not gi.exists(): gi.write_text('.build/\n.review/\n', encoding='utf-8')
print(f'作った: {src}\n  プロファイル: {name}（{why}）\n  次: 図を figs/ に置き，{deck}.src.html を書いて ./build.sh')
