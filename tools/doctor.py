"""
依存の確認．何が無いと，どの機能が外れるかを出す（標準ライブラリだけで動く）．

使い方:
  python3 doctor.py                 … 表を出す
  python3 doctor.py --chrome [資料のフォルダ]    … Chrome の場所（無ければ空）．build.sh が使う
"""
import os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def deck_cfg(deck):
    if not deck: return {}
    try:
        import config
        return config.resolve(deck)
    except SystemExit:
        return {}

def chrome(cfg=None):
    if os.environ.get('CHROME') == 'none': return ''          # 確認用: Chrome が無いときの動きを試す
    cands = [(cfg or {}).get('chrome'), os.environ.get('CHROME'),
             '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             '/Applications/Chromium.app/Contents/MacOS/Chromium',
             'C:/Program Files/Google/Chrome/Application/chrome.exe']
    cands += [shutil.which(n) for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome')]
    for c in cands:
        if c and Path(os.path.expanduser(c)).is_file(): return os.path.expanduser(c)
    return ''

def table():
    rows = [
        ('uv', shutil.which('uv'), '必須（無いと何も作れない）', 'https://docs.astral.sh/uv/'),
        ('Google Chrome / Chromium', chrome(), 'PDF とパワポ（無いと HTML だけ）', 'Chrome を入れるか，設定の "chrome" に場所を書く'),
        ('LaTeX（latex，dvisvgm）', shutil.which('latex') and shutil.which('dvisvgm'), '文字で組めない式の絵（無いと HTML では MathJax で表示）', 'TeX Live / MacTeX'),
        ('pandoc', shutil.which('pandoc'), 'パワポの式を PowerPoint の数式にする（無いと画像）', 'https://pandoc.org/'),
        ('xelatex，pdftocairo', shutil.which('xelatex') and shutil.which('pdftocairo'), '日本語を含む式の絵', 'TeX Live / poppler'),
        ('Microsoft PowerPoint（Mac）', Path('/Applications/Microsoft PowerPoint.app').exists() or None, '確認用: PowerPoint に PDF を書き出させる（ppt2pdf.scpt）', '無くても作れる'),
    ]
    print('| もの | 状態 | 使い道 | 無いとき |')
    print('|---|---|---|---|')
    for name, ok, use, how in rows:
        print(f'| {name} | {"ある" if ok else "無い"} | {use} | {"" if ok else how} |')
    try:
        import config
        ps = config.list_profiles()
        print('\nプロファイル:', ', '.join(f"{p['name']}（{p['_source']}）" for p in ps) or '無し')
    except SystemExit as e:
        print('\nプロファイルを読めない:', e)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--chrome': print(chrome(deck_cfg(sys.argv[2] if len(sys.argv) > 2 else None)))
    else: table()
