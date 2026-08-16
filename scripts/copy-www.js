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
console.log("  ads.js を差し込みました（アプリ版のみ）");
