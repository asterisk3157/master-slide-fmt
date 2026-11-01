"""
公開前チェック: 公開するファイルに，個人や所属が分かる語が入っていないかを探す．標準ライブラリだけで動く．

  探す語: 見つかる全部のプロファイルの private_words（公開しない側のプロファイルに書いておく）と，--word で足した語
  探す形: メールアドレス（GitHub の noreply と example.* を除く），ホームフォルダのパス（/Users/<名前>/，/home/<名前>/）
  探す所: git に入るファイル（.gitignore で外したものは見ない）．.pptx・.docx・.xlsx は中の XML（スライド・レイアウト・
          作成者の欄 docProps）まで開く．作成者の欄が空でなければ，それも知らせる

使い方: python3 check_public.py [公開するフォルダ（既定はこのスキル）] [--word 語 ...]
終了コード: 見つからなければ 0，見つかれば 1
"""
import argparse, os, re, subprocess, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
HOME = re.compile(r'/(?:Users|home)/([A-Za-z0-9._-]+)/')
SAFE_EMAIL = re.compile(r'(users\.noreply\.github\.com|@example\.(com|org|net)|noreply@anthropic\.com)$')
TEXT_EXT = {'.md', '.py', '.js', '.css', '.html', '.json', '.sh', '.txt', '.scpt', '.toml', '.yml', '.yaml', '.gitignore', '.xml', '.svg', '.csv'}

def files(root):
    try:
        out = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=root, capture_output=True, text=True, check=True).stdout
        return [root / f for f in out.splitlines() if (root / f).is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and 'profiles' not in p.relative_to(root).parts[:1]]

def scan_text(label, text, words, hits):
    for n, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        for w in words:
            if (re.search(r'(?<![A-Za-z0-9])%s(?![A-Za-z0-9])' % re.escape(w.lower()), low)) if w.isascii() else (w in line):   # 英字の語は単語の区切りで照合する
                hits.append((label, n, f'語「{w}」', line.strip()[:120]))
        for m in EMAIL.finditer(line):
            if not SAFE_EMAIL.search(m.group(0)): hits.append((label, n, 'メールアドレス', m.group(0)))
        for m in HOME.finditer(line):
            if m.group(1) not in ('runner', 'user', 'you', 'name', 'USER', 'me'): hits.append((label, n, 'ホームのパス', m.group(0)))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', nargs='?', default=str(config.SKILL)); ap.add_argument('--word', action='append', default=[])
    a = ap.parse_args()
    root = Path(a.root).resolve()
    words = set(a.word)
    for p in config.list_profiles():
        words |= {w for w in p.get('private_words', []) if w}
    u = os.environ.get('USER', '')
    if len(u) >= 4: words.add(u)                         # ログイン名（短いものは誤検出が多いので外す．ホームのパスは別に探す）
    hits = []
    fs = files(root)
    for f in fs:
        rel = str(f.relative_to(root))
        if f.suffix.lower() in ('.pptx', '.potx', '.docx', '.xlsx'):
            with zipfile.ZipFile(f) as z:
                for name in z.namelist():
                    if not name.endswith(('.xml', '.rels')): continue
                    t = z.read(name).decode('utf-8', 'replace')
                    scan_text(f'{rel}:{name}', re.sub(r'<[^>]+>', ' ', t), words, hits)
                    if name == 'docProps/core.xml':
                        for tag in ('dc:creator', 'cp:lastModifiedBy'):
                            m = re.search(r'<%s>([^<]+)</%s>' % (tag, tag), t)
                            if m and m.group(1).strip(): hits.append((f'{rel}:{name}', 0, '作成者の欄', f'{tag} = {m.group(1)}'))
        elif f.suffix.lower() in TEXT_EXT or f.name in ('.gitignore', 'LICENSE'):
            scan_text(rel, f.read_text(encoding='utf-8', errors='replace'), words, hits)
    print(f'{root}: {len(fs)} ファイルを見た（探した語 {len(words)} 個）')
    for label, n, kind, s in hits:
        print(f'  {label}:{n}  {kind}  {s}')
    if hits:
        print(f'見つかった: {len(hits)} 件．公開する前に直す（.pptx の作成者の欄は，PowerPoint の「ファイル > プロパティ」か python-pptx の core_properties で消す）')
        sys.exit(1)
    print('個人や所属が分かる語は見つからなかった（画像の中の文字は見ていない）')

if __name__ == '__main__':
    main()
