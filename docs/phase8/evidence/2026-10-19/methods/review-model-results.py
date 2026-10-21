"""Manual semantic labels were fixed before calls. This reports validity separately from correctness, checks paired wire identity, and retains failures; model explanations/confidence are not independent evidence."""
import hashlib,json
from pathlib import Path
base=Path('/private/tmp/noye-phase8-20261019')
paired=json.loads((base/'support-v24-resumed.json').read_text());assert len(paired['rows'])==16
rows=paired['rows'];calls=[c for c in paired['model_calls'] if c['task']=='verify_support'];assert len(calls)==16
for n,case in enumerate(paired['cases']):
 pair=[]
 for c in calls:
  req=c['request'];p=req.get('prompt') or req['messages'][-1]['content']
  if json.loads(p)['claims'][0]['text']==case['text']:
   pair.append({'model':req['model'],'system':req.get('system') or req['messages'][0]['content'],'prompt':p,'format':req['format'],'options':req['options']})
 assert len(pair)==2 and pair[0]==pair[1],case['id']
report={'method':__doc__,'paired_wire_identity':{'cases':8,'equal_system_user_schema_model_options':True,'differences':'thinking false/generate versus thinking true/chat only; JSON object order does not affect the comparison'},'results':[]}
for mode in [False,True]:
 group=[x for x in rows if x['thinking']==mode]
 report['results'].append({'thinking':mode,'completed':len(group),'valid':sum(x['valid'] for x in group),'correct':sum(x.get('correct',False) for x in group),'false_approvals':[x['id'] for x in group if x['valid'] and not x['expected'] and x.get('actual')],'false_rejections':[x['id'] for x in group if x['valid'] and x['expected'] and not x.get('actual')],'invalid':[x['id'] for x in group if not x['valid']],'new_controls_correct':sum(x.get('correct',False) for x in group if not x['regression']),'new_controls_total':4,'known_regressions_correct':sum(x.get('correct',False) for x in group if x['regression']),'known_regressions_total':4,'sum_completed_row_seconds':round(sum(x['seconds'] for x in group),3)})
report['review']={'known-unsafe-comparison':'Both modes approve an unsupported instrumental connection between independently reported stored volume and log-file use. The full compound statement is not entailed.','known-unsafe-wiki-summary':'Off approves SQLite as the means for capacity. On reaches the output limit; a refused incomplete answer is not a correct negative classification.','known-four-day-translation':'Off misreads faithful four-day translation. On returns the expected positive.','known-adjoining-backups':'Both reject normal adjoining-sentence subject continuity despite no competing subject in the supplied passage.','conclusion':'No default thinking change is adopted: the known unsafe comparison remains falsely approved and Wiki reasoning fails to finish. The fresh subset is too small to establish general quality.','latency_limit':'Paired order is counterbalanced but load/cache and external download effects were not controlled. Summed row times are observed work only, not a causal latency benchmark. Original interrupted in-flight work is excluded.'}
alt=json.loads((base/'alternative-support.json').read_text());assert len(alt['rows'])==8
report['alternative']={'model':'gemma4:e2b-it-qat','method':'Same fixed controls, unchanged production v24 non-thinking generate contract; inherited model sampling differs; diagnostic, not new holdouts or full workflow acceptance.','valid':sum(x['valid'] for x in alt['rows']),'correct':sum(x.get('correct',False) for x in alt['rows']),'rows':alt['rows'],'seconds':alt['seconds'],'acceptance':'No adoption follows from component scores alone.'}
examples=json.loads((base/'examples-gemma.json').read_text());assert len(examples['rows'])==16
report['examples']={'model':examples['model'],'valid':sum(x['valid'] for x in examples['rows']),'correct':sum(x.get('correct',False) for x in examples['rows']),'prior_correct':sum(x.get('correct',False) for x in examples['rows'] if not x['fresh']),'fresh_correct':sum(x.get('correct',False) for x in examples['rows'] if x['fresh']),'rows':examples['rows'],'seconds':examples['seconds'],'decision':'Not adopted: both prior unsupported relationship claims remain falsely approved. Fresh controls do not have paired baseline calls.'}
focus=json.loads((base/'link-focus.json').read_text());assert len(focus['rows'])==8
report['link_focus']={'valid':sum(x['valid'] for x in focus['rows']),'correct':sum(x.get('correct',False) for x in focus['rows']),'rows':focus['rows'],'seconds':focus['seconds'],'decision':'Not adopted. One HTTP 500, three non-verbatim extracted-link failures, and one valid false approval of the isolated unsafe storage/log-file relationship. Four valid judgments, three correct, across eight intended cases; refusals are not successful factual generation.'}
report['inputs_sha256']={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in ['support-v24-resumed.json','alternative-support.json','support-v24-fresh-controls.json','examples-gemma.json','examples-fresh-controls.json','link-focus.json']}
(base/'review-model-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['paired_wire_identity','results','alternative']},ensure_ascii=False))
