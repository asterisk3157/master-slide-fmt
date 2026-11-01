"""
設定とプロファイル．

  設定は 3 段で重ねる: 道具の既定値（DEFAULTS） → プロファイルの "config" → 資料のフォルダの slides.config.json
  "auto" の項目は，マスターから読んだ値を使う（theme_css.py が解決する）

プロファイルは「マスター + 設定 + 言い回しの決まり」を 1 つのフォルダにまとめたもの．探す場所（上ほど優先）:
  1. 環境変数 MASTER_SLIDE_PROFILES（: 区切りで複数）
  2. ~/.config/master-slide-fmt/profiles/   … おすすめ．どのリポジトリの外にもあるので，誤って公開されない
  3. <スキル>/profiles/                      … gitignore で公開から外れる
  4. <スキル>/examples/                      … 公開の見本（架空の名前だけ）
"""
import copy, fnmatch, json, os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DECK_CONFIG = 'slides.config.json'
MARKER = '.slide-profile'

DEFAULTS = {
    "profile": None,
    "master": None,
    "layouts": {"content": "auto", "cover": "auto"},
    "content_box": "auto",
    "fonts": {"latin": "auto", "ea": "auto",
              "fallback": ["Hiragino Kaku Gothic ProN", "Hiragino Sans", "Yu Gothic", "Meiryo", "Noto Sans CJK JP", "sans-serif"]},
    "title": {"size": "auto", "color": "auto", "bold": "auto"},
    "sizes_pt": {"lead": "auto", "body": "auto", "sub": "auto", "small": 12, "strict": True},
    "bullets": {"lead": "auto", "body": "auto", "sub": "auto"},
    "colors": {"text": "auto", "good": "0070C0", "bad": "FF0000", "table_head": "D9D9D9", "table_border": "000000",
               "box_border": "000000", "page_bg": "2F3B52"},
    "footer": {"text": "auto", "date": "field", "date_format": "en-long", "number": True},
    "math": {"font": "sans", "preamble": "", "pptx": "office", "plugin": ""},
    "chrome": "",
    "style_guide": None,
}


def merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = merge(out[k], v)
        else: out[k] = copy.deepcopy(v)
    return out


# ------------------------------------------------------------------ プロファイル
def profile_dirs():
    dirs = [Path(p).expanduser() for p in os.environ.get('MASTER_SLIDE_PROFILES', '').split(':') if p]
    dirs += [Path('~/.config/master-slide-fmt/profiles').expanduser(), SKILL / 'profiles', SKILL / 'examples']
    return dirs

def source_of(d):
    if d == SKILL / 'examples': return 'example'
    if d == SKILL / 'profiles': return 'skill'
    return 'user'

def list_profiles():
    seen, out = set(), []
    for d in profile_dirs():
        if not d.is_dir(): continue
        for p in sorted(d.iterdir()):
            f = p / 'profile.json'
            if not f.is_file(): continue
            try: data = json.loads(f.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e: raise SystemExit(f'{f} が JSON として読めない: {e}')
            name = data.get('name', p.name)
            if name in seen: continue                      # 上の場所にある同じ名前が優先
            seen.add(name); data['_dir'] = str(p); data['_source'] = source_of(d); data.setdefault('name', name)
            out.append(data)
    return out

def load_profile(name):
    for p in list_profiles():
        if p['name'] == name: return p
    names = ', '.join(p['name'] for p in list_profiles()) or '（無し）'
    raise SystemExit(f'プロファイル「{name}」が見つからない．あるもの: {names}')

def _match(pattern, path):
    pat = str(Path(pattern).expanduser())
    path = str(path)
    if pat.endswith('/**'): return path == pat[:-3] or path.startswith(pat[:-3] + '/')
    return fnmatch.fnmatch(path, pat)

def which(directory):
    """(プロファイル名, 理由) か (None, 候補の一覧)．順: 資料の設定 → .slide-profile → match.paths"""
    d = Path(directory).expanduser().resolve()
    cfg = d / DECK_CONFIG
    if cfg.is_file():
        name = json.loads(cfg.read_text(encoding='utf-8')).get('profile')
        if name: return name, f'{cfg} に "profile": "{name}" とある'
    for up in [d, *d.parents]:
        m = up / MARKER
        if m.is_file():
            name = m.read_text(encoding='utf-8').strip().splitlines()[0].strip()
            return name, f'{m} にある'
    best = None
    for p in list_profiles():
        for pat in (p.get('match') or {}).get('paths', []):
            if _match(pat, d):
                score = len(str(Path(pat).expanduser()))
                if best is None or score > best[0]: best = (score, p['name'], pat)
    if best: return best[1], f'ディレクトリが {best[2]} に当てはまる'
    return None, [{k: p.get(k) for k in ('name', 'description', 'match', '_source')} for p in list_profiles()]


# ------------------------------------------------------------------ 資料の設定を解決する
def resolve(deck_dir, profile=None):
    """資料のフォルダの設定を，プロファイルと既定値に重ねて返す．master と style_guide は絶対パスにする"""
    d = Path(deck_dir).resolve()
    deck = {}
    f = d / DECK_CONFIG
    if f.is_file():
        try: deck = json.loads(f.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e: raise SystemExit(f'{f} が JSON として読めない: {e}')
    name = profile or deck.get('profile')
    reason = f'{f} の指定' if name else None
    if not name:
        name, reason = which(d)
        if not name:
            raise SystemExit('プロファイルが決まらない．slides.config.json に "profile" を書くか，'
                             '`profile.py which` / `profile.py list` で選ぶ（新しく作るなら `profile.py new`）')
    prof = load_profile(name)
    cfg = merge(merge(DEFAULTS, prof.get('config', {})), {k: v for k, v in deck.items() if k != 'profile'})
    cfg['profile'] = name
    pdir = Path(prof['_dir'])
    master = deck.get('master') and (d / deck['master']) or (pdir / prof.get('master', 'master.pptx'))
    cfg['master'] = str(Path(master).resolve())
    sg = prof.get('style_guide')
    cfg['style_guide'] = str((pdir / sg).resolve()) if sg else None
    if cfg['math'].get('plugin'):                          # 式のプラグインは，プロファイルのフォルダからの相対でもよい
        cfg['math']['plugin'] = str((pdir / Path(cfg['math']['plugin']).expanduser()).resolve())
    cfg['_profile'] = {'name': name, 'dir': str(pdir), 'source': prof['_source'], 'reason': reason, 'description': prof.get('description', '')}
    if not Path(cfg['master']).is_file(): raise SystemExit(f'マスターが見つからない: {cfg["master"]}')
    return cfg
