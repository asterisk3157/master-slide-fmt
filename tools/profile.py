"""
プロファイル（研究室・サークル・会社など，使う形ごとのマスター + 設定 + 言い回しの決まり）を扱う．標準ライブラリだけで動く．

使い方:
  python3 profile.py list                    … プロファイルの一覧（名前・置き場所・説明・当てはまるディレクトリ）
  python3 profile.py which [ディレクトリ]     … そのディレクトリで使うプロファイルと理由．決まらなければ候補を出して終了コード 2
  python3 profile.py show <名前>             … 既定値に重ねた設定
  python3 profile.py new <名前> --master <マスター.pptx> [--description 説明] [--match '~/research/**'] [--where user|skill]
                                             … プロファイルを作る（既定は ~/.config/master-slide-fmt/profiles/）
"""
import argparse, json, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

def cmd_list(a):
    ps = config.list_profiles()
    if not ps: print('プロファイルが無い．`profile.py new` で作る'); return
    for p in ps:
        m = ', '.join((p.get('match') or {}).get('paths', [])) or '-'
        print(f"{p['name']}  [{p['_source']}]  {p.get('description', '')}\n    場所: {p['_dir']}\n    当てはまるディレクトリ: {m}")

def cmd_which(a):
    name, why = config.which(a.dir or '.')
    if name:
        print(json.dumps({'profile': name, 'reason': why}, ensure_ascii=False)); return
    print(json.dumps({'profile': None, 'candidates': why,
                      'next': '説明・hints とディレクトリの中身（CLAUDE.md・README など）から選び，迷うならユーザーに聞く．'
                              '決めたら資料の slides.config.json に "profile" を書く'}, ensure_ascii=False, indent=1))
    sys.exit(2)

def cmd_show(a):
    p = config.load_profile(a.name)
    cfg = config.merge(config.DEFAULTS, p.get('config', {}))
    print(json.dumps({'profile': {k: v for k, v in p.items() if not k.startswith('_') and k != 'config'}, 'config': cfg}, ensure_ascii=False, indent=1))

def cmd_new(a):
    base = Path('~/.config/master-slide-fmt/profiles').expanduser() if a.where == 'user' else config.SKILL / 'profiles'
    d = base / a.name
    if d.exists(): sys.exit(f'もうある: {d}')
    src = Path(a.master).expanduser()
    if not src.is_file(): sys.exit(f'マスターが無い: {src}')
    d.mkdir(parents=True)
    shutil.copy2(src, d / 'master.pptx')
    prof = {'name': a.name, 'description': a.description or '（どんな資料に使うか．Claude がプロファイルを選ぶときに読む）',
            'match': {'paths': a.match or [], 'hints': []}, 'master': 'master.pptx', 'style_guide': 'STYLE.md',
            'new_deck': {'cover_title': '（タイトル）', 'cover_sub': '{date}<br>（名前）'},
            'config': {'footer': {'text': 'auto'}},
            'private_words': []}
    (d / 'profile.json').write_text(json.dumps(prof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (d / 'STYLE.md').write_text('# %s の書き方の決まり\n\n- 見出しの付け方:\n- 文の終わり方（です・ます／体言止め）:\n- 色の付け方:\n- 文字の大きさの段:\n' % a.name, encoding='utf-8')
    print(f'作った: {d}\n  profile.json の description・match・private_words（公開前チェックで探す名前）を埋める')

ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
sub.add_parser('list').set_defaults(f=cmd_list)
w = sub.add_parser('which'); w.add_argument('dir', nargs='?'); w.set_defaults(f=cmd_which)
s = sub.add_parser('show'); s.add_argument('name'); s.set_defaults(f=cmd_show)
n = sub.add_parser('new'); n.add_argument('name'); n.add_argument('--master', required=True); n.add_argument('--description')
n.add_argument('--match', action='append'); n.add_argument('--where', choices=['user', 'skill'], default='user'); n.set_defaults(f=cmd_new)
a = ap.parse_args(); a.f(a)
