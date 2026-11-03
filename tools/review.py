#!/usr/bin/env python3
"""
review.py — レビュー画面で資料にコメントを付け，チャットの AI に送る（Artifact を使わない．Claude 以外の AI でも使える）

  python3 review.py open  <資料のフォルダ> [--name 名前] [--no-window] [--native]   レビュー画面を開く（サーバーが無ければ裏で立てる．すぐ戻る）
                                                                      --native: この画面のコメントを使わず，ブラウザの「箇所を指定」でチャットに送る（Codex のアプリ）
  python3 review.py wait  <資料のフォルダ> [--timeout 秒]               レビュー画面から送信されたコメントが来るまで待ち，AI 向けの文にして出す
  python3 review.py reply <資料のフォルダ> <id> "返信" [--resolve]       レビュー画面のコメントに AI から返信する（--resolve で解決にする）
  python3 review.py list  <資料のフォルダ> [--all]                      コメントの一覧（--all で解決済みも）
  python3 review.py stop  <資料のフォルダ>                              サーバーを止める

仕組み:
  - サーバー（127.0.0.1．Python の標準ライブラリだけ）が，build 済みの <名前>.html に部品（review_overlay.js）を差し込んで出す
  - レビュー画面で要素に乗ると塗られ，押すと吹き出しが出る（文を選んでもよい）．書いて「送信」．コメントは <資料>/.review/comments.json に残る
  - AI は wait で受け取り，直して build し，reply で返す．<名前>.html が変わると画面が自動で読み直す（今見ている枚は保つ）
  - wait の終了コード: 0 = 届いた，2 = 時間切れ（もう一度 wait する）
"""
import argparse, json, mimetypes, os, subprocess, sys, time, threading, urllib.request, webbrowser
from contextlib import contextmanager
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
try:
    import fcntl                                              # 画面のサーバーと wait・reply が同じファイルを書くので，ロックする
except ImportError:                                           # Windows には無い（そのときはロックしない）
    fcntl = None

TOOLS = Path(__file__).resolve().parent
ME = TOOLS / 'review.py'


# ---------- コメントの置き場（<資料>/.review/comments.json） ----------
# スレッド = {id, slide, index, title, quote, path, state: open|resolved, created, messages: [...]}
# メッセージ = {who: user|ai, text, at, status}．status は user だけ: draft（下書き）→ sent（送信）→ delivered（AI が受け取った）
def rdir(deck):
    d = deck / '.review'
    d.mkdir(exist_ok=True)
    return d


def now():
    return datetime.now().isoformat(timespec='seconds')


@contextmanager
def store(deck, write=True):
    d = rdir(deck)
    f = d / 'comments.json'
    with open(d / 'lock', 'a') as lk:
        if fcntl:
            fcntl.flock(lk, fcntl.LOCK_EX)
        data = json.loads(f.read_text(encoding='utf-8')) if f.is_file() else {'next': 1, 'threads': []}
        yield data
        if write:
            tmp = d / 'comments.tmp'
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
            os.replace(tmp, f)


def find(data, tid):
    for t in data['threads']:
        if t['id'] == tid:
            return t
    raise LookupError(f'review: {tid} というコメントはありません。review.py list で一覧を表示できます。')


def pending(data, statuses=('sent',)):
    """AI にまだ渡していないユーザーのメッセージ（スレッドごと）"""
    out = []
    for t in data['threads']:
        ms = [m for m in t['messages'] if m['who'] == 'user' and m.get('status') in statuses]
        if ms:
            out.append((t, ms))
    return out


def where(t):
    return f'{t["index"]} 枚目「{t["title"]}」' if t.get('title') else f'{t["index"]} 枚目'


def prompt(deck, items):
    """AI がそのまま読める形にする（wait の出力と，画面の「コメントをコピー」で同じものを使う）"""
    n = sum(len(ms) for _, ms in items)
    L = [f'レビュー画面からコメントが {n} 件届きました。資料: {deck}']
    for t, ms in items:
        L.append(f'\n[{t["id"]}] {where(t)}')
        if t.get('quote'):
            L.append(f'  選択したテキスト: 「{t["quote"]}」')
        if t.get('path'):
            L.append(f'  要素: {t["path"]}')
        for m in t['messages']:
            if m in ms:
                L.append(f'  コメント: {m["text"]}')
            else:
                L.append(f'  （前の{"コメント" if m["who"] == "user" else "AI の返信"}）{m["text"]}')
    L.append('\n直したら build し、コメントごとに何をどう直したかを返信する。質問には答え、直さない場合は理由を書く:')
    L.append(f'  python3 {ME} reply {deck} <id> "返信" [--resolve]')
    L.append(f'返信し終えたら、次のコメントを待つ: python3 {ME} wait {deck}')
    return '\n'.join(L)


