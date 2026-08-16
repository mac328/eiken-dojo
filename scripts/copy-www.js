// ルート直下の index.html と audio/ を www/ へコピーする。
// www/ は Capacitor のビルド対象（webDir）。GitHub Pages 公開用のルートは触らない。
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const wwwDir = path.join(root, "www");

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    fs.copyFileSync(src, dest);
  }
}

fs.rmSync(wwwDir, { recursive: true, force: true });
fs.mkdirSync(wwwDir, { recursive: true });

copyRecursive(path.join(root, "index.html"), path.join(wwwDir, "index.html"));
copyRecursive(path.join(root, "audio"), path.join(wwwDir, "audio"));

// アプリ版だけの処理（広告）を差し込む。
// native/ads.js は www/ にしか置かないので、GitHub Pages の Web版には
// 一切入らない。index.html 側のフックは window.EikenAds が無ければ
// 素どおりするので、Web版の動作は変わらない。
copyRecursive(path.join(root, "native", "ads.js"), path.join(wwwDir, "ads.js"));

// --release を付けたときだけ、広告をテストから本番に切りかえる。
// 手で書きかえる運用にすると「戻し忘れ」で
//   ・開発中に本物の広告に触れてアカウント停止
//   ・公開したのにテスト広告のままで収益ゼロ
// という事故が起きるので、ビルドの種類で自動的に決まるようにする。
// 元の native/ads.js は DEV=true のまま変えない。
const isRelease = process.argv.includes("--release");
const adsPath = path.join(wwwDir, "ads.js");
let ads = fs.readFileSync(adsPath, "utf8");
const DEV_TRUE = "var DEV = true;";
const DEV_FALSE = "var DEV = false;";
if (!ads.includes(DEV_TRUE)) {
  throw new Error(`native/ads.js に "${DEV_TRUE}" が見つからない（想定外）`);
}
if (isRelease) {
  ads = ads.replace(DEV_TRUE, DEV_FALSE);
  fs.writeFileSync(adsPath, ads);
}

const indexPath = path.join(wwwDir, "index.html");
let html = fs.readFileSync(indexPath, "utf8");
const tag = '<script src="ads.js"></script>';
if (html.includes(tag)) {
  throw new Error("ads.js の読み込みが既にある（想定外）");
}
if (!html.includes("</body>")) {
  throw new Error("</body> が見つからないので ads.js を差し込めない");
}
html = html.replace("</body>", `${tag}\n</body>`);
fs.writeFileSync(indexPath, html);

console.log(`www/ を再生成しました（${wwwDir}）`);
console.log(
  isRelease
    ? "  ads.js を差し込みました（★本番の広告★ DEV=false）"
    : "  ads.js を差し込みました（テスト広告 DEV=true）"
);
