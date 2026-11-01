---
name: master-slide-fmt
description: 自分のパワポのマスター（.pptx）から体裁を読み取り，スライドを縦スクロールの HTML で 1 枚ずつ作って，PDF と全部編集できるパワポ（そのマスターの上）に書き出す。研究室・サークル・会社など，使う形をプロファイルで切り替え，作業しているディレクトリから選ぶ。Claude では，公開したページ（Artifact）にコメントをもらいながら直すのを基本の流れにする。「スライドを作って」「報告のスライド」「発表資料」「このマスターで」「いつもの形式で」「パワポにして」と言われたら使う。
---

# master-slide-fmt

パワポのマスターを 1 つ渡すと，その体裁（大きさ 4:3 / 16:9，タイトルの位置・大きさ・色，本文の書体と段，飾りの線や帯や画像，脚注）で HTML を組み，同じ見た目の PDF と，全部編集できるパワポを作る。

- 正本は `*.src.html`（スライド 1 枚 = `<section class="slide">`）。体裁の CSS は書かない。build のたびに，マスターと設定から作って埋め込む
- パワポは，ブラウザで測った位置のとおりに，マスターの上へ置き直す（文はテキスト，表は表，式はテキストか PowerPoint の数式，図は画像）
- 使う形（マスター + 設定 + 言い回しの決まり）は **プロファイル** にまとめ，作業しているディレクトリから選ぶ

道具はすべて `tools/` にある。以下 `$S` はこのスキルのフォルダ（例: `~/.claude/skills/master-slide-fmt`）。

## 1. 最初にすること: プロファイルを決める

```bash
python3 $S/tools/doctor.py                        # 依存と，見つかったプロファイル
python3 $S/tools/profile.py which <資料を作るディレクトリ>
```

- `which` が名前を返したら，それを使う。**選んだプロファイルと理由を 1 行でユーザーに伝える**（例: 「~/research の下なので my-lab の形で作ります」）
- 決まらない（終了コード 2）ときは，候補の `description`・`hints` と，そのディレクトリの CLAUDE.md・README・フォルダ名から選ぶ。迷うときは AskUserQuestion で聞く。合うものが無ければ，マスターをもらって `profile.py new` で作る
- プロファイルの `style_guide`（STYLE.md）があれば，**書き始める前に必ず読む**。見出しの付け方・語尾・色の付け方・文字の段など，その形の決まりが書いてある
- 決めたプロファイルは，資料の `slides.config.json` の `"profile"` に書く（以後は同じ形で作られる）

プロファイルを探す場所（上ほど優先）: 環境変数 `MASTER_SLIDE_PROFILES` → `~/.config/master-slide-fmt/profiles/` → `$S/profiles/`（gitignore で公開されない）→ `$S/examples/`（公開の見本）。どれを選ぶか（上ほど優先）: 資料の `slides.config.json` の `"profile"` → 上のフォルダの `.slide-profile`（1 行でプロファイル名）→ プロファイルの `match.paths`（一番長く当てはまるもの）→ Claude の判断。

## 2. 資料の始め方

```bash
python3 $S/tools/new_deck.py <資料のフォルダ> [--profile 名前] [--title タイトル]
cd <資料のフォルダ> && ./build.sh            # HTML・PDF・パワポ（--html-only で HTML だけ）
```

`<名前>.src.html`（ひな形。表紙と見本が 3 枚）・`slides.config.json`・`build.sh`・`figs/`・`.gitignore`（`.build/`）ができる。build が作るもの:

| ファイル | 中身 |
|---|---|
| `<名前>.html` | 体裁・飾り・図・式を全部埋め込んだ 1 ファイル。公開（Artifact）とプレビューに使う。右上のボタンで PDF・パワポを開ける |
| `<名前>.pdf` | 1 枚 1 ページ（大きさはマスターと同じ） |
| `<名前>.pptx` | 全部編集できるパワポ。作れなかったときだけ，中身が画像の版に切り替わる |
| `.build/<名前>.sheet.png` | PDF の全部の枚を並べた画像（確認用） |
| `.build/master.json`・`resolved.json`・`theme.css` | マスターから読んだもの・解決した設定・作った CSS（何が入ったかを見るため） |

## 3. HTML の書き方

**書き方の見本は `$S/examples/decks/parts/parts.src.html`**（部品を 1 枚に 1 つずつ）。用途ごとの見本の資料も `$S/examples/decks/` にある（研究の報告・勉強会・学会発表・LT・サークルの説明会・旅行のしおり・製品の紹介・地域のお知らせ・社内の報告・自己紹介）。初めての形で書くときは，近い見本の src を読んでから書く。

