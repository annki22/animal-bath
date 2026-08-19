// roll_sim.js — rollLevel 纯逻辑模拟器（从 动物泡澡-手搓版-v4.html 逐行复刻）
// 2026-08-20 v4.9.15: 同步「纯概率回归 + 1/2 后期保底」——删 r7 让位/r9 补配对（棋盘感知被否），
//   p1T: 11%→8%（保底，1 是唯一不可合成数字，后期断供=玩家干等 1）
//   p2T: 25%→5%（保底，2 可由 1+1 合成，需求低于 1）
// 运行: node scripts/roll_sim.js

// 复刻 rollLevel：dropCount 注入，rand 可替换（v4.9.15 起不依赖棋盘状态）
function makeRollLevel(dropCount){
  return function rollLevel(rand){
    const d = Math.min(1, dropCount / 100);   // 进度 0→1（100 投到顶）
    const maxMid = dropCount >= 25 ? 6 : 5;   // v4.2 节奏：开局 25 投内只掉 1-5，之后 6 常驻
    const center = 3.4 + d * 0.8;             // 重心 3.4 → 4.2
    const sigma = 1.15 + d * 0.3;             // 后期分布略宽
    let p1T = 0.11 + (0.08 - 0.11) * d;   // 11% → 8%（保底）
    let p2T = 0.25 + (0.05 - 0.25) * d;   // 25% → 5%（保底）
    const w = [0, 0];
    const lv = [1, 2];
    let s36 = 0;
    for (let i = 3; i <= maxMid; i++){
      const dist = Math.abs(i - center);
      let weight = Math.exp(-(dist * dist) / (2 * sigma * sigma));
      if (i === 3) weight += 0.45;
      weight = Math.max(weight, 0.05);
      w.push(weight); lv.push(i);
      s36 += weight;
    }
    const p7 = dropCount >= 25 ? 0.04 : 0;
    const anchor = s36 / (1 - p1T - p2T - p7);
    w[0] = p1T * anchor;
    w[1] = p2T * anchor;
    if (p7 > 0){ w.push(p7 * anchor); lv.push(7); }
    const total = w.reduce((a,b)=>a+b, 0);
    let r = rand() * total;
    for (let i = 0; i < w.length; i++){
      r -= w[i];
      if (r <= 0) return lv[i];
    }
    return lv[w.length - 1] || 3;
  };
}

// 场景: [名称, dropCount, 期望断言 {等级: [min%, max%] 或 0=必须为0}]
const scenarios = [
  // 理论值：p1T = 0.11-0.03d，p2T = 0.25-0.20d，p7 = 25投后 4%
  ['开局 0投 (1≈11% 2≈25% 无6/7)', 0, {'1': [10.7, 11.3], '2': [24.7, 25.3], '6': 0, '7': 0}],
  ['25投 (1≈10.3% 2≈20% 7=4% 6解锁)', 25, {'1': [9.9, 10.6], '2': [19.7, 20.3], '7': [3.7, 4.3]}],
  ['50投 (1≈9.5% 2≈15%)', 50, {'1': [9.2, 9.8], '2': [14.7, 15.3], '7': [3.7, 4.3]}],
  ['100投保底 (1=8% 2=5% 不再下降)', 100, {'1': [7.7, 8.3], '2': [4.7, 5.3], '7': [3.7, 4.3]}],
  ['150投仍保底 (1=8% 2=5%)', 150, {'1': [7.7, 8.3], '2': [4.7, 5.3]}],
  ['200投仍保底 (1=8% 2=5%)', 200, {'1': [7.7, 8.3], '2': [4.7, 5.3]}],
];

const N = 300000;
let pass = 0, fail = 0;
for (const [name, dropCount, assert] of scenarios){
  const roll = makeRollLevel(dropCount);
  const counts = {};
  for (let i = 0; i < N; i++){
    const v = roll(Math.random);
    counts[v] = (counts[v] || 0) + 1;
  }
  const pct = (lv) => (counts[lv] || 0) / N;
  let ok = true, msg = '';
  for (const [lv, expect] of Object.entries(assert)){
    const got = pct(+lv);
    if (expect === 0){ if (got !== 0){ ok = false; msg += ` lv${lv}=${(got*100).toFixed(2)}% 应为0`; } }
    else {
      const [lo, hi] = expect;
      const g = got * 100;
      if (g < lo || g > hi){ ok = false; msg += ` lv${lv}=${g.toFixed(2)}% 应在[${lo},${hi}]`; }
    }
  }
  // 8+ 永不掉落
  let hi8 = 0;
  for (let k = 8; k <= 20; k++) hi8 += counts[k] || 0;
  if (hi8 > 0){ ok = false; msg += ` 8+=${(hi8/N*100).toFixed(3)}% 应=0`; }
  const dist = Object.keys(counts).sort((a,b)=>a-b).map(lv => `${lv}:${(pct(+lv)*100).toFixed(1)}%`).join(' ');
  if (ok){ pass++; console.log(`PASS ${name} | ${dist}`); }
  else { fail++; console.log(`FAIL ${name} | ${dist}${msg}`); }
}
console.log(`\n${pass}/${pass+fail} 场景通过`);
process.exit(fail > 0 ? 1 : 0);
