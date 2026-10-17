import json,glob,collections,re,datetime,statistics
root='/workspace/xrail/sessions'
TZ=datetime.timezone(datetime.timedelta(hours=8))
def pt(s): return datetime.datetime.fromisoformat(s.replace('Z','+00:00'))
def loc(d): return d.astimezone(TZ).strftime('%m-%d %H:%M:%S')
lat=collections.defaultdict(list)
bursts=[];switches=[];stalls=[];userint=collections.Counter();userex=collections.defaultdict(list)
taskpy=collections.Counter();taskpyerr=[];supreq=0;supex=[]
subres=collections.Counter();subex=collections.defaultdict(list)
compinfo=[]
for f in sorted(glob.glob(root+'/**/*.jsonl',recursive=True)):
    rel=f[len(root)+1:]
    if 'subagent-artifacts' in rel: continue
    kind='subrun' if '/run-' in rel else 'main'
    sid=re.search(r'_([0-9a-f]{8})-',rel.split('/')[1]).group(1) if kind=='main' else 'sub:'+rel.split('/')[2][:8]
    ents=[]
    for l in open(f):
        try:o=json.loads(l)
        except: continue
        if o.get('timestamp'): ents.append(o)
    cur=None;prevts=None;prevdesc=None;pending={}
    lastErr=None
    for i,o in enumerate(ents):
        ts=pt(o['timestamp']);t=o['type']
        if t=='custom_message':
            txt=json.dumps(o,ensure_ascii=False)
            if 'supervisor_request' in txt or 'needs a supervisor decision' in txt: supreq+=1;supex.append((sid,loc(ts),o.get('customType'),str(o.get('content'))[:200]))
        if t=='compaction':
            compinfo.append((sid,kind,loc(ts),o.get('tokensBefore'),len(o.get('summary',''))))
        if t=='model_change':
            if lastErr and (ts-lastErr[0]).total_seconds()<1800:
                switches.append((sid,loc(ts),lastErr[1],o.get('provider')+'/'+o.get('modelId'),round((ts-lastErr[0]).total_seconds()/60,1)))
        if t!='message': 
            prevts=ts;prevdesc=t;continue
        m=o['message'];role=m['role']
        if role=='assistant':
            p=m.get('provider')
            if m.get('stopReason') not in ('error','aborted') and m.get('durationMs'):
                lat[p].append(m['durationMs']/1000)
            if m.get('stopReason') in ('error','aborted'):
                if m.get('stopReason')=='error':
                    if cur is None: cur=dict(sid=sid,kind=kind,start=ts,provider=p,n=0,msgs=collections.Counter())
                    cur['n']+=1;cur['msgs'][(m.get('errorMessage') or '')[:50]]+=1;cur['end']=ts
                lastErr=(ts,p)
            else:
                if cur:
                    cur['resolved']='same_provider_ok' if p==cur['provider'] else 'other_provider_ok:'+p
                    cur['recover_s']=(ts-cur['start']).total_seconds();bursts.append(cur);cur=None
            for c in m.get('content',[]):
                if c.get('type')=='toolCall':
                    pending[c['id']]=(c['name'],c.get('arguments'),ts)
        elif role=='toolResult':
            name,args,t0=pending.pop(m['toolCallId'],(m['toolName'],None,None))
            txt=''.join(c.get('text','') for c in m['content'] if isinstance(c,dict))
            if name in ('bash','ctx_execute') and args and 'task.py' in json.dumps(args):
                cmd=re.search(r'task\.py\s+(\w+)',json.dumps(args));sub=cmd.group(1) if cmd else '?'
                taskpy[(sub,m['isError'] or bool(re.search(r'exit(ed)? (with )?code [1-9]|Exit code: [1-9]',txt)))]+=1
                if m['isError'] or re.search(r'Exit code: [1-9]|exited with code [1-9]',txt): taskpyerr.append((sid,loc(ts),sub,txt[:160].replace('\n',' ')))
            if name=='subagent':
                k='ok'
                if re.search(r'timed out after (\d+)ms',txt): k='timeout:'+re.search(r'timed out after (\d+)ms',txt).group(1)
                elif m['isError']: k='error'
                elif re.search(r'\bfailed\b|Request was aborted|upstream_error|stopped',txt[:400]): k='failed-in-text'
                subres[k]+=1;subex[k].append((sid,loc(ts),txt[:200].replace('\n',' ')))
            if t0 and (ts-t0).total_seconds()>600:
                stalls.append((sid,kind,'tool_running',name,round((ts-t0).total_seconds()/60,1),loc(t0)))
        elif role=='user':
            if cur: cur['resolved']='user_intervened';cur['recover_s']=(ts-cur['start']).total_seconds();bursts.append(cur);cur=None
            txt=''.join(c.get('text','') for c in (m['content'] if isinstance(m['content'],list) else []) if isinstance(c,dict) and c.get('text')).strip()
            if kind=='main' and len(txt)<200:
                for lab,pat in [('继续/催促',r'^(继续|continue|go on|接着|继续执行|一直执行)|继续$'),('询问进度',r'进度|完成了吗|做完|好了吗|了解完了吗|接下来做什么|到哪'),('不满/质疑',r'为什么|怎么又|又失败|卡住|卡了|没反应|不对|错了|别|不要再|还没'),('subagent通知','Subagent updates above')]:
                    if re.search(pat,txt,re.I): userint[lab]+=1;userex[lab].append((sid,loc(ts),txt[:80]))
        # stall: gap between entries
        if prevts and (ts-prevts).total_seconds()>900 and role=='user' and prevdesc and prevdesc.startswith('assistant'):
            pass
        prevts=ts;prevdesc=role+':'+str(m.get('stopReason'))
    if cur: cur['resolved']='session_end';cur['recover_s']=None;bursts.append(cur)
