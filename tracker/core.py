import os, time, json, hashlib, subprocess, threading
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict
import psutil
from .config import *

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
def db():
 import sqlite3
 c=sqlite3.connect(DB_PATH,timeout=20); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL'); return c
def now(): return datetime.now().astimezone().isoformat(timespec='seconds')
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,name TEXT UNIQUE,root TEXT);
  CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,event_key TEXT UNIQUE,ts TEXT,project_id INTEGER,workspace TEXT,source TEXT,category TEXT,summary TEXT,details TEXT);
  CREATE INDEX IF NOT EXISTS ev_ts ON events(ts);
  CREATE TABLE IF NOT EXISTS idle(id INTEGER PRIMARY KEY,start TEXT,end TEXT,seconds INTEGER,status TEXT DEFAULT 'pending',note TEXT);
  CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,day TEXT,project_id INTEGER,description TEXT,original TEXT,start TEXT,end TEXT,seconds INTEGER DEFAULT 0,adjusted_hours REAL,category TEXT,confidence INTEGER,status TEXT DEFAULT 'draft',evidence TEXT,is_estimated INTEGER DEFAULT 1,created TEXT,updated TEXT);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,log_id INTEGER,at TEXT,action TEXT,before TEXT,after TEXT);''')
def add_event(ts, workspace, source, category, summary, details=None):
 with db() as c:
  pid=None
  if workspace:
   root=str(Path(workspace).expanduser())
   r=c.execute('SELECT id FROM projects WHERE root=?',(root,)).fetchone()
   if r: pid=r['id']
   else:
    name=Path(root).name or root
    if c.execute('SELECT 1 FROM projects WHERE name=?',(name,)).fetchone():
     name=f"{name} ({Path(root).parent.name})"
    c.execute('INSERT OR IGNORE INTO projects(name,root) VALUES(?,?)',(name,root))
    r=c.execute('SELECT id FROM projects WHERE root=?',(root,)).fetchone(); pid=r['id'] if r else None
  k=hashlib.sha256((ts[:19]+source+summary+str(details)).encode()).hexdigest()
  c.execute('INSERT OR IGNORE INTO events(event_key,ts,project_id,workspace,source,category,summary,details) VALUES(?,?,?,?,?,?,?,?)',(k,ts,pid,workspace,source,category,summary,json.dumps(details or {})))
def cursor_info():
 from urllib.parse import urlparse, unquote
 paths=[]; running=False
 for p in psutil.process_iter(['name','cmdline']):
  try:
   name=(p.info.get('name') or '').lower(); cmd=p.info.get('cmdline') or []
   if 'cursor' not in name and not any('cursor' in str(x).lower() for x in cmd[:3]): continue
   running=True
   i=0
   while i<len(cmd):
    arg=str(cmd[i]); candidate=None
    if arg.startswith('--folder-uri=') or arg.startswith('--file-uri='):
     uri=arg.split('=',1)[1]; parsed=urlparse(uri)
     if parsed.scheme=='file':
      candidate=Path(unquote(parsed.path)); candidate=candidate if arg.startswith('--folder-uri=') else candidate.parent
    elif arg in ('--folder-uri','--file-uri') and i+1<len(cmd):
     parsed=urlparse(str(cmd[i+1]))
     if parsed.scheme=='file':
      candidate=Path(unquote(parsed.path)); candidate=candidate if arg=='--folder-uri' else candidate.parent
     i+=1
    elif arg.startswith('/') and Path(arg).is_dir(): candidate=Path(arg)
    if candidate and candidate.exists() and candidate.is_dir():
     candidate=candidate.resolve()
     if any(candidate==r or r in candidate.parents for r in ROOTS): paths.append(str(candidate))
    i+=1
  except (psutil.NoSuchProcess,psutil.AccessDenied, OSError): pass
 return running,list(dict.fromkeys(paths))

def idle_time():
 try:return int(subprocess.check_output(['xprintidle'],stderr=subprocess.DEVNULL,timeout=2).strip())//1000
 except Exception:return None
def scan(root):
 out={}
 for cur,dirs,names in os.walk(root):
  dirs[:]=[d for d in dirs if d not in EXCLUDES and not d.startswith('.cache')]
  for n in names:
   p=Path(cur)/n
   try:
    s=p.stat()
    if p.is_file() and s.st_size<5_000_000:out[str(p)]=(s.st_mtime_ns,s.st_size)
   except OSError:pass
 return out
def collector(stop):
 prev={}; last=0; idle_start=None
 while not stop.is_set():
  ts=now(); running,workspaces=cursor_info(); idle=idle_time()
  if running and idle is not None and idle>=IDLE_THRESHOLD:
   if idle_start is None:
    idle_start=ts
    with db() as c:c.execute("INSERT INTO idle(start,status) VALUES(?,'pending')",(ts,))
   add_event(ts,workspaces[0] if workspaces else None,'os_idle','Idle',f'Inactivity detected ({idle} seconds)',{'idle_seconds':idle})
  elif idle_start:
   with db() as c:c.execute('UPDATE idle SET end=?,seconds=CAST((julianday(?) - julianday(start))*86400 AS INTEGER) WHERE end IS NULL',(ts,ts))
   idle_start=None
  if running and idle is not None and idle<IDLE_THRESHOLD and time.time()-last>=60:
   for w in workspaces:add_event(ts,w,'cursor_presence','Development','Cursor process active; workspace session presence signal',{'idle_seconds':idle})
   last=time.time()
  # Cursor-only session gate: never poll workspace files while Cursor is closed.
  if running:
   # Fallback filesystem observation is restricted to workspace paths explicitly
   # present on Cursor's process command line. The extension supplies richer,
   # exact workspace events and is not limited to these configured roots.
   for root in [Path(x) for x in workspaces]:
    if not root.exists():continue
    try:
     cur=scan(root); key=str(root)
     # First scan is a baseline, not a burst of false 'created' events for every
     # existing repository file. The extension separately records actual editor opens/edits.
     if key not in prev:
      prev[key]=cur
      continue
     old=prev[key]
     for p,m in cur.items():
      if p not in old or old[p]!=m:
       kind='created' if p not in old else 'modified'; ext=Path(p).suffix.lower()
       cat='Documentation' if ext in {'.md','.rst','.txt'} else 'Development'
       add_event(ts,str(root),'cursor_session_filesystem',cat,
                 f'File {kind} during Cursor session: {Path(p).name}',
                 {'path':p,'size_bytes':m[1],'attribution':'workspace change observed while Cursor process was running; editor origin is not independently provable'})
     prev[key]=cur
    except OSError:pass
  else:
   # Force a fresh baseline on next Cursor launch; don't count changes made while it was closed.
   prev.clear()
  stop.wait(SCAN_INTERVAL)
def generate(day=None,project=None):
 day=day or date.today().isoformat(); start=day+'T00:00:00'; end=(date.fromisoformat(day)+timedelta(days=1)).isoformat()+'T00:00:00'
 with db() as c:
  sql='SELECT e.*,p.name project FROM events e LEFT JOIN projects p ON p.id=e.project_id WHERE e.ts>=? AND e.ts<?'; args=[start,end]
  if project: sql+=' AND p.name LIKE ?'; args.append('%'+project+'%')
  ev=[dict(x) for x in c.execute(sql+' ORDER BY e.ts',args)]
 groups=defaultdict(list)
 for e in ev: groups[(e['project_id'],e['workspace'])].append(e)
 made=0; updated=0
 for (pid,ws),items in groups.items():
  intervals=[]; parsed=[]
  for e in items:
   try:
    t=datetime.fromisoformat(e['ts']); parsed.append(t)
    # Explicit editor events carry a shorter evidence window than a periodic heartbeat.
    typ=(json.loads(e.get('details') or '{}').get('event_type') or '')
    span=60 if typ in ('cursor_heartbeat','cursor_presence') else 90
    intervals.append((t,t+timedelta(seconds=span)))
   except Exception: pass
  intervals.sort(); merged=[]
  for a,b in intervals:
   if merged and a<=merged[-1][1]: merged[-1]=(merged[-1][0],max(merged[-1][1],b))
   else: merged.append((a,b))
  seconds=sum(max(0,int((b-a).total_seconds())) for a,b in merged)
  summaries=[]
  for x in items:
   text=x['summary'].strip()
   if text and text not in summaries: summaries.append(text)
  # Keep the narrative readable while preserving the detailed event list as linked evidence.
  if len(summaries)==1: desc=summaries[0]+'.'
  elif summaries:
   shown=summaries[:5]
   desc='; '.join(shown)+ (f'; and {len(summaries)-len(shown)} other recorded actions' if len(summaries)>len(shown) else '')+'.'
  else: desc='Cursor activity recorded in this workspace.'
  cats=defaultdict(int)
  for x in items: cats[x['category']]+=1
  cat=max(cats,key=cats.get) if cats else 'Development'
  # Confidence describes evidence coverage, not proof of continuous work.
  extension_count=sum(1 for x in items if x['source']=='cursor_extension')
  conf=min(96,30+min(len(items),8)*5+(15 if extension_count else 0))
  ids=json.dumps([x['id'] for x in items])
  st=min(parsed).astimezone().isoformat(timespec='minutes') if parsed else None
  en=max(parsed).astimezone().isoformat(timespec='minutes') if parsed else None
  with db() as c:
   exists=c.execute("SELECT id,status FROM logs WHERE day=? AND project_id IS ? AND status IN ('draft','pending')",(day,pid)).fetchone()
   if exists:
    c.execute('UPDATE logs SET description=?,original=?,start=?,end=?,seconds=?,category=?,confidence=?,evidence=?,updated=? WHERE id=?',(desc,desc,st,en,seconds,cat,conf,ids,now(),exists['id'])); updated+=1
   else:
    c.execute("INSERT INTO logs(day,project_id,description,original,start,end,seconds,category,confidence,status,evidence,created,updated) VALUES(?,?,?,?,?,?,?,?,?,'draft',?,?,?)",(day,pid,desc,desc,st,en,seconds,cat,conf,ids,now(),now())); made+=1
 return {'date':day,'events_analyzed':len(ev),'projects_analyzed':len(groups),'created':made,'updated':updated,'note':'Evidence-based estimated duration only; not verified billable hours.'}

def logs(where='',args=()):
 with db() as c:
  sql='SELECT l.*,p.name project FROM logs l LEFT JOIN projects p ON p.id=l.project_id'
  if where:sql+=' WHERE '+where
  return [dict(x) for x in c.execute(sql+' ORDER BY l.day DESC,l.start',args)]
def events(day=None):
 with db() as c:
  sql='SELECT e.*,p.name project FROM events e LEFT JOIN projects p ON p.id=e.project_id';args=[]
  if day:sql+=' WHERE date(e.ts)=date(?)';args=[day]
  return [dict(x) for x in c.execute(sql+' ORDER BY e.ts DESC LIMIT 1000',args)]
