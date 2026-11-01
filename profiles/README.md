# profiles/

自分のプロファイル（研究室・サークル・会社など、使う形ごとのマスターと設定）を置く場所。
このフォルダの中身は `.gitignore` で公開から外れる（この README だけ公開する）。

おすすめは、どのリポジトリの外にもある `~/.config/master-slide-fmt/profiles/` に置くこと。
作り方:

```bash
python3 tools/profile.py new my-lab --master ~/Downloads/lab_template.pptx --match '~/research/**'
```

`profile.json` の `private_words` に、名前・学籍番号・所属など、公開したくない語を書いておくと、
`tools/check_public.py` が公開するファイルの中を探して知らせる。
