"""
見本の資料の図を作る（データはすべて架空）: uv run --with matplotlib --with numpy python examples/decks/make_figs.py
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
from matplotlib import font_manager
_have = {f.name for f in font_manager.fontManager.ttflist}
JP = [f for f in ('Hiragino Sans', 'Noto Sans CJK JP', 'IPAexGothic', 'Yu Gothic') if f in _have][:1] + ['DejaVu Sans']   # 手元にある和文の書体を 1 つ使う
plt.rcParams.update({'font.size': 13, 'font.family': JP, 'axes.unicode_minus': False})

def save(fig, deck, name):
    d = HERE / deck / 'figs'; d.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(d / name, dpi=160); plt.close(fig)

# research: プロンプトの長さとハルシネーション率
L = np.array([0.5, 1, 2, 4, 8, 16, 32]); x = np.log2(L)
fig, ax = plt.subplots(figsize=(7.2, 4.0))
ax.plot(x, 4 + 1.0 * x + 9 / (1 + np.exp(-(x - 3.4) * 2.2)), 'o-', mfc='none', label='Model A')
ax.plot(x, 3 + 0.8 * x + 6 / (1 + np.exp(-(x - 3.8) * 2.0)), 's--', mfc='none', label='Model B')
ax.plot(x, 3 + 0.5 * x + 2 / (1 + np.exp(-(x - 4.0) * 2.0)), '^-.', mfc='none', label='Model A + 関連文の選択')
ax.set_xticks(x); ax.set_xticklabels([f'{v:g}k' for v in L])
ax.set_xlabel('プロンプトの長さ [トークン]'); ax.set_ylabel('ハルシネーション率 [%]'); ax.grid(True, alpha=0.4); ax.legend(loc='upper left')
save(fig, 'research', 'hallucination_rate.png')

# club-welcome: 部員数の推移
fig, ax = plt.subplots(figsize=(7.0, 3.8))
years = ['2022', '2023', '2024', '2025', '2026']; n = [8, 11, 12, 19, 24]
bars = ax.bar(years, n, color=['#F3B6A9'] * 4 + ['#E8553D'])
for b, v in zip(bars, n): ax.text(b.get_x() + b.get_width() / 2, v + 0.4, f'{v} 人', ha='center')
ax.set_ylabel('部員数 [人]'); ax.set_ylim(0, 28); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'club-welcome', 'members.png')

# seminar-bayes: 検査の前と後
fig, ax = plt.subplots(figsize=(6.4, 3.6))
ax.bar(['検査の前\n（事前確率）', '陽性のあと\n（事後確率）'], [1, 16.1], color=['#9CC9C9', '#2E9C9C'], width=0.5)
for i, v in enumerate([1, 16.1]): ax.text(i, v + 0.5, f'{v:g}%', ha='center', fontsize=14)
ax.set_ylabel('かかっている確率 [%]'); ax.set_ylim(0, 20); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'seminar-bayes', 'bayes.png')

# lt-build: ビルド時間（暗い背景）
with plt.style.context('dark_background'):
    plt.rcParams.update({'font.family': JP})
    fig, ax = plt.subplots(figsize=(7.2, 3.6)); fig.patch.set_facecolor('#1E2028'); ax.set_facecolor('#1E2028')
    steps = ['依存の取得', 'ビルド', 'テスト', 'その他']
    before = np.array([6.5, 3.0, 7.5, 1.0]); after = np.array([0.5, 3.0, 4.5, 0.5])
    cols = ['#5BC0EB', '#9BC53D', '#FDE74C', '#C3423F']
    for row, vals in ((1, before), (0, after)):
        left = 0
        for s, v, c in zip(steps, vals, cols):
            ax.barh(row, v, left=left, color=c, label=s if row == 1 else None); left += v
        ax.text(left + 0.3, row, f'{left:g} 分', va='center', color='white', fontsize=14)
    ax.set_yticks([1, 0]); ax.set_yticklabels(['対策の前', '対策の後']); ax.set_xlabel('1 回のビルドの時間 [分]'); ax.set_xlim(0, 21)
    ax.legend(ncol=4, loc='upper center', bbox_to_anchor=(0.5, 1.22), frameon=False); ax.spines[['top', 'right']].set_visible(False)
    save(fig, 'lt-build', 'build_time.png')

# conference-co2: 推定値と実測値，1 日の変化
rng = np.random.default_rng(3)
true = rng.uniform(450, 1500, 120); est = true + rng.normal(0, 45, 120)
fig, ax = plt.subplots(figsize=(4.6, 4.2))
ax.scatter(true, est, s=14, color='#0B6E4F', alpha=0.7); ax.plot([400, 1600], [400, 1600], 'k--', lw=1)
ax.set_xlabel('実測値 [ppm]'); ax.set_ylabel('推定値 [ppm]'); ax.set_xlim(400, 1600); ax.set_ylim(400, 1600); ax.grid(True, alpha=0.3)
save(fig, 'conference-co2', 'co2_scatter.png')
h = np.linspace(8, 20, 145)
c = 450 + 700 * np.exp(-((h - 11) / 1.6) ** 2) + 550 * np.exp(-((h - 15.5) / 1.8) ** 2)
fig, ax = plt.subplots(figsize=(4.6, 4.2))
ax.plot(h, c, color='#555555', label='実測'); ax.plot(h, c + rng.normal(0, 25, h.size) + 30 * np.sin(h), color='#0B6E4F', ls='--', label='推定')
ax.axhline(1000, color='#C0392B', lw=1); ax.text(19.8, 1025, '換気の目安', color='#C0392B', fontsize=11, ha='right')
ax.set_xlabel('時刻 [時]'); ax.set_ylabel('CO2 濃度 [ppm]'); ax.legend(loc='upper left'); ax.grid(True, alpha=0.3)
save(fig, 'conference-co2', 'co2_time.png')

# monthly-report: 稼働率の推移
months = ['5月', '6月', '7月', '8月', '9月', '10月']
fig, ax = plt.subplots(figsize=(7.4, 3.6))
ax.plot(months, [83, 85, 84, 80, 86, 87], 'o-', color='#9E9E9E', label='予約率')
ax.plot(months, [50, 51, 52, 48, 56, 61], 'o-', color='#2F7D32', label='稼働率（実際に使った時間）')
ax.annotate('自動の取り消しを試行', xy=(4, 56), xytext=(2.2, 66), arrowprops=dict(arrowstyle='->', color='#2F7D32'), color='#2F7D32')
ax.set_ylabel('[%]'); ax.set_ylim(40, 95); ax.legend(loc='lower left', frameon=False); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'monthly-report', 'usage.png')

# parts: 並べて見せる 2 つの図
fig, ax = plt.subplots(figsize=(4.6, 3.6)); t = np.linspace(0, 4 * np.pi, 200)
ax.plot(t, np.sin(t), label='sin'); ax.plot(t, np.cos(t), '--', label='cos'); ax.legend(); ax.grid(True, alpha=0.3); ax.set_xlabel('t')
save(fig, 'parts', 'left.png')
fig, ax = plt.subplots(figsize=(4.6, 3.6))
ax.bar(['A', 'B', 'C', 'D'], [3, 5, 2, 4], color=['#1F6FB2', '#5DA5DA', '#9DC3E6', '#C9DDF0']); ax.set_ylabel('件数'); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'parts', 'right.png')

# travel-kyoto: 予算の内訳（1 人あたり）
fig, ax = plt.subplots(figsize=(6.0, 4.0))
vals = [14000, 9000, 6500, 4500]; labels = ['交通', '宿', '食事', '拝観料・\nおみやげ']
ax.pie(vals, labels=[f'{l}\n{v:,} 円' for l, v in zip(labels, vals)], colors=['#F4A261', '#E9C46A', '#2A9D8F', '#E76F51'],
       startangle=90, counterclock=False, wedgeprops=dict(width=0.45, edgecolor='#FFF8EE'), textprops=dict(fontsize=12, color='#5C4033'))
ax.text(0, 0, '合計\n34,000 円', ha='center', va='center', fontsize=15, color='#7A4E2D', fontweight='bold')
fig.patch.set_facecolor('#FFF8EE')
save(fig, 'travel-kyoto', 'budget.png')

# pitch-wallet: 家計簿が続かない理由，続いた人の割合
fig, ax = plt.subplots(figsize=(6.6, 3.8))
reasons = ['入力が面倒', 'レシートを\nなくす', '何に使ったか\n思い出せない', '続ける理由が\nない']
ax.barh(reasons[::-1], [62, 41, 35, 28][::-1], color=['#C9BFFA', '#C9BFFA', '#C9BFFA', '#6C4CF1'][::-1])
for i, v in enumerate([62, 41, 35, 28][::-1]): ax.text(v + 1, i, f'{v}%', va='center')
ax.set_xlim(0, 75); ax.set_xlabel('あてはまる人の割合 [%]'); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'pitch-wallet', 'reasons.png')
fig, ax = plt.subplots(figsize=(6.6, 3.8))
wk = np.arange(0, 13)
ax.plot(wk, 100 * np.exp(-wk / 3.0), 'o--', color='#9E9E9E', label='紙・表計算の家計簿')
ax.plot(wk, 100 * (0.25 + 0.75 * np.exp(-wk / 4.0)) * (1 - 0.004 * wk), 'o-', color='#6C4CF1', label='Example Wallet')
ax.set_xlabel('使いはじめてからの週'); ax.set_ylabel('続けている人 [%]'); ax.set_ylim(0, 105); ax.legend(frameon=False); ax.spines[['top', 'right']].set_visible(False)
save(fig, 'pitch-wallet', 'retention.png')

# festival-notice: 会場の配置図
from matplotlib.patches import FancyBboxPatch
fig, ax = plt.subplots(figsize=(6.4, 4.2)); ax.set_xlim(0, 100); ax.set_ylim(0, 66); ax.axis('off')
ax.add_patch(FancyBboxPatch((2, 2), 96, 62, boxstyle='round,pad=0,rounding_size=3', fc='#F1F8E9', ec='#2E7D32', lw=2))
spots = [((8, 40), 26, 18, '#FFE082', 'やぐら\n（盆踊り）'), ((40, 44), 22, 14, '#FFCCBC', '屋台'), ((66, 44), 26, 14, '#FFCCBC', '屋台'),
         ((40, 10), 20, 14, '#BBDEFB', '本部'), ((64, 10), 14, 14, '#F8BBD0', '救護'), ((82, 10), 12, 14, '#E0E0E0', '駐輪場'), ((8, 8), 22, 18, '#C8E6C9', 'こども\nひろば')]
for (x, y), w, h, c, t in spots:
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=2', fc=c, ec='#555555', lw=1))
    ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=13)
ax.annotate('入口', xy=(50, 2), xytext=(50, -5), ha='center', fontsize=13, color='#C62828', arrowprops=dict(arrowstyle='->', color='#C62828', lw=2), annotation_clip=False)
save(fig, 'festival-notice', 'map.png')

# self-intro: 1 週間の過ごし方
fig, ax = plt.subplots(figsize=(5.2, 3.8))
vals = [40, 49, 10, 8, 7, 54]; labels = ['仕事', '睡眠', 'ランニング', '料理', '読書', 'そのほか']
ax.pie(vals, labels=labels, colors=['#BDBDBD', '#E0E0E0', '#2F7D32', '#81C784', '#A5D6A7', '#F5F5F5'], startangle=90, counterclock=False,
       wedgeprops=dict(width=0.42, edgecolor='white'), textprops=dict(fontsize=12))
ax.text(0, 0, '1 週間\n168 時間', ha='center', va='center', fontsize=13)
save(fig, 'self-intro', 'week.png')
print('figs: done')
