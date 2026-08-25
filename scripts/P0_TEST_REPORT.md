# P0 修复本地验证报告

- 日期：2026-08-26（Asia/Shanghai）
- 页面：`http://127.0.0.1:8899`
- 浏览器：Chrome CDP，`--remote-debugging-port=9222`
- 脚本：`python3 scripts/test_p0_regressions.py`
- 总结：5 个 P0 与玩法冒烟全部通过。

| 项目 | 结果 | 证据 |
|---|---|---|
| P0-1 越线救场死锁 | PASS | 注入越线存档（`undoLeft=2`、恢复后 `undoStack=[]`、整理/锤子均为 0）；续玩后未进入救场弹窗，存档被清除并正常进入结算排行榜。 |
| P0-2 跨局异步 busy | PASS | 旧局 `drop()` 回调挂起后开启新局并设置新局 `busy=true`；旧回调结束后 `gen=2` 且 `busy` 仍为 `true`。 |
| P0-3 modal 键盘投子 | PASS | 救场弹窗打开时派发数字键 `1`；前后棋盘均为 `[[1,1,1,1,1,1,1],[],[],[],[]]`。 |
| P0-4 RLS 脚本 | PASS | 静态检查确认三表均启用 RLS，匿名角色在 `events` 上仅获 INSERT；脚本未执行。 |
| P0-5 看板 XSS/口令 | PASS | 昵称 `<img src=x onerror=window.__xss=1>` 以原样文本显示，表格内 `img=0`、`window.__xss=0`；两个看板均无 `DASH_PASS`/旧口令。 |

## 冒烟结果

| 场景 | 结果 |
|---|---|
| 正常落子 | PASS |
| 相邻合成 | PASS |
| 整理 | PASS |
| 撤回 | PASS |
| 锤子 | PASS |
| 排行榜加载 | PASS |
| 本地存档续玩路径 | PASS |

附加检查：四个 HTML 文件的内联 JavaScript 均通过 `node --check`；`index.html` 与 `动物泡澡-手搓版-v4.html` 字节一致。
