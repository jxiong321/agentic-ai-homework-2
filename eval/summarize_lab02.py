"""Generate Part F measurements only; leave the student's analysis untouched.
Run: .venv/bin/python -m eval.summarize_lab02
"""
from __future__ import annotations
import csv
import json
import math
from collections import Counter, defaultdict
from statistics import mean
import yaml
from agent.detectors import repeat_check
from eval.check_triage import check
from harness import ROOT
from harness.runner import is_free
from harness.formats import UNFINISHED
from harness.trace import read_trace
from harness.tracker import Tracker

CONFIGS = ('agent','planned_off','planned_self','planned_external')

class DraftTracker:
    def __init__(self, body): self.body = body
    def comments(self, **kwargs): return [{'body':self.body}]

def main():
    answers={int(k):v for k,v in yaml.safe_load((ROOT/'fixtures/answers.yaml').read_text())['eval'].items()}
    tracker=Tracker(ROOT)
    groups={c:[] for c in CONFIGS}
    for path in sorted((ROOT/'runs').glob('*.jsonl')):
        if path.name.startswith('_'): continue
        records=read_trace(path)
        if not records or records[0].get('type')!='run_start' or records[-1].get('type')!='run_end': continue
        start=records[0]
        if start.get('lab')!='02' or is_free(start.get('backend','')) or start.get('issue') not in answers: continue
        config='agent' if start.get('way')=='agent' else 'planned_'+start.get('critique','off') if start.get('way')=='planned' else None
        if config not in groups: continue
        terminal=next((r.get('terminal_reason') for r in records if r['type']=='end'),None)
        if terminal in UNFINISHED: continue
        groups[config].append((start,records,terminal))
    for config,items in groups.items():
        assert len(items)==18, f'{config}: expected 18 finished runs, found {len(items)}'
        assert Counter(s['issue'] for s,_,_ in items)==Counter({i:3 for i in answers}),f'{config}: incomplete issue counts'
        assert len({(s['issue'],s['sweep']) for s,_,_ in items})==18,f'{config}: duplicate issue/sweep'
    results={}; details=[]; grouped_overhead=[]
    for config,items in groups.items():
        per_issue=Counter({str(i):0 for i in answers}); sweeps=Counter()
        counts=Counter(); arrays=defaultdict(list); buckets=defaultdict(list)
        for start,records,terminal in items:
            rid=start['run_id']; issue=start['issue']; answer=answers[issue]
            ok=check(tracker,rid,issue,answer)
            calls=[r for r in records if r['type']=='model_call']
            prompt=sum(c['usage']['prompt_tokens'] for c in calls)
            output=sum(c['usage']['output_tokens'] for c in calls)
            purpose_tokens=lambda purposes: sum(c['usage']['prompt_tokens'] for c in calls if c.get('purpose') in purposes)
            plan_share=purpose_tokens(('plan','revise'))/prompt if prompt else 0
            plan_only=purpose_tokens(('plan',))/prompt if prompt else 0
            critique_share=purpose_tokens(('critique',))/prompt if prompt else 0
            rounds=[r for r in records if r['type']=='critique']
            revisions=sum(r['type']=='revision' for r in records)
            changed=any(r.get('changed') for r in rounds)
            before=check(DraftTracker(rounds[0]['draft']),rid,issue,answer) if rounds else None
            held=bool(rounds) and rounds[-1]['result']=='fail' and not tracker.comments(run_id=rid)
            repeats=bool(repeat_check(records)); off=sum(r['type']=='off_plan' for r in records)
            cost=sum(c.get('cost_usd') or 0 for c in calls)
            per_issue[str(issue)]+=ok; sweeps[start['sweep']]+=ok
            counts.update({'passes':int(ok),'drafts_changed':int(changed),'drafts_fixed':int(changed and not before and ok),
                           'drafts_broken':int(changed and before and not ok),'drafts_held':int(held),
                           'runs_with_repeat':int(repeats),'off_plan':off})
            for key,value in [('tokens',prompt+output),('latency',records[-1]['elapsed_s']),('plan',plan_share),
                              ('critique',critique_share),('revisions',revisions),('rounds',len(rounds)),('cost',cost)]:
                arrays[key].append(value)
            buckets[len(calls)].append(plan_only)
            comments=tracker.comments(run_id=rid,issue=issue)
            details.append({'configuration':config,'run_id':rid,'issue':issue,'sweep':start['sweep'],
                            'passed':ok,'terminal_reason':terminal,'model_calls':len(calls),'tokens':prompt+output,
                            'latency_s':records[-1]['elapsed_s'],'cost_usd':cost,'plan_overhead_share':plan_share,
                            'plan_only_share':plan_only,'critique_overhead_share':critique_share,'revisions':revisions,
                            'revision_rejections':sum(r['type']=='revision' and not r['valid'] for r in records),
                            'schema_rejections':sum(r['type']=='schema' for r in records),
                            'review_rounds':len(rounds),'draft_changed':changed,'initial_draft_passed':before,
                            'held':held,'repeat':repeats,'off_plan':off,
                            'first_draft':rounds[0]['draft'] if rounds else '',
                            'final_draft':rounds[-1]['draft'] if rounds else '',
                            'posted_comment':comments[0]['body'] if len(comments)==1 else '',
                            'review_reasons':json.dumps([r['reason'] for r in rounds if r.get('reason')])})
        planned=config!='agent'; second=config in ('planned_self','planned_external')
        results[config]={'runs':len(items),'passes':counts['passes'],'per_issue':dict(sorted(per_issue.items())),
                         'sweep_min':min(sweeps.values()),'sweep_max':max(sweeps.values()),
                         'mean_tokens':mean(arrays['tokens']),
                         'p50_latency_s':sorted(arrays['latency'])[math.ceil(len(items)*.5)-1],
                         'max_latency_s':max(arrays['latency']),
                         'plan_overhead_share':mean(arrays['plan']) if planned else None,
                         'critique_overhead_share':mean(arrays['critique']) if second else None,
                         'runs_with_repeat':counts['runs_with_repeat'],'off_plan':counts['off_plan'] if planned else None,
                         'revisions_mean':mean(arrays['revisions']) if planned else None,'revisions_max':max(arrays['revisions']) if planned else None,
                         'rounds_mean':mean(arrays['rounds']) if second else None,'rounds_max':max(arrays['rounds']) if second else None,
                         **{k:counts[k] if second else None for k in ('drafts_changed','drafts_fixed','drafts_broken','drafts_held')}}
        if planned:
            for n,shares in sorted(buckets.items()):
                grouped_overhead.append({'configuration':config,'model_calls':n,'runs':len(shares),'mean_plan_only_share':mean(shares)})
    report_path=ROOT/'reports/LAB_02.json'; report=json.loads(report_path.read_text()); report['results']=results
    report_path.write_text(json.dumps(report,indent=2)+'\n')
    def save_csv(name,rows):
        with (ROOT/'reports'/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    save_csv('part_f_runs.csv',details); save_csv('part_f_plan_overhead.csv',grouped_overhead)
    def fmt(v): return '' if v is None else f'{v:.2f}' if isinstance(v,float) else str(v)
    def row(label,values): return '| '+label+' | '+' | '.join(values)+' |'
    table=['| Measure | Agent | Planned, off | Planned, self | Planned, external |','|---|---|---|---|---|']
    def add(label,fn): table.append(row(label,[fn(results[c],c) for c in CONFIGS]))
    add('Passes, of 18',lambda r,c:str(r['passes']))
    add('Per issue, 4201–4206, each of 3',lambda r,c:', '.join(str(v) for v in r['per_issue'].values()))
    add('Sweep passes: lowest–highest, of 6',lambda r,c:f"{r['sweep_min']}–{r['sweep_max']}")
    add('Mean tokens per run',lambda r,c:f"{r['mean_tokens']:,.1f}")
    add('Latency seconds: median / slowest',lambda r,c:f"{r['p50_latency_s']:.2f} / {r['max_latency_s']:.2f}")
    for label,key in [('Plan + revision prompt share, mean','plan_overhead_share'),('Review prompt share, mean','critique_overhead_share')]:
        add(label,lambda r,c,k=key:'' if r[k] is None else f'{r[k]:.1%}')
    for label,key in [('Runs with an exact repeat','runs_with_repeat'),('Off-plan attempts','off_plan')]: add(label,lambda r,c,k=key:fmt(r[k]))
    for label,prefix in [('Revisions per run: mean / maximum','revisions'),('Review rounds per run: mean / maximum','rounds')]:
        add(label,lambda r,c,p=prefix:'' if r[p+'_mean'] is None else f"{r[p+'_mean']:.2f} / {r[p+'_max']}")
    add('Drafts changed / fixed / broken',lambda r,c:'' if r['drafts_changed'] is None else ' / '.join(str(r[k]) for k in ('drafts_changed','drafts_fixed','drafts_broken')))
    add('Drafts held',lambda r,c:fmt(r['drafts_held']))
    add('Total cost, USD (harness prices)',lambda r,c:f"${sum(d['cost_usd'] for d in details if d['configuration']==c):.4f}")
    extra=['','Plan-call-only prompt share, grouped by number of model calls:','',
           '| Configuration | Model calls per run | Runs | Mean plan-only share |','|---|---|---|---|']
    extra += [row(g['configuration'],[str(g['model_calls']),str(g['runs']),f"{g['mean_plan_only_share']:.1%}"]) for g in grouped_overhead]
    table_text='\n'.join(table+extra)+'\n'
    (ROOT/'reports/PART_F_TABLE.md').write_text('# Part F measured results\n\n'+table_text)
    md=ROOT/'reports/LAB_02.md'; text=md.read_text(); begin=text.index('| Measure',text.index('## Part F')); end=text.index('1. **What did the plan buy',begin)
    text=text[:begin]+table_text+'\nGenerated by `eval/summarize_lab02.py` with `.venv/bin/python -m eval.summarize_lab02`. Per-run evidence: `reports/part_f_runs.csv`; grouped overhead: `reports/part_f_plan_overhead.csv`. Analysis below is left for the student.\n\n'+text[end:]
    md.write_text(text)
    print('\n'.join(table))
    print('Verified 72 finished runs; generated tables, per-run CSV, and LAB_02.json results. Analysis unchanged.')

if __name__=='__main__': main()
