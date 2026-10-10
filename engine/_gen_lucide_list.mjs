// engine/_gen_lucide_list.mjs
// 从 engine/eink_assets/lucide.umd.min.js 提取全部 lucide 图标名（含别名）的 kebab-case 白名单，
// 写入 engine/eink_assets/lucide_icons.txt（一行一个，字典序）。
// 用途：eink 的 lint_outline.py（ic= 校验）与 render_outline.py（未知图标兜底警告）的数据源。
// 重跑时机：升级 engine/eink_assets/lucide.umd.min.js 后，用 node 跑本脚本刷新白名单。
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const umd = path.join(here, 'eink_assets', 'lucide.umd.min.js');
const out = path.join(here, 'eink_assets', 'lucide_icons.txt');

const code = fs.readFileSync(umd, 'utf8');

// umd 形如 (function(global, factory){ typeof exports==='object' && typeof module!=='undefined' ? factory(exports) : ... })(this, function(exports){ ... })
// 用 new Function 提供 exports/module/window 等形参，让 umd 走 CommonJS 分支（factory(exports)）注册图标。
const mod = { exports: {} };
let lib;
try {
  const fn = new Function('exports', 'module', 'window', 'document', 'navigator', 'self', 'globalThis', code);
  fn(mod.exports, mod, undefined, undefined, undefined, undefined, undefined);
  lib = mod.exports;
} catch (e1) {
  try {
    const fn2 = new Function('exports', 'module', 'window', 'document', 'navigator', 'self',
      code + '\n;return (typeof lucide!=="undefined") ? lucide : exports;');
    lib = fn2(mod.exports, mod, undefined, undefined, undefined, undefined);
  } catch (e2) {
    console.error('[gen] umd 解析失败:', e2.message);
    process.exit(1);
  }
}

const names = new Set();
const collect = (obj) => { if (obj && typeof obj === 'object') Object.keys(obj).forEach((n) => names.add(n)); };
collect(lib.icons);
collect(lib.aliases);
if (lib.default) { collect(lib.default.icons); collect(lib.default.aliases); }
// 兜底：exports 顶层 PascalCase 键（图标导出对象）
Object.keys(lib).forEach((n) => { if (/^[A-Z][A-Za-z0-9]*$/.test(n) && n !== 'createIcons') names.add(n); });

const kebab = (s) => s
  .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
  .replace(/([A-Z]+)([A-Z][a-z])/g, '$1-$2')
  .toLowerCase();

const list = [...names].map(kebab).filter(Boolean).sort();
fs.writeFileSync(out, list.join('\n') + '\n', 'utf8');
console.log('[gen] 提取 lucide 图标名 %d 个 -> %s', list.length, out);
