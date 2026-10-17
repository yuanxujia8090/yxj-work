import json,glob,collections,re,datetime,os,sys
root='/workspace/xrail/sessions'
TZ=datetime.timezone(datetime.timedelta(hours=8))
def pt(s):
    try: return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
    except: return None
def cls(provider,msg):
    m=(msg or '').lower()
    if 'aborted after' in m: return 'retry_exhausted_abort'
    if 'operation aborted' in m or 'request was aborted' in m or 'this operation was aborted' in m: return 'aborted'
    if 'timed out' in m or '524' in m: return 'timeout'
    if '账号池' in m or 'concurrency' in m or 'busy' in m or 'overloaded' in m or 'rate' in m or '429' in m or 'account selection' in m: return 'capacity/rate'
    if 'temporarily unavailable' in m or '502' in m or '503' in m or '520' in m or 'upstream' in m: return 'upstream_unavailable'
    if 'connection error' in m or 'terminated' in m or 'stream ended' in m or 'stream' in m: return 'connection/stream'
    if '401' in m or '403' in m or 'balance' in m: return 'auth/quota'
    if '400' in m or '422' in m: return 'bad_request'
    return 'other'
rows=[]
for f in sorted(glob.glob(root+'/**/*.jsonl',recursive=True)):
    rel=f[len(root)+1:]
    if 'subagent-artifacts' in rel: kind='transcript'
    elif '/run-' in rel: kind='subrun'
    else: kind='main'
    if kind=='transcript': continue
    sid=None;first=last=None
    r=dict(file=rel,kind=kind,project=rel.split('/')[0].replace('--Users-yuanxj-Documents-','').strip('-'))
    prov=collections.Counter();err=collections.Counter();errp=collections.Counter();errs=[]
    a=0;tr=0;trerr=0;user=0;comp=0;mc=[];stop=collections.Counter();mtime=0
    xr=0;userTexts=[];gaps=[];prev=None;prevkind=None;compts=[]
    lastAssistantStop=None;subcalls=0;suberr=0;subtimeouts=0
    model_by_ts=[]
    for l in open(f):
        try:o=json.loads(l)
        except: continue
        t=o.get('type');ts=pt(o.get('timestamp','')) if o.get('timestamp') else None
        if t=='session': sid=o.get('id');r['cwd']=o.get('cwd')
        if ts:
            first=first or ts
            if prev and (ts-prev).total_seconds()>600:
                gaps.append(((ts-prev).total_seconds(),prevkind,t if t!='message' else o['message'].get('role'),prev.astimezone(TZ).strftime('%m-%d %H:%M')))
            prev=ts;last=ts
            prevkind = t if t!='message' else (o['message'].get('role')+':'+str(o['message'].get('stopReason')))
        if 'x-rail' in l or 'x_rail' in l: xr+=1
        if t=='compaction': comp+=1;compts.append(ts.astimezone(TZ).strftime('%m-%d %H:%M') if ts else '')
        if t=='model_change': mc.append((ts.astimezone(TZ).strftime('%m-%d %H:%M:%S') if ts else '',o.get('provider'),o.get('modelId')))
        if t!='message': continue
        m=o['message'];role=m.get('role')
        if role=='assistant':
            a+=1;p=m.get('provider');prov[p+'/'+str(m.get('model'))]+=1;stop[m.get('stopReason')]+=1
            mtime+=m.get('durationMs') or 0
            if m.get('stopReason') in ('error','aborted'):
                c=cls(p,m.get('errorMessage'))
                if m.get('stopReason')=='aborted' and c not in('retry_exhausted_abort',): c='aborted'
                err[(p,c)]+=1;errp[p]+=1
                errs.append((ts.astimezone(TZ).strftime('%m-%d %H:%M:%S') if ts else '',p,m.get('model'),c,(m.get('errorMessage') or '')[:100],m.get('durationMs')))
            for c in m.get('content',[]):
                if isinstance(c,dict) and c.get('type')=='toolCall' and c.get('name')=='subagent': subcalls+=1
        elif role=='toolResult':
            tr+=1
            if m.get('isError'): trerr+=1
            if m.get('toolName')=='subagent':
                txt=''.join(c.get('text','') for c in m.get('content',[]) if isinstance(c,dict))
                if m.get('isError'): suberr+=1
                if re.search(r'timed out after \d+ms|timed_out|Subagent timed out',txt): subtimeouts+=1
        elif role=='user':
            user+=1
            txt=''.join(c.get('text','') for c in (m.get('content') if isinstance(m.get('content'),list) else [{'text':m.get('content')}]) if isinstance(c,dict) and c.get('text'))
            userTexts.append((ts.astimezone(TZ).strftime('%m-%d %H:%M') if ts else '',txt[:300].replace('\n',' ')))
    r.update(sid=sid,start=first.astimezone(TZ).strftime('%Y-%m-%d %H:%M') if first else None,
             wall_h=round((last-first).total_seconds()/3600,2) if first else 0,assist=a,model_h=round(mtime/3.6e6,2),
             tools=tr,tool_err=trerr,user=user,compactions=comp,compts=compts,model_changes=mc,providers=dict(prov),
             stop=dict(stop),errors={f'{k[0]}|{k[1]}':v for k,v in err.items()},err_by_provider=dict(errp),errlist=errs,
             xrail_lines=xr,gaps=gaps,user_texts=userTexts,subagent_calls=subcalls,subagent_err=suberr,subagent_timeouts=subtimeouts)
    rows.append(r)
json.dump(rows,open('/workspace/xrail/analysis/sessions.json','w'),ensure_ascii=False,indent=1)
print(len(rows))
