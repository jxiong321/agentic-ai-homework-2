"""Score Part G memory answers against traces; do not write interpretation."""
from __future__ import annotations
import csv
import json
from collections import Counter
from harness import ROOT
from harness.runner import is_free
from harness.formats import UNFINISHED
from harness.trace import read_trace


def main():
    entries=[]; details=[]
    for path in sorted((ROOT/'runs').glob('*.jsonl')):
        if path.name.startswith('_'): continue
        rows=read_trace(path)
        if not rows or rows[-1].get('type')!='run_end': continue
        start=rows[0]
        if start.get('lab')!='02' or start.get('way')!='notes' or start.get('issue') not in (4203,4204,4206) or is_free(start.get('backend','')): continue
        terminal=next((r.get('terminal_reason') for r in rows if r['type']=='end'),None)
        if terminal in UNFINISHED: continue
        seen=[]; compacted=False; questions=[]; seen_when_asked=None
        for row in rows:
            if row['type']=='tool_call':
                for p in row.get('paths',[]):
                    if p not in seen: seen.append(p)
            elif row['type']=='compaction' and not questions: compacted=True
            elif row['type']=='question':
                if seen_when_asked is None: seen_when_asked=list(seen)
                questions.append({'path':row['path'],'truth':'yes' if row['path'] in seen else 'no','answer':row['answer']})
        assert len(questions)==6 and compacted, f'{start["run_id"]}: missing questions or compaction'
        assert {q['path'] for q in questions if q['truth']=='yes'}==set(seen_when_asked[:3])
        right=sum(q['truth']==q['answer'] for q in questions)
        entry={'run_id':start['run_id'],'issue':start['issue'],'notes_shown':start['notes']=='on',
               'compacted':compacted,'questions':questions,'right':right}
        entries.append(entry)
        calls=[r for r in rows if r['type']=='model_call']
        details.append({'run_id':start['run_id'],'issue':start['issue'],'sweep':start['sweep'],
                        'notes':start['notes'],'right':right,'questions':6,'seen_questions':sum(q['truth']=='yes' for q in questions),
                        'compactions':sum(r['type']=='compaction' for r in rows),
                        'estimated_notes_tokens':sum(r['estimated_tokens'] for r in rows if r['type']=='notes_context'),
                        'total_tokens':sum(r['usage']['prompt_tokens']+r['usage']['output_tokens'] for r in calls),
                        'cost_usd':sum(r.get('cost_usd') or 0 for r in calls),'latency_s':rows[-1]['elapsed_s'],
                        'terminal_reason':terminal})
    assert len(entries)==12, f'Expected 12 completed memory experiments, found {len(entries)}'
    assert Counter((e['issue'],e['notes_shown']) for e in entries)==Counter({(i,on):2 for i in (4203,4204,4206) for on in (False,True)})
    p=ROOT/'reports/LAB_02.json'; report=json.loads(p.read_text()); report['context']=entries;p.write_text(json.dumps(report,indent=2)+'\n')
    with (ROOT/'reports/part_g_runs.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(details[0]));w.writeheader();w.writerows(details)
    lines=['<!-- BEGIN GENERATED CONTEXT TABLE -->','',
           '| Issue | Notes | Sweep | Correct / 6 | Compactions | Estimated notes tokens | Total tokens |',
           '|---|---|---|---|---|---|---|']
    for d in sorted(details,key=lambda d:(d['issue'],d['notes'],d['sweep'])):
        lines.append(f"| {d['issue']} | {d['notes']} | {d['sweep']} | {d['right']} | {d['compactions']} | {d['estimated_notes_tokens']} | {d['total_tokens']} |")
    lines += ['','Notes tokens are character-based estimates for the progress-file text included in executor and question requests, not an exact vendor token attribution. Total tokens come from provider usage.','',
              'Generated with `.venv/bin/python -m eval.summarize_context`; per-run evidence is in `reports/part_g_runs.csv`, and all six answers and trace-based truth labels are in `reports/LAB_02.json`.','', '<!-- END GENERATED CONTEXT TABLE -->']
    table='\n'.join(lines)+'\n'
    (ROOT/'reports/PART_G_TABLE.md').write_text('# Part G measured results\n\n'+table)
    p=ROOT/'reports/LAB_02.md'; text=p.read_text()
    if '<!-- BEGIN GENERATED CONTEXT TABLE -->' in text:
        a=text.index('<!-- BEGIN GENERATED CONTEXT TABLE -->');b=text.index('<!-- END GENERATED CONTEXT TABLE -->',a)+len('<!-- END GENERATED CONTEXT TABLE -->')
        text=text[:a]+table.rstrip()+text[b:]
    else:
        heading=next(line for line in text.splitlines() if line.startswith('## Part G'))
        text=text.replace(heading,heading+'\n\n'+table,1)
    p.write_text(text)
    for mode in ('off','on'):
        subset=[d for d in details if d['notes']==mode]
        print(mode,':',sum(d['right'] for d in subset),'/ 36 correct;',sum(d['estimated_notes_tokens'] for d in subset),'estimated notes tokens')
    print('Generated context results. Student analysis unchanged.')

if __name__=='__main__': main()
