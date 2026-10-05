from __future__ import annotations

import json, math, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from trendspyg import download_google_trends_explore, download_google_trends_rss

ROOT = Path(__file__).resolve().parents[1]
CFG, SEEDS = ROOT/'config/settings.json', ROOT/'config/seeds.txt'
SEEN, PENDING = ROOT/'state/seen.json', ROOT/'state/pending.json'
DATA, REPORTS = ROOT/'data', ROOT/'reports'

MONEY = [
 (r'\b(calculator|generator|checker|converter|analyzer|tracker|planner|builder|editor|downloader|simulator)\b',90,'tool'),
 (r'\b(codes?|values?|stats?|database|tier\s*list|rankings?|schedule|results?)\b',82,'repeat-data'),
 (r'\b(pricing|price|cost|compare|comparison|alternative|alternatives|coupon|deals?|discount|buy|marketplace)\b',86,'transactional'),
 (r'\b(template|templates|prompt|prompts|preset|presets|pack|packs|spreadsheet|resume)\b',76,'digital-product'),
 (r'\b(api|automation|workflow|reporting|compliance|invoice|payroll|tax|analytics)\b',78,'saas-b2b'),
 (r'\b(ai|app|tool|software)\b',45,'software'),
]
NOISE = ('weather','earthquake','score','election','lottery','death','obituary','breaking news','near me')


def now(): return datetime.now(timezone.utc)
def norm(s): return re.sub(r'\s+',' ',str(s).strip()).lower()
def valid(q): return 2 <= len(q) <= 90 and q.count(' ') <= 9 and not q.isdigit()
def load(p,d):
 try: return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
 except Exception: return d
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def money(q):
 q=norm(q); best=(22,'informational')
 for pat,score,kind in MONEY:
  if re.search(pat,q,re.I) and score>best[0]: best=(score,kind)
 if len(q.split())>=2: best=(min(100,best[0]+4),best[1])
 return best
def noisy(q): return any(x in norm(q) for x in NOISE)
def seed_list():
 if not SEEDS.exists(): return []
 return list(dict.fromkeys(norm(x) for x in SEEDS.read_text(encoding='utf-8').splitlines() if x.strip() and not x.lstrip().startswith('#')))


def remember(seen,q,source,today):
 q=norm(q)
 if q not in seen: seen[q]={'first_seen':today,'sources':[source]}
 elif source not in seen[q].setdefault('sources',[]): seen[q]['sources'].append(source)
 seen[q]['last_seen']=today


def queue(pending,q,geo,source,today):
 q=norm(q)
 if not valid(q): return
 x=pending.setdefault(q,{'query':q,'geo':geo,'source':source,'first_seen':today,'checks':0})
 x['last_seen']=today
 if not x.get('geo') and geo: x['geo']=geo


def rss_discover(geos,seen,pending):
 today=now().date().isoformat(); out=[]
 for geo in geos:
  try:
   env=download_google_trends_rss(geo=geo,normalize=True)
   for t in env.get('trends',[]):
    vals=[(norm(t.get('keyword','')),f'rss:{geo}:keyword')]
    for r in t.get('related_queries') or []:
     q = norm(r if isinstance(r,str) else r.get('query') or r.get('keyword') or '')
     vals.append((q,f'rss:{geo}:related'))
    for q,source in vals:
     if valid(q):
      out.append({'query':q,'geo':geo,'source':source}); remember(seen,q,source,today); queue(pending,q,geo,source,today)
  except Exception as e: print(f'RSS {geo}: {type(e).__name__}: {e}',file=sys.stderr)
 return out


def suggest(q,geo):
 params=urllib.parse.urlencode({'client':'firefox','q':q,'hl':'en','gl':(geo or 'US').lower()})
 req=urllib.request.Request('https://suggestqueries.google.com/complete/search?'+params,headers={'User-Agent':'Mozilla/5.0 NewKeywordRadar/1.0'})
 with urllib.request.urlopen(req,timeout=8) as r: p=json.loads(r.read().decode())
 return [norm(x) for x in (p[1] if isinstance(p,list) and len(p)>1 else []) if valid(norm(x))]


def suggest_discover(items,seen,pending,limit):
 today=now().date().isoformat(); bases=[]; used=set(); added=[]
 for x in items:
  if ':keyword' in x['source'] and x['query'] not in used and not noisy(x['query']):
   used.add(x['query']); bases.append(x)
  if len(bases)>=limit: break
 for i,x in enumerate(bases):
  try:
   for q in suggest(x['query'],x['geo']):
    if money(q)[0] < 55: continue
    src=f"suggest:{x['geo']}:{x['query']}"; row={'query':q,'geo':x['geo'],'source':src}
    added.append(row); remember(seen,q,src,today); queue(pending,q,x['geo'],src,today)
  except Exception as e: print(f"Suggest {x['query']}: {type(e).__name__}: {e}",file=sys.stderr)
  if i<len(bases)-1: time.sleep(.7)
 return items+added