def deliver(deck, statuses=('sent',)):
    """渡していないメッセージを delivered にして，AI 向けの文を返す（無ければ None）"""
    with store(deck) as data:
        items = pending(data, statuses)
        if not items:
            return None
        text = prompt(deck, items)
        for _, ms in items:
            for m in ms:
                m['status'] = 'delivered'
                m['delivered_at'] = now()
        return text


# ---------- サーバー ----------
def deck_name(deck, name):
    if name:
        return name
    srcs = sorted(deck.glob('*.src.html'))
    if len(srcs) == 1:
        return srcs[0].name[:-len('.src.html')]
    htmls = [p for p in sorted(deck.glob('*.html')) if not p.name.endswith('.src.html')]
    if len(srcs) == 0 and len(htmls) == 1:
        return htmls[0].stem
    raise SystemExit(f'review: 資料が 1 つに決まりません（{", ".join(p.name for p in srcs or htmls) or "なし"}）。--name で指定してください')


def make_handler(deck, name):
    html = deck / f'{name}.html'
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):                            # アクセスの記録は出さない
            pass

        def send(self, code, body, ctype='text/plain; charset=utf-8'):
            b = body if isinstance(body, bytes) else body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(b)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(b)

        def state(self):
            with store(deck, write=False) as data:
                return {'name': name, 'deck': str(deck), 'version': html.stat().st_mtime if html.is_file() else 0, 'threads': data['threads']}

        def do_GET(self):
            p = self.path.split('?')[0]
            if p == '/':
                self.send_response(302)
                self.send_header('Location', f'/deck/{urllib.request.quote(name)}.html')
                self.end_headers()
                return
            if p == '/__review/overlay.js':
                return self.send(200, (TOOLS / 'review_overlay.js').read_bytes(), 'text/javascript; charset=utf-8')
            if p == '/__review/ping':
                return self.send(200, json.dumps({'deck': str(deck), 'name': name}), 'application/json')
            if p == '/__review/state':
                return self.send(200, json.dumps(self.state(), ensure_ascii=False), 'application/json; charset=utf-8')
            if p == '/__review/events':
                return self.events()
            if p.startswith('/deck/'):
                f = (deck / urllib.request.unquote(p[len('/deck/'):])).resolve()
                if deck not in f.parents or not f.is_file():
                    return self.send(404, 'not found')
                body = f.read_bytes()
                if f == html:                                  # 資料にコメントの部品を差し込む（build の出力そのものは変えない）
                    s = body.decode('utf-8')
                    i = s.rfind('</body>')
                    tag = f'<script src="/__review/overlay.js" data-name="{name}"></script>'
                    body = (s[:i] + tag + s[i:] if i >= 0 else s + tag).encode('utf-8')
                return self.send(200, body, (mimetypes.guess_type(f.name)[0] or 'application/octet-stream'))
            return self.send(404, 'not found')

        def events(self):
            """資料（<名前>.html）とコメントが変わったら知らせる（Server-Sent Events）"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            cf = rdir(deck) / 'comments.json'
            mt = lambda f: f.stat().st_mtime if f.is_file() else 0
            last_h, last_c, beat = mt(html), mt(cf), time.time()
            try:
                while True:
                    time.sleep(0.5)
                    h, c = mt(html), mt(cf)
                    if h != last_h:
                        time.sleep(0.3)                          # build が書き終わるのを少し待つ
                        last_h = mt(html)
                        self.wfile.write(b'event: html\ndata: 1\n\n')
                    if c != last_c:
                        last_c = c
                        self.wfile.write(b'event: comments\ndata: 1\n\n')
                    if time.time() - beat > 15:
                        beat = time.time()
                        self.wfile.write(b': keep\n\n')
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            q = json.loads(self.rfile.read(n) or b'{}')
            p = self.path.split('?')[0]
            try:
                return self.post(p, q)
            except (LookupError, IndexError) as e:
                return self.send(404, str(e))

        def post(self, p, q):
            with lock, store(deck) as data:
                out = {'ok': True}
                if p == '/__review/new':                       # 新しいコメント（範囲を選んで，または枚ごと）
                    t = {'id': f'c{data["next"]}', 'slide': q.get('slide', ''), 'index': q.get('index', 0),
                         'title': q.get('title', ''), 'quote': q.get('quote', ''), 'path': q.get('path', ''),
                         'state': 'open', 'created': now(), 'messages': []}
                    data['next'] += 1
                    t['messages'].append({'who': 'user', 'text': q['text'], 'at': now(), 'status': 'sent' if q.get('send') else 'draft'})
                    data['threads'].append(t)
                    out['id'] = t['id']
                elif p == '/__review/reply':                   # 既存のスレッドに続けて書く
                    t = find(data, q['id'])
                    t['messages'].append({'who': 'user', 'text': q['text'], 'at': now(), 'status': 'sent' if q.get('send') else 'draft'})
                    t['state'] = 'open'
                elif p == '/__review/send':                    # 下書きをまとめて送信
                    for t in data['threads']:
                        for m in t['messages']:
                            if m['who'] == 'user' and m.get('status') == 'draft':
                                m['status'] = 'sent'
                elif p == '/__review/edit':                    # 下書きを書き直す・消す
                    t = find(data, q['id'])
                    m = t['messages'][q['msg']]
                    if m.get('status') != 'draft':
                        return self.send(409, '送信済みのコメントは編集できません')
                    if q.get('text'):
                        m['text'] = q['text']
                    else:
                        t['messages'].pop(q['msg'])
                        if not t['messages']:
                            data['threads'].remove(t)
                elif p == '/__review/state':                   # 解決 / 開き直す
                    find(data, q['id'])['state'] = q['state']
                elif p == '/__review/copy':                    # 「コピーして貼る」: 下書きと送信済みをまとめて文にし，渡したことにする
                    items = pending(data, ('draft', 'sent'))
                    out['text'] = prompt(deck, items) if items else ''
                    for _, ms in items:
                        for m in ms:
                            m['status'] = 'delivered'
                            m['delivered_at'] = now()
                else:
                    return self.send(404, 'not found')
            return self.send(200, json.dumps(out, ensure_ascii=False), 'application/json; charset=utf-8')

    return H


def server_info(deck):
    f = rdir(deck) / 'server.json'
    if not f.is_file():
        return None
    info = json.loads(f.read_text())
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{info["port"]}/__review/ping', timeout=1.5) as r:
            if json.loads(r.read())['deck'] == str(deck):
                return info
    except Exception:
        pass
    return None


def serve(deck, name, port):
    srv = ThreadingHTTPServer(('127.0.0.1', port), make_handler(deck, name))
    srv.daemon_threads = True
    info = {'port': srv.server_address[1], 'pid': os.getpid(), 'name': name, 'started': now()}
    (rdir(deck) / 'server.json').write_text(json.dumps(info))
    print(f'review: http://127.0.0.1:{info["port"]}/ で {deck / (name + ".html")} を表示しています', flush=True)
    srv.serve_forever()


def open_window(url, deck):
    """アドレスバーの無い専用のウィンドウ（Chrome の --app）．Chrome が無ければ既定のブラウザ"""
    try:
        chrome = subprocess.run([sys.executable, str(TOOLS / 'doctor.py'), '--chrome', str(deck)], capture_output=True, text=True).stdout.strip()
    except Exception:
        chrome = ''
    if chrome:
        subprocess.Popen([chrome, f'--app={url}', '--window-size=1600,1000'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    else:
        webbrowser.open(url)


# ---------- コマンド ----------
def cmd_open(a):
    deck = Path(a.deck).resolve()
    name = deck_name(deck, a.name)
    if not (deck / f'{name}.html').is_file():
        raise SystemExit(f'review: {name}.html がありません。先に build してください')
    info = server_info(deck)
    if not info:
        log = open(rdir(deck) / 'server.log', 'a')
        subprocess.Popen([sys.executable, str(ME), 'serve', str(deck), '--name', name, '--port', str(a.port)],
                         stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
        for _ in range(50):
            time.sleep(0.2)
            info = server_info(deck)
            if info:
                break
        if not info:
            raise SystemExit(f'review: サーバーを起動できませんでした。{rdir(deck) / "server.log"} を確認してください')
    url = f'http://127.0.0.1:{info["port"]}/deck/{urllib.request.quote(name)}.html' + ('?native=1' if a.native else '')
    if not a.no_window:
        open_window(url, deck)
    print(f'review: レビュー画面 {url}（資料 {name}.html）')
    if a.native:
        print('次: この URL をブラウザで開いてもらう。コメントはブラウザの「箇所を指定」でチャットに届くので，wait は要らない。直したら build すれば画面が読み直す')
    else:
        print(f'次: このまま wait を回し，送信されたコメントを待つ。ユーザーに「送ったら教えて」と頼んでターンを終えない: python3 {ME} wait {deck}')


def cmd_wait(a):
    deck = Path(a.deck).resolve()
    if not server_info(deck):
        print(f'review: レビュー画面のサーバーが動いていません。python3 {ME} open {deck} で開いてください', file=sys.stderr)
    t0 = time.time()
    while True:
        text = deliver(deck)
        if text:
            print(text)
            return 0
        if a.timeout and time.time() - t0 > a.timeout:
            print(f'review: {a.timeout} 秒待ちましたが、コメントはまだ届いていません。ユーザーに聞かず、すぐもう一度 wait する: python3 {ME} wait {deck}')
            return 2
        time.sleep(1)


def cmd_reply(a):
    deck = Path(a.deck).resolve()
    with store(deck) as data:
        t = find(data, a.id)
        t['messages'].append({'who': 'ai', 'text': a.text, 'at': now()})
        if a.resolve:
            t['state'] = 'resolved'
    print(f'review: {a.id} に返信しました' + ('（解決済みにしました）' if a.resolve else ''))


def cmd_list(a):
    deck = Path(a.deck).resolve()
    with store(deck, write=False) as data:
        ts = [t for t in data['threads'] if a.all or t['state'] == 'open']
        if not ts:
            print('review: コメントはありません')
        for t in ts:
            print(f'[{t["id"]}] {where(t)}（{"解決済み" if t["state"] == "resolved" else "未解決"}）' + (f' 「{t["quote"]}」' if t.get('quote') else ''))
            for m in t['messages']:
                tag = 'AI' if m['who'] == 'ai' else {'draft': '下書き', 'sent': '送信済み', 'delivered': 'AI に渡した'}.get(m.get('status'), '')
                print(f'   {tag}: {m["text"]}')


def cmd_stop(a):
    deck = Path(a.deck).resolve()
    info = server_info(deck)
    if not info:
        print('review: サーバーは動いていません')
        return
    try:
        os.kill(info['pid'], 15)
        print('review: サーバーを止めました')
    except OSError as e:
        print(f'review: サーバーを止められませんでした（{e}）')


def main():
    ap = argparse.ArgumentParser(description='レビュー画面で資料にコメントを付け、AI に送る')
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('open'); p.add_argument('deck'); p.add_argument('--name'); p.add_argument('--port', type=int, default=0); p.add_argument('--no-window', action='store_true'); p.add_argument('--native', action='store_true')
    p = sp.add_parser('serve'); p.add_argument('deck'); p.add_argument('--name'); p.add_argument('--port', type=int, default=0)
    p = sp.add_parser('wait'); p.add_argument('deck'); p.add_argument('--timeout', type=int, default=540, help='秒．0 で待ち続ける（既定 540）')
    p = sp.add_parser('reply'); p.add_argument('deck'); p.add_argument('id'); p.add_argument('text'); p.add_argument('--resolve', action='store_true')
    p = sp.add_parser('list'); p.add_argument('deck'); p.add_argument('--all', action='store_true')
    p = sp.add_parser('stop'); p.add_argument('deck')
    a = ap.parse_args()
    if a.cmd == 'serve':
        deck = Path(a.deck).resolve()
        return serve(deck, deck_name(deck, a.name), a.port)
    try:
        return {'open': cmd_open, 'wait': cmd_wait, 'reply': cmd_reply, 'list': cmd_list, 'stop': cmd_stop}[a.cmd](a)
    except LookupError as e:
        raise SystemExit(str(e))


if __name__ == '__main__':
    sys.exit(main() or 0)