out={}
for p,v in lat.items():
    v=sorted(v);n=len(v)
    out[p]=dict(n=n,median=round(statistics.median(v),1),p90=round(v[int(n*.9)],1),p99=round(v[int(n*.99)],1),gt120=sum(x>120 for x in v),gt300=sum(x>300 for x in v),max=round(v[-1]))
print('LATENCY (successful assistant msgs, s)');[print(' ',k,v) for k,v in out.items()]
print('BURSTS',len(bursts))
bc=collections.Counter((b['provider'],b['resolved'].split(':')[0]) for b in bursts);print(bc)
for p in ('openai26','bai'):
    B=[b for b in bursts if b['provider']==p]
    print(p,'bursts',len(B),'errors in bursts',sum(b['n'] for b in B),'multi(>=3)',sum(b['n']>=3 for b in B),'max n',max(b['n'] for b in B),'recover min median',statistics.median([b['recover_s']/60 for b in B if b.get('recover_s')]) if B else 0,'sum recover h',round(sum((b.get('recover_s') or 0) for b in B)/3600,2))
print('TOP BURSTS');
for b in sorted(bursts,key=lambda b:-(b.get('recover_s') or 0))[:15]: print(' ',b['sid'],b['kind'],loc(b['start']),b['provider'],b['n'],b['resolved'],round((b.get('recover_s') or 0)/60,1),'min',dict(b['msgs'].most_common(2)))
print('SWITCH after err (<30min)',len(switches));[print(' ',s) for s in switches]
print('USER',userint);[print(' ',k,v[:6]) for k,v in userex.items()]
print('TASKPY',taskpy);print(len(taskpyerr));[print(' ',x) for x in taskpyerr[:25]]
print('SUPREQ',supreq);[print(' ',x) for x in supex[:12]]
print('SUBAGENT results',subres)
for k,v in subex.items():
    if k!='ok': print(' ',k);[print('    ',x) for x in v[:8]]
print('LONG TOOL >10min',len(stalls));[print(' ',s) for s in sorted(stalls,key=lambda s:-s[4])[:25]]
print('COMPACTIONS',len(compinfo));[print(' ',c) for c in compinfo[:100]]
