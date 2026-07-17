#!/usr/bin/env python3
"""Wave-7 Raven bridge PoC smoke."""
from __future__ import annotations
import argparse, asyncio, json
from pathlib import Path
from memory_bridge import make_backend

async def run_smoke(repo_root: Path) -> int:
    b = make_backend(repo_root)
    await b.start()
    try:
        await b.store('wave7', [{'role':'user','content':'hello'}], user_id='u')
        await b.feedback({'action':'smoke','status':'ok'})
        hits=await b.recall('hello', user_id='u', top_k=3)
        print(json.dumps({'status':'ok','repo':repo_root.name,'hits':[{'text':h.text,'score':h.score,'metadata':h.metadata} for h in hits]}, ensure_ascii=False, indent=2))
        return 0
    finally:
        await b.stop()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument('--repo', default=str(Path.cwd()))
    p.add_argument('--smoke', action='store_true')
    ns=p.parse_args()
    if not ns.smoke:
        print('请带 --smoke')
        return 0
    return asyncio.run(run_smoke(Path(ns.repo).resolve()))

if __name__=='__main__':
    raise SystemExit(main())