def select(items,seeds,seen,pending,n):
 pool={q:{'query':q,'geo':'','source':'manual-seed'} for q in seeds}
 for q,x in pending.items(): pool.setdefault(q,{'query':q,'geo':x.get('geo',''),'source':x.get('source','pending')})
 for x in items: pool.setdefault(x['query'],x)
 today=now().date(); ranked=[]
 for x in pool.values():
  q=x['query']; first=seen.get(q,{}).get('first_seen',today.isoformat())
  try: age=max(0,(today-datetime.fromisoformat(first).date()).days)
  except Exception: age=999
  bonus=(100 if x['source']=='manual-seed' else 0)+(28 if x['source'].startswith('suggest:') else 0)+(18 if ':related' in x['source'] else 0)
  checks=int(pending.get(q,{}).get('checks',0)); score=money(q)[0]+max(0,30-age)+bonus+max(0,18-checks*6)-(25 if noisy(q) else 0)
  ranked.append((score,q,x))
 ranked.sort(key=lambda z:(-z[0],z[1])); return [x for _,_,x in ranked[:n]]


def analyze(keyword,geo,source,first,series,related,cfg):
 pts=[]
 for x in series:
  try:
   d=datetime.fromisoformat(str(x['date']).replace('Z','+00:00')); d=d if d.tzinfo else d.replace(tzinfo=timezone.utc); pts.append((d,int(x.get('value',0) or 0)))
  except Exception: pass
 pts.sort()
 ms,mt=money(keyword)
 if not pts: return {'keyword':keyword,'geo':geo,'source':source,'first_seen':first,'newness_score':0,'money_score':ms,'money_type':mt,'true_new':False,'verdict':'reject','series':series,'related_rising':related}
 cutoff=pts[-1][0]-timedelta(days=int(cfg.get('lookback_new_days',30))); base=[v for d,v in pts if d<cutoff]; recent=[(d,v) for d,v in pts if d>=cutoff]
 if not base:
  k=max(1,int(len(pts)*2/3)); base=[v for _,v in pts[:k]]; recent=pts[k:]
 rv=[v for _,v in recent] or [0]; ba=round(sum(base or [0])/max(1,len(base)),2); bp=max(base or [0]); bn=round(sum(v>0 for v in (base or [0]))/max(1,len(base)),3); rp=max(rv)
 threshold=max(5,math.ceil(rp*.12)); rise=next((d for d,v in recent if v>=threshold),None); peak=next((d for d,v in recent if v==rp),None); cur=round(sum(rv[-3:])/len(rv[-3:]),2); ret=round(cur/rp*100,1) if rp else 0
 true=ba<=cfg.get('max_baseline_avg',1.5) and bn<=cfg.get('max_baseline_nonzero_ratio',.1) and bp<=cfg.get('max_baseline_peak',10) and rp>=cfg.get('min_recent_peak',20) and rise is not None
 ns=(30 if ba<=.5 else 20 if ba<=1.5 else 0)+(18 if bn<=.05 else 10 if bn<=.1 else 0)+(12 if bp<=5 else 6 if bp<=10 else 0)+(20 if rp>=50 else 14 if rp>=20 else 0)+(8 if rise else 0)+(7 if ret>=15 else 3 if ret>0 else 0)
 if any(str(x.get('formatted_value','')).lower()=='breakout' for x in related): ns+=5
 if any(money(x.get('query',''))[0]>=75 for x in related): ms=min(100,ms+6)
 verdict='formal' if true and ms>=cfg.get('min_money_score',55) else 'trend-watch' if true else 'commercial-watch' if ms>=60 and ns>=45 else 'reject'
 return {'keyword':keyword,'geo':geo,'source':source,'first_seen':first,'baseline_avg':ba,'baseline_peak':bp,'baseline_nonzero_ratio':bn,'recent_peak':rp,'current_level':cur,'retention_pct':ret,'first_rise_date':rise.isoformat() if rise else None,'peak_date':peak.isoformat() if peak else None,'newness_score':min(100,ns),'money_score':ms,'money_type':mt,'true_new':true,'verdict':verdict,'related_rising':related,'series':series}