| 書き方 | 意味 | パワポでは |
|---|---|---|
| `<section class="slide cover">` + `.cover-title` / `.cover-sub` | 表紙 | マスターの表紙のレイアウト（タイトル + サブタイトル） |
| `<section class="slide">` + `<h2>` | 本文の枚と見出し | マスターの「タイトルだけ」のレイアウトのタイトル |
| `<p class="lead">` | 本文（その枚で一番大事なこと．段 1） | テキスト（記号は `bullets.lead`） |
| `<ul class="body"><li>` / 入れ子の `<li>` | 内容（段 2）/ 要素（段 3） | 箇条書き |
| `<p class="cap">` / `.cap.small` | 図の下の 1 行 / 小さい注記 | テキスト |
| `<div class="box">` / `.box.eqn`（`.eqbody` + `.eqno`） | 黒枠 / 番号つきの式 | 四角 + テキスト（番号は右端にそろえた別の文字の箱） |
| `<table>` / `table.tight` / `table.sym` | 表 / 列の多い表 / 記号の表 | パワポの表 |
| `<img class="graph" src="figs/…">` | 図（build が埋め込む） | 画像 |
| `.row` > `.col` + `.figcap` / `.two` | 図を横に並べる / 2 段組み | 画像とテキスト |
| `<p class="refs">` | 出典（脚注の帯のすぐ上に固定） | テキスト |
| `<span class="good">` / `<span class="bad">` | 良い面（既定は青）/ 悪い面・注意（既定は赤）。意味のまとまりごとに付ける | 文字の色 |
| `$…$` | 式（LaTeX）。文字で書けるもの（記号・添字・ギリシャ文字）はテキスト，分数・Σ の上下・根号・行列・ハットなどは絵 | テキスト / PowerPoint の数式（代わりの表示として画像も入れる。変換できない式は画像だけ） |

- 脚注（日付・名前・ページ番号）と飾りは書かない。マスターと設定から入る
- build は，各スライドを「飾り → 見出し → 本文の領域（`.inner`）→ 出典 → 脚注」の形に組んで HTML に書き込む。スクリプトが動かない表示（ブラウザのペインの静止画など）でも崩れない。スクリプトがするのは，開いた日の日付・画面の幅に合わせた縮小・はみ出したときの図の縮小だけ
- 文字は縮めない。入らないときは図が先に小さくなり，それでも入らない枚は `data-over` が付いて，パワポの書き出しが「はみ出し: n 枚目」と出す。**枚を分けるか文を短くする**（`style="font-size:…"` で縮めない）
- 資料だけの調整は `<style>` に書く（例: `.row img.graph { width: 52% }`）

## 4. 進め方（ユーザーと話しながら 1 枚ずつ）

1. **聞く**: 聞き手が何を知っているか，時間，形式（発表 / 画面共有で議論 / 配布）。聞き手が知っていることは削る
2. **構成を決める**: 見出しと本文（1 文）の案を表で出して合意を取る。1 枚 = 1 メッセージ
3. **文を書く**: STYLE.md の決まりに合わせる。数値・条件・「未検証」などの確度を落とさない。考察はユーザーの考えをそのまま書く（理由を作らない）
4. **図を作る**: スクリプトを残し（`uv run --with matplotlib …`），作ったら自分の目で画像を確かめる（文字の切れ・重なり）。まだ無い図は「（仮）〜の図」の画像で置いておく
5. **HTML にして build**，全部の枚を画像で確かめる（7）
6. **公開してコメントで直す**（5。Claude のとき）
7. 区切りごとにローカル commit（資料がリポジトリの中にあるとき）

## 5. サイトでコメントをもらいながら直す（Claude 専用）

いちばん効率が良い流れ。Artifact（claude.ai のページ）とコメント（ArtifactComments）を使うので，**Claude のときだけ**使える。Codex など他のハーネスでは，build した PDF を見てもらい，チャットで直す所をもらう。

**流れ**
1. 構成と本文が決まったら，図が無い枚は仮の図のまま `./build.sh` を回す
2. 埋め込み済みの `<名前>.html` を Artifact で公開する（以後は同じ file_path で公開し直すと，同じ URL のまま版が上がる）
3. ユーザーがページの枚・図・語にコメントする。`ArtifactComments` で開いているスレッドを読み，まとめて直す
4. `./build.sh`（`--html-only` ではなく全部）→ `.build/<名前>.sheet.png` で全部の枚を確かめる → 公開し直す
5. スレッドごとに「何をどう直したか（版の番号つき）」を返信し，解決済みにする。区切りごとにローカル commit

