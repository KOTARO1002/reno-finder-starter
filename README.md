# 中古×リノベ 資金計画シミュレーター

自己資金・月々の支払可能額・金利などの条件から、**購入可能な物件価格を逆算**する
1ページのシミュレーターです。

**サーバー不要の静的サイト**なので、コールドスタート（Render 無料枠の起動待ち）は発生しません。
ページを開いた瞬間に使えます。

---

## 構成

```
index.html            画面（このファイルを開くだけで動きます）
assets/
  calc.js             計算ロジック（純粋関数のみ。ブラウザ／Node 兼用）
  app.js              画面まわりの処理
  app.css             Tailwind のビルド済み CSS（コミット済み・デプロイ時のビルド不要）
  sh-logo.png         フッターのロゴ
src/tailwind.css      app.css のビルド元
tests/calc.test.js    計算ロジックのリグレッションテスト
```

デプロイに必要なのは **`index.html` と `assets/` だけ**です。
`src/` `tests/` `package.json` は、後からスタイルを直したりテストを回したりするための開発用ファイルです。

## ローカルで動かす

`index.html` をブラウザで直接開くだけでも動きます。ローカルサーバー経由で確認したい場合は:

```bash
npm start        # http://localhost:3000
```

## デプロイ

ビルド不要の静的サイトなので、どのホスティングでも「ビルドコマンドなし・公開ディレクトリはリポジトリ直下」で完了します。

| サービス | 設定 |
|---|---|
| **Cloudflare Pages** | Build command: 空欄 / Build output directory: `/` |
| **Netlify** | Build command: 空欄 / Publish directory: `.` |
| **Vercel** | Framework Preset: `Other` / Build command: 空欄 / Output directory: `.` |
| **GitHub Pages** | Settings → Pages → Deploy from a branch → `/ (root)` |

いずれも無料枠でスリープしません。**Render は不要です。**

## スタイルを変更するとき

`index.html` の Tailwind クラスを増やしたり `src/tailwind.css` を編集した場合は、CSS を再ビルドして
`assets/app.css` を一緒にコミットしてください。

```bash
npm install
npm run build:css        # 変更を監視し続ける場合は npm run watch:css
```

## テスト

```bash
npm test
```

`tests/calc.test.js` の期待値は、静的化する前の FastAPI 実装（旧 `myapp/main.py` の `POST /calc`）を
実行して得た出力そのものです。ここが緑である限り、ブラウザ側の計算はサーバー時代と同じ数字を返します。

## 計算の前提

| 項目 | 値 | 定義場所 |
|---|---|---|
| 諸費用率 | 8%（物件価格に対して） | `assets/calc.js` の `FEE_RATE` |
| 消費税率 | 10%（リノベ費に対して） | `assets/calc.js` の `TAX_RATE` |
| フルリノベ概算 | 必要㎡数 × 12万円 + 350万円 | `assets/calc.js` の `fullRenovationCost()` |
| ボーナス返済 | 年2回（6ヶ月ごと） | `assets/calc.js` の `pvBonuses()` |
| 借入期間 | 1〜50年 | `assets/calc.js` の `validate()` |

サーバーが無くなったため、これらは環境変数ではなく `assets/calc.js` の先頭の定数になりました。
変更する場合はここを直接編集してください。

> 計算式はブラウザから読める状態になります（静的サイトである以上避けられません）。
> 非公開にしたい前提値がある場合は、その部分だけサーバー側に戻す必要があります。

## Render からの移行について

このアプリには DB も認証も外部 API 呼び出しもサーバー側の秘密情報も無く、
`POST /calc` は入力値だけで完結する四則演算でした。そのため計算をブラウザへ移し、
FastAPI（`myapp/`）を丸ごと削除しています。旧実装は Git の履歴に残っています。

静的サイト側の動作を確認できたら、Render 側のサービスは停止して問題ありません。
