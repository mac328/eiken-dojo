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

console.log(`www/ を再生成しました（${wwwDir}）`);