**決まり**
- **自動の返信を信じない**。直す前に自動の返信が付くことがあり，中身が誤っていることがある。スレッドを読み，誤りは直した後の返信で「前の返信は誤りでした」と訂正する。自動の返信が付いたスレッドへの返信には `acknowledge_duplicate: true` が要る
- **名前や言い方を「どれが良い？」と聞かれたスレッドは，ユーザーが選ぶまで開いたままにする**。こちらで決めて直さない
- コメントの描き方が式・事実と合わないときは，正しい形で描き，返信で理由を 1 文書く
- 言い換えは，スライド・図のスクリプト・目次をまとめて置き換え，`grep` で残りを確かめる
- 枚を足して式の番号が変わったら振り直し，返信で知らせる（「NMSE の式は (11) になりました」）
- 説明用の図は，同じ 1 つの例を枚をまたいで使う（同じ数値で話がつながる）
- プレビュー（ブラウザのペイン）は相対パスの図を読めない。公開・プレビューには埋め込み済みの `<名前>.html` を使う

## 6. 設定（`slides.config.json`。プロファイルの `"config"` にも同じ形で書く）

既定値 → プロファイルの `config` → 資料の `slides.config.json` の順に重なる。`"auto"` はマスターから読む。

| 項目 | 既定 | 意味 |
|---|---|---|
| `profile` | — | 使うプロファイル（資料の側にだけ書く） |
| `master` | プロファイルの master.pptx | 資料ごとに別のマスターを使うとき（資料のフォルダからの相対パス） |
| `layouts.content` / `layouts.cover` | auto | 本文と表紙に使うレイアウトの名前。auto は「タイトルだけ」と「タイトル スライド」を探す |
| `content_box` | auto | 本文の領域 `{x, y, w, h}`（px）。auto はタイトルの帯の下から脚注の帯の上まで |
| `fonts.latin` / `fonts.ea` / `fonts.fallback` | auto | 英字・和文の書体，無いときの代わり（Mac のヒラギノなど） |
| `title.size` / `.color` / `.bold` | auto | 見出しの書式を変えたいとき |
| `sizes_pt.lead` / `.body` / `.sub` / `.small` / `.strict` | auto（マスターの段 1〜3）/ 12 / true | 文字の大きさの段（pt）。strict は段の外の大きさを知らせる |
| `bullets.lead` / `.body` / `.sub` | auto（マスターの記号） | 箇条書きの記号（例: ◆ – •）。`""` で記号なし |
| `colors.text` / `.good` / `.bad` / `.table_head` / `.table_border` / `.box_border` / `.page_bg` | auto / 0070C0 / FF0000 / D9D9D9 / 000000 / 000000 / 2F3B52 | 文字・強調・表・枠・ページの背景（スライドの外）の色 |
| `footer.text` / `.date` / `.date_format` / `.number` | auto（マスターのフッターの文字）/ field / en-long / true | 脚注の名前，日付（field = 開いた日に変わる / fixed / none），書式（en-long = October 3, 2026 / ymd = 2026/10/3 / iso），ページ番号 |
| `math.font` / `.preamble` / `.pptx` / `.plugin` | sans / "" / office / "" | 式の書体（sans = Arial 風 / serif），LaTeX のプリアンブルに足す行，パワポの絵の式（office = PowerPoint の数式。pandoc で変換 / image = 画像），パワポで絵の式を置く Python のファイル（プロファイルのフォルダからの相対でよい。`add(slide, tex, size_pt, color, (x, y, w, h))` で置き，置けなければ例外。無ければ画像） |
| `chrome` | 自動で探す | Chrome / Chromium の場所 |

プロファイル（`profile.json`）にだけ書く項目: `name`，`description`（Claude が選ぶときに読む），`match.paths`（当てはまるディレクトリ。`~/research/**` の形）と `match.hints`（話題の語），`master`，`style_guide`，`new_deck.cover_title` / `cover_sub`（ひな形の表紙。`{date}` は今日），`private_words`（公開前チェックで探す語）。

## 7. 確かめ方

- **全部の枚を画像で見る**: build の後に `.build/<名前>.sheet.png` を Read で開く。1 枚だけ見て済ませない
- **パワポも見る**: `$S/tools/pptx_sheet.sh <名前>.pptx [出力.png]`（LibreOffice で PDF にして並べる）。Mac に PowerPoint があれば `--powerpoint` の方が正確（日本語の字間が LibreOffice と違う）。PowerPoint が許可の確認で止まることがあるので，そのときは LibreOffice の結果で見て，その旨を伝える
- **HTML とパワポを左右に並べる**: `uv run --with pymupdf --with pillow python $S/tools/compare.py <名前>.pdf <パワポの PDF> <出力の接頭辞> [枚の番号,…]`
- build の出力に「はみ出し」「段の外の文字の大きさ」「画像にした式」が出たら，その枚を直す
- 見本の資料を全部のプロファイルで作る: `$S/tools/try_profiles.sh <出力のフォルダ> [名前 …]`

