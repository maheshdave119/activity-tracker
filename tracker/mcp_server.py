import json
from datetime import date,timedelta
from mcp.server.fastmcp import FastMCP
from .core import db,events,logs,generate,add_event,now
mcp=FastMCP('cursor-only-activity-tracker')
@mcp.tool()
def get_today_activity(project:str='')->str:
 """Get today's collected local Cursor and filesystem evidence."""
 a=events(date.today().isoformat());return json.dumps([x for x in a if not project or project.lower() in str(x.get('project','')).lower()],indent=2)
@mcp.tool()
def get_activity_by_project(project:str,days:int=1)->str:
 """Get collected evidence for a project over the requested recent number of days."""
 since=(date.today()-timedelta(days=max(1,min(days,90))-1)).isoformat()
 with db() as c:a=[dict(x) for x in c.execute('SELECT e.*,p.name project FROM events e LEFT JOIN projects p ON p.id=e.project_id WHERE date(e.ts)>=date(?) AND p.name LIKE ? ORDER BY e.ts',(since,'%'+project+'%'))]
 return json.dumps(a,indent=2)
@mcp.tool()
def generate_today_timelog()->str:
 """Generate today's project-wise draft timelogs. Review before approval."""
 return json.dumps(generate(),indent=2)
@mcp.tool()
def generate_project_timelog(project:str,start_date:str,end_date:str)->str:
 """Generate project draft timelogs for an inclusive YYYY-MM-DD date range."""
 d=date.fromisoformat(start_date);end=date.fromisoformat(end_date);out=[]
 while d<=end:out.append(generate(d.isoformat(),project));d+=timedelta(days=1)
 return json.dumps(out,indent=2)
@mcp.tool()
def search_timelogs(keyword:str,project:str='')->str:
 """Search saved timelogs by description keyword and optional project."""
 return json.dumps([x for x in logs() if keyword.lower() in x['description'].lower() and (not project or project.lower() in str(x.get('project','')).lower())],indent=2)
@mcp.tool()
def get_timelog_history(days:int=30)->str:
 """Get saved timelogs for the last N days."""
 since=(date.today()-timedelta(days=max(1,min(days,365))-1)).isoformat();return json.dumps([x for x in logs() if x['day']>=since],indent=2)
@mcp.tool()
def get_workspace_projects()->str:
 """List detected workspace projects."""
 with db() as c:return json.dumps([dict(x) for x in c.execute('SELECT * FROM projects ORDER BY name')],indent=2)
@mcp.tool()
def get_activity_summary(days:int=7)->str:
 """Summarize collected events and generated timelogs over recent days."""
 since=(date.today()-timedelta(days=max(1,min(days,365))-1)).isoformat()
 with db() as c:a=[dict(x) for x in c.execute('SELECT date(ts) day,COUNT(*) events FROM events WHERE date(ts)>=date(?) GROUP BY date(ts) ORDER BY day DESC',(since,))]
 return json.dumps({'daily_event_counts':a,'timelogs':[x for x in logs() if x['day']>=since]},indent=2)
@mcp.tool()
def get_activity_for_date(work_date:str)->str:
 """Get evidence for a date formatted YYYY-MM-DD."""
 return json.dumps(events(work_date),indent=2)
if __name__=='__main__':mcp.run()

@mcp.tool()
def record_activity(project_path:str,activity:str,category:str='Search & Research')->str:
 """Record a user-supplied activity or research topic in the local Cursor journal. Use a workspace folder path and a concise human-readable summary; do not include secrets."""
 if category not in ('Search & Research','Development','Planning','Debugging','Documentation','Code Review','Other'):
  category='Other'
 add_event(now(),project_path,'manual_cursor_note',category,activity[:500],{'event_type':'manual_note','attribution':'user supplied'})
 return json.dumps({'ok':True,'project':project_path,'category':category,'recorded':activity[:500]})
