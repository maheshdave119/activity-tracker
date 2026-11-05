import threading,csv,io
from datetime import date,timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from fastapi.responses import HTMLResponse,StreamingResponse
from pydantic import BaseModel, Field
from .activity_source import ActivitySourceError, fetch_report, report_csv
from .core import *
stop=threading.Event()
@asynccontextmanager
async def lifespan(app):
 init();threading.Thread(target=collector,args=(stop,),daemon=True).start();yield;stop.set()
app=FastAPI(title='Cursor-Only Activity Tracker',lifespan=lifespan)
class Edit(BaseModel):description:str|None=None;adjusted_hours:float|None=None;status:str|None=None
class Ingest(BaseModel):
 ts:str
 workspace:str|None=None
 source:str='cursor_extension'
 category:str='Other'
 summary:str=Field(min_length=1,max_length=500)
 details:dict=Field(default_factory=dict)
@app.get('/',response_class=HTMLResponse)
def home():return PAGE
@app.get('/api/health')
def health():
 with db() as c:
  n=c.execute("SELECT COUNT(*) FROM events WHERE source='cursor_extension'").fetchone()[0]
  last=c.execute("SELECT MAX(ts) FROM events WHERE source='cursor_extension'").fetchone()[0]
 return {'status':'ok','workspace_roots':[str(x) for x in ROOTS],'cursor_extension_events':n,'last_extension_event':last,'extension_required':True}
@app.post('/api/ingest')
def ingest(b:Ingest):
 from datetime import datetime
 try: ts=datetime.fromisoformat(b.ts.replace('Z','+00:00')).astimezone().isoformat(timespec='seconds')
 except ValueError: raise HTTPException(400,'Invalid timestamp')
 ws=str(Path(b.workspace).expanduser().resolve()) if b.workspace else None
 if ws and not Path(ws).exists(): ws=None
 details=dict(b.details or {}); details['event_type']=details.get('event', 'activity')
 add_event(ts,ws,b.source,b.category,b.summary,details)
 return {'ok':True}
@app.get('/api/summary')
def summary():
 d=date.today().isoformat(); es=events(d); ls=logs('l.day=?',(d,));
 return {'events':len(es),'projects':len(set(x['project_id'] for x in es if x['project_id'])),'logs':len(ls),'pending':sum(x['status']=='draft' for x in ls),'hours':round(sum((x['adjusted_hours'] if x['adjusted_hours'] is not None else x['seconds']/3600) for x in ls),2)}
@app.get('/api/events')
def get_events(day:str|None=None):return events(day or date.today().isoformat())
@app.get('/api/projects')
def projects():
 with db() as c:return [dict(x) for x in c.execute('SELECT * FROM projects ORDER BY name')]
@app.get('/api/logs')
def get_logs(day:str|None=None,project:str|None=None,q:str|None=None,status:str|None=None):
 cond=[];args=[]
 if day:cond.append('l.day=?');args.append(day)
 if project:cond.append('p.name LIKE ?');args.append('%'+project+'%')
 if q:cond.append('l.description LIKE ?');args.append('%'+q+'%')
 if status:cond.append('l.status=?');args.append(status)
 return logs(' AND '.join(cond),args)
@app.post('/api/generate')
def gen():return generate()
@app.patch('/api/logs/{i}')
def edit(i:int,b:Edit):
 data=b.model_dump(exclude_none=True)
 with db() as c:
  old=c.execute('SELECT * FROM logs WHERE id=?',(i,)).fetchone()
  if not old:raise HTTPException(404,'Not found')
  sets=','.join(k+'=?' for k in data); vals=list(data.values())
  if sets:c.execute(f'UPDATE logs SET {sets},updated=? WHERE id=?',vals+[now(),i])
  new=dict(c.execute('SELECT * FROM logs WHERE id=?',(i,)).fetchone())
  c.execute('INSERT INTO audit(log_id,at,action,before,after) VALUES(?,?,?,?,?)',(i,now(),'edit',json.dumps(dict(old)),json.dumps(new)))
  return new
@app.post('/api/logs/{i}/approve')
def approve(i:int):return edit(i,Edit(status='approved'))
@app.get('/api/idle')
def idle():
 with db() as c:return [dict(x) for x in c.execute('SELECT * FROM idle ORDER BY start DESC LIMIT 100')]
@app.patch('/api/idle/{i}')
def idle_update(i:int,status:str,note:str=''):
 if status not in ('confirmed_work','break','dismissed'):raise HTTPException(400,'Invalid status')
 with db() as c:c.execute('UPDATE idle SET status=?,note=? WHERE id=?',(status,note,i))
 return {'ok':True}
@app.get('/api/export.csv')
def export():
 out=io.StringIO();w=csv.writer(out);w.writerow(['Date','Project Name','Description','Start Time','End Time','Total Hours','Category','Status','Confidence'])
 for x in logs():w.writerow([x['day'],x['project'],x['description'],x['start'],x['end'],round(x['adjusted_hours'] if x['adjusted_hours'] is not None else x['seconds']/3600,2),x['category'],x['status'],x['confidence']])
 return StreamingResponse(iter([out.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=cursor-timelogs.csv'})
@app.get('/api/timelog')
async def timelog(day:str|None=None, project:str|None=None):
 day=_day(day)
 try: return await fetch_report(day, project or '')
 except ActivitySourceError as exc: raise HTTPException(502, str(exc))
@app.get('/api/timelog.csv')
async def timelog_csv(day:str|None=None, project:str|None=None):
 day=_day(day)
 try: report=await fetch_report(day, project or '')
 except ActivitySourceError as exc: raise HTTPException(502, str(exc))
 filename=f"timelog-{day}.csv"
 return StreamingResponse(iter([report_csv(report)]),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename={filename}'})
def _day(day:str|None)->str:
 day=day or date.today().isoformat()
 try: date.fromisoformat(day)
 except ValueError: raise HTTPException(400,'Use a date in YYYY-MM-DD format.')
 return day
PAGE=(Path(__file__).with_name('dashboard.html')).read_text()
