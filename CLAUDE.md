# 英検準2級「反復道場」

英検準2級の合格を目指す学習アプリ。単一HTMLのWebアプリとして完成済みで、
これから Capacitor で Android アプリ化し、Google Play で公開する。

## 現在の状態（Web版は完成・公開中）

- 公開先: GitHub Pages `https://mac328.github.io/eiken-dojo/`（リポジトリ `mac328/eiken-dojo`）
- 収録: 732問（単語300・熟語90・文法75・会話文60・会話リスニング80・英作文50・長文45・面接カード32枚）
- 音声: `audio/` に mp3 2078本（約27.6MB）
- 進捗保存: ブラウザの localStorage（キー `eikenP2v1`）

## ファイル構成

```
eiken-dojo/
├── index.html                    アプリ本体（React・全問題データ・アイコンを内包）
├── audio/                        mp3 2078本
├── data/audio_manifest.json      音声生成の中間ファイル
└── tools/
    ├── build_audio_manifest.py   index.html から英文を抽出しマニフェスト生成
    ├── make_audio.py             マニフェストから mp3 を生成（edge-tts）
    ├── check_pronunciation.py    発音の自動点検（faster-whisper）
    ├── try_pron.py / try_voices.py / export_word_audio.py   発音調査用
    └── purge_for_voice.py        声を変えたとき用の削除
```

## index.html の扱い（重要）

esbuild で圧縮済みの巨大な1行を含む。**手で編集しない。**
変更するときは Python か Node のスクリプトで文字列置換・配列再生成を行う。

データ配列の変数名（すべて `<script>` 内）:

| 変数 | 内容 | id接頭辞 | 件数 |
|---|---|---|---|
| `Ot` | 単語・熟語 | w | 390 |
| `xd` | 覚え方ヒント（語→解説のマップ） | — | 390 |
| `_d` | 文法・空所 | c | 75 |
| `Td` | 会話文 | d | 60 |
| `Nd` | 会話リスニング | l | 80 |
| `zd` | 英作文の型 | t | 50 |
| `Yp` / `Vr` | 長文の本文 / 設問 | r | 15本 / 45問 |
| `Lr` | 面接カード | i | 32 |

- 日本語は `\uXXXX` 形式でエスケープされている。追加時も同形式にすること
- オブジェクトのキーは**引用符なし**（`{lines:[...],sp:[...]}`）。
  `JSON.stringify` で書き戻すと `build_audio_manifest.py` が英文を拾えなくなる
- 編集後は必ず `<script>` を抽出して `node --check` で構文検証する
- 動作確認は jsdom（`npm install jsdom`）でヘッドレス実行できる

## 音声システム

- ファイル名 = 英文のハッシュ値（`Au()` 関数。JS と Python に同一実装）
- 会話リスニングのみ「話者記号|本文」をハッシュ対象にする（例 `K|I'm home, Mom.`）
- 声: 文は `en-US-JennyNeural`、会話は M=Guy / F=Jenny / K=Ana（-20Hz）
- 単語は Jenny。ただし Jenny が語頭の v を弱く読むため、
  v で始まる6語と `cause` のみ `en-US-MichelleNeural`（`make_audio.py` の `VOICE_FOR`）
- **手順を守ること**: `build_audio_manifest.py` → `make_audio.py` の順。
  マニフェストに無い mp3 は `make_audio.py` が自動削除する。
  マニフェスト生成時の合計が 2078 前後でなければ、そこで止める

## これからやること（Androidアプリ化）

1. ~~Capacitor でラップして Android アプリにする~~（済: Capacitor 8.5.0 導入・Androidビルド成功）
2. AdMob でバナー広告を表示する
3. ユーザーが時刻を設定できる学習リマインド通知
4. Google Play で公開

### Android プロジェクトの構成（導入済み）

- appId: `com.mac328.eikendojo` / アプリ表示名: `反復トレ`
- webDir は `www/`。`npm run sync:www`（`scripts/copy-www.js`）で
  ルートの `index.html` と `audio/` を `www/` へコピーして生成する
- `www/` は生成物なので `.gitignore` 済み。コミットしない
- ビルド: `npm run cap:sync` → `android/gradlew assembleDebug`
- JDK は Android Studio 同梱の JBR 21 を `JAVA_HOME` に設定して使う
  （PATH 上の JDK 26 は AGP と非互換の可能性があるため使わない）

### 実機で確認済み（Android 12 / A201OP）

- 音声: `audio/` の相対パスはそのまま動く。WebView は `https://localhost/` から
  読み込み、APK 内の `assets/public/audio/` に解決される。mp3 2078本を同梱（APK 33MB）
- 進捗: `localStorage` はアプリを完全終了しても保持される
- Capacitor が WebView 側を自動設定するため、追加の対応は不要
  （`setDomStorageEnabled(true)` と `setMediaPlaybackRequiresUserGesture(false)`）

### やってはいけないこと

**`capacitor.config.json` の `androidScheme` を変更しない。**
localStorage は `https://localhost` というオリジンに紐づいて保存される。
スキームを変えるとオリジンが変わり、**利用者の進捗がすべて消える。**
公開後の変更は特に厳禁。

### 方針

- **Web版を壊さない。** GitHub Pages は今のまま動き続ける必要がある。
  `index.html` と `audio/` はルートに置いたまま、Capacitor の webDir は `www/` とし、
  ビルド前にルートから `www/` へコピーするスクリプトを用意する
- アプリ固有の処理（広告・通知）は、Web版では動かないので
  `Capacitor.isNativePlatform()` で分岐させ、Web版の動作に影響を与えない
- 音声はアプリに同梱する（オフラインで使えるようにする）

### 対象年齢と広告の方針（決定済み）

- **対象年齢は「13歳以上」として申告する。** Families ポリシーの対象外とし、
  13歳未満向けの配信はしない
- **広告はバナーのみ。** インタースティシャルやリワード広告は入れない
- 主な利用者は中高生なので、AdMob の広告内容フィルタは厳しめに設定する
- 学習の妨げにならないよう、バナーの表示位置は問題の解答操作に
  かぶらない場所にする

## 設計思想

トップの進捗ゲージは「ゴール」ではなく**「今どのくらい身についたかの目安」**。
100%到達を目指して問題数を絞るのは本末転倒で、収録問題数は多いほど指標として正確になる。

## SRS（間隔反復）の仕様

- 間隔: `[1分, 10分, 1日, 3日, 7日, 14日, 30日]`（box 0〜6）
- 保存形式: `srs[問題id] = [box, 次回出題時刻(ms), 到達した最高box]`
- 正解で box+1、不正解で box0。習得判定は box5 以上
- 長文のみセッション内リトライを行わず、3問1組を分割しない

## コミュニケーション

- 日本語で回答する
- 技術的な説明が分かりにくいときは、平易な言葉で言い直す
- 音声の発音の正しさは AI では判定できない。必ず作者の耳で確認してもらう
