#!/usr/bin/env python3
"""CDP regression suite for the five P0 fixes and core gameplay smoke tests."""
import json
import pathlib
import time
import urllib.request

import websocket

ROOT = pathlib.Path(__file__).resolve().parents[1]
CDP = "http://127.0.0.1:9222"
BASE = "http://127.0.0.1:8899"


class Browser:
    def __init__(self):
        req = urllib.request.Request(CDP + "/json/new?about:blank", method="PUT")
        tab = json.loads(urllib.request.urlopen(req, timeout=5).read())
        self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"], timeout=15, suppress_origin=True)
        self.mid = 0
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Page.addScriptToEvaluateOnNewDocument", {"source": """
          window.__xss = 0;
          window.fetch = async function(url) {
            const u = String(url);
            if (u.includes('/scores?')) return new Response(JSON.stringify([
              {nickname:'<img src=x onerror=window.__xss=1>',score:123,max_level:4,created_at:new Date().toISOString()}
            ]), {status:200,headers:{'Content-Type':'application/json'}});
            if (u.includes('/saves?')) return new Response('[]', {status:200,headers:{'Content-Type':'application/json'}});
            if (u.includes('/rpc/events_agg')) return new Response('{}', {status:200,headers:{'Content-Type':'application/json'}});
            return new Response('{}', {status:200,headers:{'Content-Type':'application/json'}});
          };
        """})

    def call(self, method, params=None):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                return msg.get("result", {})

    def eval(self, expression):
        out = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if out.get("exceptionDetails"):
            raise RuntimeError(json.dumps(out["exceptionDetails"], ensure_ascii=False))
        return out.get("result", {}).get("value")

    def go(self, path):
        self.call("Page.navigate", {"url": BASE + path + "?t=" + str(time.time_ns())})
        time.sleep(0.8)


def saved_state(reorg, undo, hammer):
    return {"stacks": [[1] * 7, [], [], [], []], "score": 10, "dropCount": 7,
            "nextQueue": [1, 2], "maxLevel": 1, "nickname": "p0-test", "ver": "v5.9.17",
            "reorgLeft": reorg, "undoLeft": undo, "hammerLeft": hammer}


def main():
    b = Browser()
    results = []
    try:
        b.go("/index.html")

        # P0-1: an overflow restore with nominal undo count but no in-memory snapshot must end.
        state = json.dumps(saved_state(0, 2, 0), ensure_ascii=False)
        b.eval(f"localStorage.setItem('animalBathNick','p0-test');localStorage.setItem('animalBathSave',{json.dumps(state)});location.reload()")
        time.sleep(0.9)
        b.eval("document.getElementById('nameContinue').click()")
        time.sleep(0.9)
        p01 = b.eval("({rescue:rescueOverlay.classList.contains('show'),save:localStorage.getItem('animalBathSave'),rank:rankOverlay.classList.contains('show')})")
        results.append(("P0-1", not p01["rescue"] and p01["save"] is None, p01))

        # P0-2: an old drop finalizer must not clear the busy lock belonging to a new generation.
        b.eval("document.querySelectorAll('.overlay.show').forEach(x=>x.classList.remove('show'));__animalBathTest.startNewGame();__animalBathTest.setState({nextQueue:[1,2]});__animalBathTest.drop(0);__animalBathTest.startNewGame();__animalBathTest.setBusy(true)")
        time.sleep(0.9)
        p02 = b.eval("__animalBathTest.getState()")
        results.append(("P0-2", p02["busy"] is True and p02["gen"] >= 2, p02))

        # P0-3: numeric keydown while rescue modal is open cannot mutate the board.
        b.eval("__animalBathTest.setBusy(false);__animalBathTest.setState({stacks:[[1,1,1,1,1,1,1],[],[],[],[]],nextQueue:[2,3],reorgLeft:1,undoLeft:0,hammerLeft:0});document.getElementById('rescueOverlay').classList.add('show')")
        before = b.eval("__animalBathTest.getState().stacks")
        b.eval("document.dispatchEvent(new KeyboardEvent('keydown',{key:'1',bubbles:true}))")
        time.sleep(0.4)
        after = b.eval("__animalBathTest.getState().stacks")
        results.append(("P0-3", before == after, {"before": before, "after": after}))

        # P0-4: SQL is present, enables all tables, and grants anon only INSERT on events.
        sql = (ROOT / "scripts/enable_rls.sql").read_text()
        p04 = all(f"alter table public.{t} enable row level security" in sql.lower() for t in ("scores", "saves", "events")) and "grant insert on table public.events to anon" in sql.lower() and "grant select" not in sql.lower()
        results.append(("P0-4", p04, "static SQL review; script was not executed"))

        # P0-5: malicious nickname renders literally and creates no img/onerror execution.
        b.go("/dashboard-v2.html")
        time.sleep(0.8)
        p05 = b.eval("({text:document.querySelector('#playerTable tbody tr td:nth-child(2)')?.textContent,imgs:document.querySelectorAll('#playerTable tbody img').length,xss:window.__xss})")
        dashboard_sources = (ROOT / "dashboard-v2.html").read_text() + (ROOT / "dashboard.html").read_text()
        p05_ok = p05["text"] == "<img src=x onerror=window.__xss=1>" and p05["imgs"] == 0 and p05["xss"] == 0 and "DASH_PASS" not in dashboard_sources and "bath2026" not in dashboard_sources
        results.append(("P0-5", p05_ok, p05))

        # Gameplay smoke: drop, adjacent merge, undo, reorg, hammer, leaderboard, restore.
        b.go("/index.html")
        b.eval("document.querySelectorAll('.overlay.show').forEach(x=>x.classList.remove('show'));__animalBathTest.startNewGame();__animalBathTest.setState({nextQueue:[1,2]});__animalBathTest.drop(0)")
        time.sleep(0.9)
        normal = b.eval("__animalBathTest.getState().stacks[0].length===1")
        b.eval("__animalBathTest.setState({stacks:[[1],[],[],[],[]],nextQueue:[1,2],busy:false});__animalBathTest.drop(0)")
        time.sleep(1.3)
        merge = b.eval("JSON.stringify(__animalBathTest.getState().stacks[0])==='[2]'")
        b.eval("__animalBathTest.setState({stacks:[[],[],[],[],[]],nextQueue:[2,3],undoLeft:2,busy:false});__animalBathTest.drop(0)")
        time.sleep(0.9)
        b.eval("__animalBathTest.doUndo()")
        undo = b.eval("__animalBathTest.getState().stacks[0].length===0")
        b.eval("__animalBathTest.setState({stacks:[[3,1],[2,1],[],[],[]],reorgLeft:1,busy:false});__animalBathTest.doReorg({c0:0,c1:1,r0:0,r1:1})")
        time.sleep(1.2)
        reorg = b.eval("__animalBathTest.getState().reorgLeft===0")
        b.eval("__animalBathTest.setState({stacks:[[1,2],[],[],[],[]],hammerLeft:1,busy:false});__animalBathTest.doHammer(0,0)")
        time.sleep(1.1)
        hammer = b.eval("JSON.stringify(__animalBathTest.getState().stacks[0])==='[2]' && __animalBathTest.getState().hammerLeft===0")
        b.eval("document.getElementById('rankBtn').click()")
        time.sleep(0.8)
        rank = b.eval("rankOverlay.classList.contains('show') && !document.getElementById('rankLoading').offsetParent")
        smoke = {"normal_drop": normal, "adjacent_merge": merge, "undo": undo, "reorg": reorg, "hammer": hammer, "leaderboard": rank, "save_restore": results[0][1]}
        results.append(("SMOKE", all(smoke.values()), smoke))
    finally:
        b.ws.close()

    for name, passed, evidence in results:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {json.dumps(evidence, ensure_ascii=False)}")
    if not all(passed for _, passed, _ in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
