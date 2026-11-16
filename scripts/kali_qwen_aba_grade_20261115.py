"""Frozen, explicit DEV utility + old per-case retention score, no LLM judge."""
import collections,math

def grade(metadata, native_by_id, behavior_by_id, baseline_native_by_id, baseline_behavior_by_id):
 new=metadata['new46'];old=metadata['old64_ids'];hist=set(metadata['historical_correct13']);assert len(hist)==13
 assert set(new)<=set(native_by_id) and set(old)<=set(native_by_id)
 def utility(verdicts):
  groups=collections.defaultdict(list)
  for ident,row in new.items():groups[row['group']].append(verdicts[ident]=='fixture_pass')
  return math.fsum(sum(v)/len(v) for v in groups.values())/len(groups)*100
 base_correct={i for i in old if baseline_native_by_id[i]['strict']};correct={i for i in old if native_by_id[i]['strict']}
 oldmean=math.fsum(native_by_id[i]['native'] for i in old)/len(old)*100;basemean=math.fsum(baseline_native_by_id[i]['native'] for i in old)/len(old)*100
 retained=len(correct&hist);lost=len(hist-correct);trunc=sum(native_by_id[i]['truncated'] for i in list(new)+old);early=sum(native_by_id[i].get('early_EOS',False) for i in list(new)+old)
 checks={'old_native_floor':oldmean>=basemean-2,'historical13_retention_floor':retained>=11,'paired_E0_retention_floor':len(correct&base_correct)>=math.ceil(.8*len(base_correct)),'no_truncation_or_earlyEOS':trunc==early==0}
 operational=utility(behavior_by_id);base_operational=utility(baseline_behavior_by_id);raw=operational-base_operational+.25*(oldmean-basemean)-10*lost/13
 score=raw if all(checks.values()) else -100-lost-trunc
 return {'score':score,'raw_score':raw,'eligible':all(checks.values()),'checks':checks,'utility_points':operational,'baseline_utility_points':base_operational,'old_native_points':oldmean,'baseline_old_native_points':basemean,'historical_retained':retained,'historical_lost':lost,'paired_E0_retained':len(correct&base_correct),'paired_E0_correct_count':len(base_correct),'strict_total':len(correct),'unknown_count':sum(behavior_by_id[i].startswith('unknown') for i in new),'truncated':trunc,'early_EOS':early,'scope':'Certified operational utility under frozen finite admission; UNKNOWN is unresolved, not semantic failure. No official TEST.'}