def explore(x,seen,cfg):
 q=x['query']; geo=x.get('geo') or ''; first=seen.get(q,{}).get('first_seen',now().date().isoformat())
 try:
  env=download_google_trends_explore(q,geo=geo,timeframe=cfg.get('timeframe','today 3-m'),include_related=True,include_geo=False,max_retries=2,retry_wait=6,cache='disk',cookies='disk',engine='auto')
  series=[{'date':str(p.get('date')),'value':int(p.get('value',0) or 0),'is_partial':bool(p.get('is_partial',False))} for p in env.get('interest_over_time',[]) if isinstance(p,dict)]
  related=[{'query':norm(r.get('query','')),'value':r.get('value'),'formatted_value':r.get('formatted_value'),'link':r.get('link')} for r in env.get('related_queries',{}).get('rising',[])[:12] if isinstance(r,dict)]
  return analyze(q,geo,x['source'],first,series,related,cfg)
 except Exception as e:
  ms,mt=money(q); return {'keyword':q,'geo':geo,'source':x['source'],'first_seen':first,'newness_score':0,'money_score':ms,'money_type':mt,'true_new':False,'verdict':'error','related_rising':[],'series':[],'error':f'{type(e).__name__}: {e}'}


def report(payload):
 lines=['# New Keyword Radar — Latest','',f"Generated: {payload['generated_at']}",'','## Formal candidates','']
 if not payload['formal_candidates']: lines.append('**今日无合格可变现新词。**')
 for i,x in enumerate(payload['formal_candidates'],1):
  lines += [f"### {i}. {x['keyword']}",'',f"- Newness **{x['newness_score']}/100**; money **{x['money_score']}/100** ({x['money_type']}).",f"- Baseline avg **{x.get('baseline_avg')}**, recent peak **{x.get('recent_peak')}**, first rise {x.get('first_rise_date')}, retention **{x.get('retention_pct')}%**.",f"- Source {x['source']}; geo {x['geo'] or 'Worldwide'}; radar first seen {x['first_seen']}.",'']
 lines += ['## Watch / rejected','']
 for x in payload['all_checked']:
  if x['verdict']!='formal': lines.append(f"- {x['keyword']} — **{x['verdict']}** — newness {x['newness_score']}, money {x['money_score']}"+(f" — {x['error']}" if x.get('error') else ''))
 return '\n'.join(lines)+'\n'


def main():
 DATA.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True); cfg=load(CFG,{}); seen=load(SEEN,{}); pending=load(PENDING,{}); seeds=seed_list(); today=now().date().isoformat()
 items=rss_discover(cfg.get('geos',['US','BR','MX','ES','GB']),seen,pending); items=suggest_discover(items,seen,pending,int(cfg.get('max_suggest_bases',12)))
 for q in seeds: remember(seen,q,'manual-seed',today); queue(pending,q,'','manual-seed',today)
 chosen=select(items,seeds,seen,pending,int(cfg.get('max_explore_per_run',7))); checked=[]
 for i,x in enumerate(chosen):
  print(f"[{i+1}/{len(chosen)}] Explore: {x['query']} ({x.get('geo') or 'Worldwide'})"); r=explore(x,seen,cfg); checked.append(r)
  m=pending.setdefault(x['query'],{'query':x['query'],'geo':x.get('geo',''),'source':x['source'],'first_seen':today,'checks':0}); m['checks']=int(m.get('checks',0))+1; m['last_checked']=today; m['last_verdict']=r['verdict']
  for rq in r.get('related_rising',[]):
   q=norm(rq.get('query',''))
   if valid(q): src=f"explore-related:{x['query']}"; remember(seen,q,src,today); queue(pending,q,x.get('geo',''),src,today)
  if i<len(chosen)-1: time.sleep(9)
 checked.sort(key=lambda x:(x['verdict']!='formal',-x['newness_score'],-x['money_score'],x['keyword'])); formal=[x for x in checked if x['verdict']=='formal'][:int(cfg.get('formal_limit',3))]
 pend=sorted(pending.values(),key=lambda x:(int(x.get('checks',0)),-money(x.get('query',''))[0],x.get('first_seen','9999-99-99')))[:250]; pending={x['query']:x for x in pend if x.get('query')}
 payload={'generated_at':now().isoformat(),'timeframe':cfg.get('timeframe','today 3-m'),'source_geos':cfg.get('geos',[]),'checked_count':len(checked),'formal_count':len(formal),'formal_candidates':formal,'all_checked':checked,'discovered_count':len(items),'pending_count':len(pending),'method':{'new_word_gate':'near-zero baseline + first rise in last 30 days','money_gate':f"money_score >= {cfg.get('min_money_score',55)}",'discovery':'Trending Now RSS + related queries + Google autocomplete + Explore rising queries','note':'Google Trends is relative 0-100 interest, not absolute volume.'}}
 save(DATA/f'{today}.json',payload); save(DATA/'latest.json',payload); save(SEEN,seen); save(PENDING,pending); md=report(payload); (REPORTS/f'{today}.md').write_text(md,encoding='utf-8'); (REPORTS/'latest.md').write_text(md,encoding='utf-8'); print('Formal candidates:',len(formal)); return 0

if __name__=='__main__': raise SystemExit(main())
