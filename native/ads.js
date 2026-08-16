/* AdMob の 広告を あつかいます（アプリ版だけ）。
 *
 * このファイルは www/ にだけ コピーされ、GitHub Pages の Web版には
 * 入りません（scripts/copy-www.js が コピーと 読みこみを 行います）。
 * そのため Web版の うごきには 影響しません。
 *
 * index.html 側は 次の 2か所を 呼ぶだけです。どちらも
 * window.EikenAds が 無ければ 何も せず 素どおりします。
 *   ・1セット終わったとき   EikenAds.onSetEnd()
 *   ・面接に 入るとき       EikenAds.gateInterview(つづきの処理)
 */
(function () {
  "use strict";

  // ===== 設定 =====================================================
  var IDS = {
    interstitial: "ca-app-pub-4259051521565413/9739888055", // セット終了時
    reward: "ca-app-pub-4259051521565413/3174479709",       // 面接の解放
  };

  // 開発中は かならず true。テスト広告(「Test Ad」の 印つき)だけが 出ます。
  // 自分の 広告を さわると 無効な アクティビティと 判定され、
  // アカウントが 止められる おそれが あるためです。
  // 公開する ときだけ false に します。
  var DEV = true;

  // テスト端末の 識別子。logcat に 出る 文字列を ここに 足すと、
  // 本物の 広告ユニットIDの まま テスト広告に なります。
  var TEST_DEVICES = [];

  // インタースティシャルを 出す 最短の 間かく（ミリ秒）。
  // 立て続けに 出すと 学習の じゃまに なり、
  // AdMob の ポリシー違反にも なりえます。
  var MIN_GAP_MS = 3 * 60 * 1000;

  // 面接の 解放を おぼえておく キー。
  // 本体の 進捗(eikenP2v1)とは 分けます。壊さないためです。
  var UNLOCK_KEY = "eikenP2_iv_unlock";

  // ===== ここから 実装 =============================================
  var C = window.Capacitor;
  if (!C || !C.isNativePlatform || !C.isNativePlatform()) return; // Web版は 何も しない
  var AdMob = C.Plugins && C.Plugins.AdMob;
  if (!AdMob) return;

  var lastShown = 0;
  var interstitialReady = false;
  var ready = false;

  function log() {
    var a = ["[ads]"].concat([].slice.call(arguments));
    console.log.apply(console, a);
  }

  function today() {
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }

  // ---- 初期化 ----------------------------------------------------
  AdMob.initialize({
    initializeForTesting: DEV,
    testingDevices: TEST_DEVICES,
    // 13歳未満向けでは ないので false。
    tagForChildDirectedTreatment: false,
    // 利用者は 中高生。広告の 内容を しぼります。
    maxAdContentRating: "Teen",
  })
    .then(function () {
      ready = true;
      log("初期化しました DEV=" + DEV);
      prepareInterstitial();
    })
    .catch(function (e) {
      log("初期化に失敗:", e && e.message ? e.message : e);
    });

  // ---- インタースティシャル（1セット終了時）----------------------
  function prepareInterstitial() {
    if (!ready) return;
    AdMob.prepareInterstitial({ adId: IDS.interstitial, isTesting: DEV })
      .then(function () {
        interstitialReady = true;
        log("インタースティシャルの用意ができました");
      })
      .catch(function (e) {
        interstitialReady = false;
        log("インタースティシャルの用意に失敗:", e && e.message ? e.message : e);
      });
  }

  function onSetEnd() {
    if (!ready || !interstitialReady) return;
    var now = Date.now();
    if (now - lastShown < MIN_GAP_MS) {
      log("前回から間がないので出しません");
      return;
    }
    lastShown = now;
    interstitialReady = false;
    AdMob.showInterstitial()
      .then(function () {
        log("インタースティシャルを表示しました");
      })
      .catch(function (e) {
        log("表示に失敗:", e && e.message ? e.message : e);
      })
      .then(function () {
        setTimeout(prepareInterstitial, 1000); // つぎの ぶんを 用意
      });
  }

  // ---- リワード（面接の解放）------------------------------------
  function unlockedToday() {
    try {
      return localStorage.getItem(UNLOCK_KEY) === today();
    } catch (e) {
      return false;
    }
  }

  function markUnlocked() {
    try {
      localStorage.setItem(UNLOCK_KEY, today());
    } catch (e) {
      /* 保存できなくても 進めます */
    }
  }

  /* 広告を 見るかどうかを たずねる 画面。
   *
   * AdMob の きまりで、リワード広告は 利用者が はっきり
   * 「はい」を えらんだ あとでしか 出せません。
   * 面接ボタンは「面接を はじめる」ボタンであって
   * 「広告に 同意する」ボタンでは ないので、ここで たずねます。
   * https://support.google.com/admob/answer/7313578 */
  function askOptIn(onYes, onNo) {
    var C1 = "#FBF7EE", INK = "#3B2A06", GOLD = "#F59E0B", SUB = "#8A7A5C";

    var back = document.createElement("div");
    back.setAttribute("style", [
      "position:fixed", "inset:0", "z-index:2147483000",
      "background:rgba(0,0,0,.45)",
      "display:flex", "align-items:center", "justify-content:center",
      "padding:24px", "box-sizing:border-box",
      "font-family:'Zen Maru Gothic',sans-serif",
    ].join(";"));

    var box = document.createElement("div");
    box.setAttribute("style", [
      "background:" + C1, "color:" + INK,
      "border-radius:18px", "padding:22px 20px",
      "max-width:340px", "width:100%",
      "box-shadow:0 8px 30px rgba(0,0,0,.25)",
    ].join(";"));

    var h = document.createElement("div");
    h.textContent = "面接練習を解放しますか？";
    h.setAttribute("style", "font-size:18px;font-weight:700;margin-bottom:12px;");

    var p = document.createElement("div");
    p.setAttribute("style", "font-size:14px;line-height:1.7;color:" + SUB + ";margin-bottom:18px;");
    p.textContent =
      "面接は二次試験向けのおまけの機能です。" +
      "動画広告を最後まで見ると、今日は何度でも練習できます。";

    var yes = document.createElement("button");
    yes.textContent = "広告を見て解放";
    yes.setAttribute("style", [
      "width:100%", "padding:13px", "margin-bottom:8px",
      "background:" + GOLD, "color:" + INK,
      "border:none", "border-radius:12px",
      "font-size:16px", "font-weight:700",
      "font-family:inherit", "cursor:pointer",
    ].join(";"));

    var no = document.createElement("button");
    no.textContent = "やめる";
    no.setAttribute("style", [
      "width:100%", "padding:11px",
      "background:transparent", "color:" + SUB,
      "border:none", "border-radius:12px",
      "font-size:15px", "font-family:inherit", "cursor:pointer",
    ].join(";"));

    function close() {
      if (back.parentNode) back.parentNode.removeChild(back);
    }
    yes.onclick = function () { close(); onYes(); };
    no.onclick = function () { close(); onNo(); };
    // 背景を さわった ときも「やめる」あつかいに します
    back.onclick = function (e) { if (e.target === back) { close(); onNo(); } };

    box.appendChild(h);
    box.appendChild(p);
    box.appendChild(yes);
    box.appendChild(no);
    back.appendChild(box);
    document.body.appendChild(back);
  }

  /* 面接に 入る まえに 呼ばれます。
   * go() を 呼べば 面接が はじまります。
   *
   * 通信できない ときや 広告が 用意できない ときは そのまま 通します。
   * 広告を 出せない のは こちらの 都合であって、
   * 学習者を しめ出す 理由に ならないためです。 */
  function gateInterview(go) {
    if (typeof go !== "function") return;
    if (unlockedToday()) {
      log("今日はもう解放ずみ");
      go();
      return;
    }
    if (!ready) {
      log("初期化前なので、そのまま通します");
      go();
      return;
    }
    // ここで かならず 同意を とってから 広告を 出します
    askOptIn(
      function () { showRewardThenGo(go); },
      function () { log("やめるが押されました"); }
    );
  }

  function showRewardThenGo(go) {
    var done = false;
    function finish(reason) {
      if (done) return;
      done = true;
      log("面接へ:", reason);
      go();
    }

    // 広告が 出ない まま 待たせ続けない ための 保険
    var guard = setTimeout(function () {
      finish("時間切れのため解放");
    }, 12000);

    AdMob.prepareRewardVideoAd({ adId: IDS.reward, isTesting: DEV })
      .then(function () {
        return AdMob.showRewardVideoAd();
      })
      .then(function (reward) {
        clearTimeout(guard);
        markUnlocked(); // 今日ぶん 解放
        finish("報酬をうけとりました " + JSON.stringify(reward || {}));
      })
      .catch(function (e) {
        clearTimeout(guard);
        // 広告が 無い・通信できない・利用者が 途中で とじた
        log("リワードを出せませんでした:", e && e.message ? e.message : e);
        finish("広告を出せないため解放");
      });
  }

  window.EikenAds = {
    onSetEnd: onSetEnd,
    gateInterview: gateInterview,
    // 動作確認用
    _state: function () {
      return {
        ready: ready,
        interstitialReady: interstitialReady,
        unlockedToday: unlockedToday(),
        DEV: DEV,
      };
    },
  };

  log("よみこみました");
})();
