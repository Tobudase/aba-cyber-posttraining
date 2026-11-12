#!/usr/bin/env python3
"""Check real private receipts; export aggregate consistency evidence only."""
import argparse,gzip,hashlib,json
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=a.study
 receipts={c:json.loads((s/c/'run/adapter-bundle-private/training-receipt.json').read_text()) for c in ['P11','P12','P13','P14']}
 for c,r in receipts.items():
  assert json.loads((s/c/'run/host-private.json').read_text())['status']=='COLLECTED'
  assert r['optimizer_steps']==r['nonzero_gradient_steps']==733 and r['supervised_token_presentations']==17439 and r['DEV_or_validation_gradient_rows']==0
 base=[(s/c/'run/base-predictions-private.json').read_bytes() for c in receipts];assert all(b==base[0] for b in base)
 assert len({receipts[c]['initial_lora_sha256'] for c in ['P11','P12','P14']})==1
 assert receipts['P13']['initial_lora_sha256']!=receipts['P12']['initial_lora_sha256']
 assert receipts['P12']['epoch_order_sha256']==receipts['P14']['epoch_order_sha256']
 assert receipts['P12']['trace'][0]==receipts['P14']['trace'][0],'LR must not change loss/gradient before the first update'
 assert receipts['P11']['trace'][:14]==receipts['P12']['trace'][:14]
 result={'status':'PASS_REAL_FOUR_ARM_CONSISTENCY','arms':['P11','P12','P13','P14'],'all_fresh_base_DEV128_bytes_identical':True,'base_predictions_sha256':hashlib.sha256(base[0]).hexdigest(),'seed42_initial_LoRA_bytes_identical_P11_P12_P14':True,'seed43_P13_initial_LoRA_differs':True,'P12_P14_epoch_order_identical':True,'P12_P14_first_pre_update_loss_gradient_token_record_identical':True,'P12_P14_first_pre_update_record':receipts['P12']['trace'][0],'P11_P12_pre_replacement_14_step_records_identical':True,'optimizer_steps_per_arm':733,'supervised_tokens_per_arm':17439,'DEV_gradient_rows':0,'scope':'Necessary implementation consistency checks for these runs;not an independent replication,unique historical root-cause proof,or statistical-stability guarantee.'}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'real_training_updates':2932}))
if __name__=='__main__':main()