## 8. プロファイルを作る・公開する

```bash
python3 $S/tools/profile.py new my-lab --master ~/Downloads/lab.pptx --match '~/research/**' --description '研究室のゼミの報告（4:3）'
python3 $S/tools/profile.py show my-lab
```

- 既定の置き場は `~/.config/master-slide-fmt/profiles/<名前>/`（`master.pptx`・`profile.json`・`STYLE.md`）。どのリポジトリの外にもあるので，名前入りのマスターを置いても公開されない
- `private_words` に名前・学籍番号・所属など公開したくない語を書く
- このスキルを公開する前に `python3 $S/tools/check_public.py` を回す。全プロファイルの `private_words`・メールアドレス・ホームのパス・.pptx の中（レイアウトの文字と作成者の欄）を探し，見つかれば終了コード 1
- 見本のマスターを作る: `uv run --with python-pptx --with pillow python $S/tools/make_plain_master.py out.pptx --aspect 16:9 --style plain|seminar|report|club|dark|conference|minimal|pastel|pitch|notice`

## 9. マスターから読むもの・読めないもの

| 読む | 読まない（警告して HTML では描かない．パワポにはマスターから出る） |
|---|---|
| スライドの大きさ，テーマの書体と色（schemeClr の lumMod などを計算） | グラデーション・画像の塗りの図形，斜めの線 |
| レイアウトの名前と種類，プレースホルダーの位置（レイアウト → マスターの順に継承） | 四角・角丸・楕円以外の形（四角で近似） |
| タイトル・サブタイトル・本文の段 1〜3・脚注の書式（大きさ・太字・色・書体・揃え・上下の揃え・内側の余白） | アニメーション，SmartArt |
| 飾り（四角・線・画像・図形の中の文字，グループの中も），背景（単色・画像） | |

## 10. 依存

| もの | 無いとき |
|---|---|
| uv | 何も作れない（止まって入れ方を出す） |
| Google Chrome / Chromium | HTML だけ作る（PDF・パワポは作らない） |
| LaTeX（latex・dvisvgm。日本語を含む式は xelatex・pdftocairo） | HTML の式は MathJax で表示する（パワポの代わりの画像も MathJax の見た目） |
| pandoc | パワポの式は画像だけ（PowerPoint の数式にならない） |
| LibreOffice / PowerPoint | パワポの確認の画像が作れない（作ること自体はできる） |

`python3 $S/tools/doctor.py` で，何があって何が外れるかを表で出す。

## 11. 古い形の資料を移す

体裁の CSS・脚注（名前を直接書いたもの）・自動縮小のスクリプトを src に持っている資料は，`python3 $S/tools/migrate_deck.py <古い.src.html> <新しい.src.html>` で共通の部分を外す。資料だけの規則は残る。移したら `slides.config.json` にプロファイルを書いて build し，`compare.py` で前の PDF と並べて確かめる。

## 12. 落とし穴

- 図を作り直したら `figs/` に置き直して build する（古い図が残りやすい）。直したら全部の図を目で確かめる
- matplotlib で日本語と `$数式$` が同じ文字列に混ざると，書体の切り替えが効かず □ になることがある。その文字列には `fontfamily` で和文の書体を直接指定する
- 折り返しは文節ごと（`word-break: auto-phrase`）。それでも 1 語だけ次の行に落ちる所は，文を短くするか `<br>` を入れる。表のセルは折り返さない（必要な所だけ `<br>`）
- パワポの改行は HTML と同じ位置に入れてある。パワポ上で文を大きく書き換えたら，改行を入れ直す
- PowerPoint の数式は Cambria Math で組まれるので，HTML（LaTeX の絵）と字の形と幅が少し違う。測った位置の中心にそろえて置いてある
- LibreOffice・Keynote・Google スライドは PowerPoint の数式を描けず，一緒に入れた画像が出る。数式の見た目は PowerPoint で開いて確かめる（LibreOffice の確認用の画像では分からない）
- pandoc が読めない書き方の式は画像だけになり，build の「画像にした式」に理由が出る（`{\rm H}`，`\arg\min` は自動で書き換える）
- 箇条書きの記号の幅 = 字下げ（パワポのぶら下げインデントと同じ並び）。この CSS を変えると，パワポで文と式の位置がずれる
- 結合したセルのある表はパワポに書き出せない（その資料は画像の版になる）
- 日本語の書体は，マスターの書体（例: ＭＳ ゴシック）が Mac に無いと，HTML・PDF では `fonts.fallback`（ヒラギノなど）で出る。パワポはマスターの書体のまま
