from __future__ import annotations

import json, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from trendspyg import download_google_trends_interest_over_time

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/'config/settings.json'; DATA=ROOT/'data'; REPORTS=ROOT/'reports'

def load(p,d):
 try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
 except Exception:return d

def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

def parse_dt(s):
 d=datetime.fromisoformat(str(s).replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def history_summary(keyword,geo,cfg):
 series=download_google_trends_interest_over_time(keyword,geo=geo or '',timeframe=cfg.get('history_timeframe','today 5-y'),max_retries=2,retry_wait=6,cache='disk',cookies='disk',engine='auto')
 cutoff=datetime.now(timezone.utc)-timedelta(days=120)
 old=[]
 for p in series:
  try:
   d=parse_dt(p['date']); v=int(p.get('value',0) or 0)
   if d<cutoff: old.append(v)
  except Exception: pass
 if not old:return {'historically_new':None,'old_avg':None,'old_peak':None,'old_nonzero_ratio':None,'points':0}
 avg=round(sum(old)/len(old),2); peak=max(old); nz=round(sum(v>0 for v in old)/len(old),3)
 material_threshold=int(cfg.get('history_material_threshold',5)); material_ratio=round(sum(v>=material_threshold for v in old)/len(old),3)
 ok=avg<=cfg.get('max_history_avg',0.5) and peak<=cfg.get('max_history_peak',8) and material_ratio<=cfg.get('max_history_material_ratio',0.03)
 return {'historically_new':ok,'old_avg':avg,'old_peak':peak,'old_nonzero_ratio':nz,'old_material_ratio':material_ratio,'material_threshold':material_threshold,'points':len(old)}

def make_report(payload):
 lines=['# New Keyword Radar — Latest','',f"Generated: {payload['generated_at']}",'','## Formal candidates','']
 if not payload['formal_candidates']:lines.append('**今日无合格可变现新词。**')
 for i,x in enumerate(payload['formal_candidates'],1):
  h=x.get('history_5y',{})
  lines += [f"### {i}. {x['keyword']}",'',f"- Newness **{x['newness_score']}/100**; money **{x['money_score']}/100** ({x['money_type']}).",f"- 90d baseline avg **{x.get('baseline_avg')}**, recent peak **{x.get('recent_peak')}**, first rise {x.get('first_rise_date')}, retention **{x.get('retention_pct')}%**.",f"- 5y old-history gate: avg **{h.get('old_avg')}**, peak **{h.get('old_peak')}**, material ratio (>= {h.get('material_threshold')}) **{h.get('old_material_ratio')}**; raw non-zero ratio **{h.get('old_nonzero_ratio')}**.",f"- Source {x['source']}; geo {x['geo'] or 'Worldwide'}.",'']
 lines += ['## Watch / rejected','']
 for x in payload['all_checked']:
  if x['verdict']!='formal':
   h=x.get('history_5y',{}); extra=f"; 5y peak {h.get('old_peak')}" if h else ''
   lines.append(f"- {x['keyword']} — **{x['verdict']}** — newness {x['newness_score']}, money {x['money_score']}{extra}"+(f" — {x['error']}" if x.get('error') else ''))
 return '\n'.join(lines)+'\n'

def main():
 cfg=load(CFG,{}); payload=load(DATA/'latest.json',{}); provisional=list(payload.get('formal_candidates',[])); limit=int(cfg.get('max_history_checks_per_run',2)); checked=0
 by_keyword={x.get('keyword'):x for x in payload.get('all_checked',[])}
 for x in provisional:
  if checked>=limit:
   x['verdict']='history-unchecked'; by_keyword.get(x.get('keyword'),{}).update(x); continue
  try:
   h=history_summary(x['keyword'],x.get('geo',''),cfg); x['history_5y']=h; checked+=1
   if h.get('historically_new') is not True:
    x['true_new_90d']=x.get('true_new'); x['true_new']=False; x['verdict']='old-history' if h.get('historically_new') is False else 'history-unknown'
   by_keyword.get(x.get('keyword'),{}).update(x)
  except Exception as e:
   x['verdict']='history-error'; x['history_error']=f'{type(e).__name__}: {e}'; by_keyword.get(x.get('keyword'),{}).update(x); checked+=1
  time.sleep(9)
 final=[x for x in provisional if x.get('verdict')=='formal']
 payload['formal_candidates']=final; payload['formal_count']=len(final); payload['all_checked']=list(by_keyword.values()); payload.setdefault('method',{})['history_gate']='5-year exact-query anti-seasonality / anti-old-query check'; payload['history_checked_count']=checked
 save(DATA/'latest.json',payload)
 day=payload.get('generated_at','')[:10]
 if day:save(DATA/f'{day}.json',payload)
 md=make_report(payload); (REPORTS/'latest.md').write_text(md,encoding='utf-8')
 if day:(REPORTS/f'{day}.md').write_text(md,encoding='utf-8')
 print('Final formal candidates:',len(final)); return 0

if __name__=='__main__':raise SystemExit(main())
