"""Execute only fixed benign fixtures, never dataset/model command strings."""
import hashlib,json,os,platform,shutil,socket,struct,subprocess,tempfile
from pathlib import Path

def run(argv,cwd):
 p=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=20)
 return {'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def main():
 with tempfile.TemporaryDirectory() as temp:
  d=Path(temp)
  # Three synthetic Ethernet/IPv4/UDP DNS queries; no live capture or external traffic.
  question=b'\x03lab\x07example\x00'+struct.pack('!HH',1,1)
  dns=struct.pack('!HHHHHH',7,0x0100,1,0,0,0)+question
  udp=struct.pack('!HHHH',45000,53,8+len(dns),0)+dns
  ip=struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(udp),1,0,64,17,0,socket.inet_aton('192.0.2.1'),socket.inet_aton('192.0.2.2'))
  total=sum(struct.unpack('!10H',ip));total=(total&65535)+(total>>16);total=(total&65535)+(total>>16)
  ip=ip[:10]+struct.pack('!H',~total&65535)+ip[12:]
  packet=bytes.fromhex('00112233445566778899aabb0800')+ip+udp
  raw=struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)
  for i in range(3):raw+=struct.pack('<IIII',1700000000+i,0,len(packet),len(packet))+packet
  (d/'fixture.pcap').write_bytes(raw)
  visible=run(['tshark','-n','-r','fixture.pcap','-Y','dns'],d)
  quiet=run(['tshark','-n','-q','-r','fixture.pcap','-Y','dns'],d)
  packet_check={'visible_rc':visible['returncode'],'quiet_rc':quiet['returncode'],'visible_lines':len(visible['stdout'].strip().splitlines()),'quiet_stdout_bytes':len(quiet['stdout'].encode())}
  packet_check['pass']=visible['returncode']==quiet['returncode']==0 and packet_check['visible_lines']==3 and packet_check['quiet_stdout_bytes']==0
  kept=run(['editcap','-r','fixture.pcap','kept.pcapng','2-3'],d)
  counted=run(['tshark','-n','-r','kept.pcapng','-T','fields','-e','frame.number'],d)
  range_check={'editcap_rc':kept['returncode'],'packet_count':len(counted['stdout'].strip().splitlines())}
  range_check['pass']=kept['returncode']==counted['returncode']==0 and range_check['packet_count']==2
  (d/'fixture.yar').write_text('rule fixture_match { strings: $a = "KALI_FIXTURE_MARKER" condition: $a }\n')
  (d/'fixture.bin').write_bytes(b'KALI_FIXTURE_MARKER')
  good=run(['yara','fixture.yar','fixture.bin'],d);wrong=run(['yara','fixture.bin','fixture.yar'],d)
  yara_check={'rules_first_rc':good['returncode'],'target_first_rc':wrong['returncode'],'pass':good['returncode']==0 and 'fixture_match' in good['stdout'] and wrong['returncode']!=0}
  listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1);port=listener.getsockname()[1]
  full=run(['netstat','--listening','--tcp','--numeric','--programs'],d);short=run(['netstat','--listening','--tcp','--numeric','--program'],d)
  extract=lambda result:[x for x in result['stdout'].splitlines() if f':{port} ' in x]
  a,b=extract(full),extract(short);listener.close()
  net_check={'full_rc':full['returncode'],'abbreviated_rc':short['returncode'],'same_fixture_row':a==b and len(a)==1}
  net_check['pass']=full['returncode']==short['returncode']==0 and net_check['same_fixture_row']
  pe_check={'pescan_binary_present':shutil.which('pescan') is not None,'pe_scan_binary_present':shutil.which('pe-scan') is not None,'scope':'Installed executable names only; no PE semantic fixture'}
  versions=run(['dpkg-query','-W','-f=${Package} ${Version}\n','tshark','wireshark-common','yara','net-tools','pev'],d)
  checks={'tshark_quiet_suppresses_packet_output':packet_check,'editcap_range_keeps_two_packets':range_check,'yara_rules_before_target':yara_check,'netstat_unique_long_option_abbreviation':net_check}
  result={'status':'PASS' if all(c['pass'] for c in checks.values()) else 'FAILED','platform':platform.system(),'packages':versions['stdout'].strip().splitlines(),'fixture_sha256':hashlib.sha256(raw).hexdigest(),'checks':checks,'executable_name_check':pe_check,'dataset_or_model_commands_executed':0,'external_targets_contacted':0,'scope':'Selected benign Linux fixture semantics, not all48labels or the exact original Kali package versions'}
  print('KALI_SEMANTIC_RESULT='+json.dumps(result),flush=True)
  if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
