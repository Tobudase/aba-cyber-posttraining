"""Authored training-only intents, disjoint from frozen development operations.

Two concrete scenarios per intent are correlated training examples, not new
independent validation cases. Commands are inert strings, never executed.
"""


def recipes():
    result = []
    def a(tool, family, query, command, optional, positional, rationale):
        result.append(dict(tool=tool, family=family, query=query, command=command,
            optional_args=optional, positional_args=positional, semantic_review=rationale))
    a('readpe', 'export-functions', 'Use readpe to show exported functions of file {f}.dll in CSV format.',
      'readpe --exports --format csv {f}.dll', {'--exports|-e': None, '--format|-f': 'csv'}, ['{f}.dll'], 'Exports selects exported functions; format selects CSV.')
    a('readpe', 'data-directories', 'Use readpe to display data directories of file {f}.exe in XML format.',
      'readpe --dirs --format xml {f}.exe', {'--dirs|-d': None, '--format|-f': 'xml'}, ['{f}.exe'], 'Dirs selects PE data directories; XML is a documented format.')
    a('readpe', 'section-headers', 'Use readpe to display the PE section headers of {f}.exe in CSV format.',
      'readpe --all-sections --format csv {f}.exe', {'--all-sections|-S': None, '--format|-f': 'csv'}, ['{f}.exe'], 'All-sections selects section headers, distinct from import/optional-header dev tasks.')
    a('readpe', 'all-headers', 'With readpe, show all PE headers of {f}.dll in XML format.',
      'readpe --all-headers --format xml {f}.dll', {'--all-headers|-H': None, '--format|-f': 'xml'}, ['{f}.dll'], 'All-headers requests every PE header, not one selected optional header.')
    a('pedis', 'section-disassembly', 'Use pedis to disassemble section .text of {f}.exe and emit CSV.',
      'pedis --section .text --format csv {f}.exe', {'--section|-s': '.text', '--format|-f': 'csv'}, ['{f}.exe'], 'Section chooses an entire section and format chooses CSV.')
    a('pedis', 'byte-offset-window', 'Use pedis to disassemble {n} bytes from file offset {offset} in {f}.exe.',
      'pedis --offset {offset} -n {n} {f}.exe', {'--offset|-o': '{offset}', '-n': '{n}'}, ['{f}.exe'], 'Offset is a raw file offset and -n counts bytes, unlike RVA/-i dev instructions.')
    a('pehash', 'all-piece-hashes', 'Use pehash to hash the file, sections and headers of {f}.exe with all supported hash types; emit XML.',
      'pehash --all --format xml {f}.exe', {'--all|-a': None, '--format|-f': 'xml'}, ['{f}.exe'], 'All requests file, sections and headers and the documented hash algorithms.')
    a('pehash', 'file-content-hashes', 'Use pehash to hash only the file content of {f}.dll and emit CSV.',
      'pehash --content --format csv {f}.dll', {'--content|-c': None, '--format|-f': 'csv'}, ['{f}.dll'], 'Content explicitly selects file content instead of header or named section.')
    a('pehash', 'indexed-section-hashes', 'Use pehash to hash only section number {index} of {f}.exe; section numbering starts at one.',
      'pehash --section-index {index} {f}.exe', {'--section-index': '{index}'}, ['{f}.exe'], 'Section-index accepts the positive one-based index documented in help.')
    a('peres', 'resource-information', 'With peres, show resource information from {f}.exe in text format without extracting anything.',
      'peres --info --format text {f}.exe', {'--info|-i': None, '--format|-f': 'text'}, ['{f}.exe'], 'Info requests resource information and does not request extraction.')
    a('peres', 'file-version-resource', 'Use peres to show File Version from the resource directory of {f}.dll.',
      'peres --file-version {f}.dll', {'--file-version|-v': None}, ['{f}.dll'], 'Lowercase -v/file-version is distinct from uppercase version of the tool.')
    a('jadx', 'single-class-output', 'Use jadx to decompile only class org.lab.{class_name} from {f}.apk and write it to {f}_Class.java.',
      'jadx --single-class org.lab.{class_name} --single-class-output {f}_Class.java {f}.apk',
      {'--single-class': 'org.lab.{class_name}', '--single-class-output': '{f}_Class.java'}, ['{f}.apk'], 'Both full class name and single-class output path are explicitly documented.')
    a('jadx', 'fallback-bad-code', 'Use jadx in fallback decompilation mode on {f}.apk, show inconsistent code, and write into {f}_review.',
      'jadx --decompilation-mode fallback --show-bad-code --output-dir {f}_review {f}.apk',
      {'--decompilation-mode|-m': 'fallback', '--show-bad-code': None, '--output-dir|-d': '{f}_review'}, ['{f}.apk'], 'Fallback is a documented mode; show-bad-code preserves inconsistent decompilations.')
    a('yara', 'named-rule-strings', 'Use yara with {f}.yar to scan {f}.bin, reporting only rule {rule} and printing its matching strings.',
      'yara --identifier {rule} --print-strings {f}.yar {f}.bin',
      {'--identifier|-i': '{rule}', '--print-strings|-s': None}, ['{f}.yar', '{f}.bin'], 'Identifier selects a rule name; rule file precedes scan target.')
    a('yara', 'bounded-directory-scan', 'Use yara rules {f}.yar to scan directory {f}_samples recursively with {threads} threads and a {timeout}-second timeout.',
      'yara --recursive --threads {threads} --timeout {timeout} {f}.yar {f}_samples',
      {'--recursive|-r': None, '--threads|-p': '{threads}', '--timeout|-a': '{timeout}'}, ['{f}.yar', '{f}_samples'], 'Recursive, thread count and timeout are distinct documented directory scan options.')
    a('yara', 'negated-rules', 'Use yara rules {f}.yar on file {f}.bin and print rules that are not satisfied.',
      'yara --negate {f}.yar {f}.bin', {'--negate|-n': None}, ['{f}.yar', '{f}.bin'], 'Negate prints rules that do not match; no compiled-rules or tag task is reused.')
    a('clamscan', 'recursive-without-summary', 'Use clamscan to scan {f}_uploads recursively and omit the final scan summary. Do not remove or move files.',
      'clamscan --recursive --no-summary {f}_uploads', {'--recursive|-r': None, '--no-summary': None}, ['{f}_uploads'], 'Recursive visits subdirectories; no-summary affects the final summary only.')
    a('clamscan', 'no-file-symlink-follow', 'Use clamscan to scan directory {f}_evidence recursively and never follow symbolic links to files.',
      'clamscan --recursive --follow-file-symlinks 0 {f}_evidence', {'--recursive|-r': None, '--follow-file-symlinks': '0'}, ['{f}_evidence'], 'Help defines follow-file-symlinks 0 as never; no destructive options.')
    a('clamdscan', 'multiscan-without-summary', 'Use clamdscan on directory {f}_queue, force MULTISCAN mode and omit the final summary.',
      'clamdscan --multiscan --no-summary {f}_queue', {'--multiscan|-m': None, '--no-summary': None}, ['{f}_queue'], 'Multiscan and no-summary are daemon-client options, distinct from stream/config dev tasks.')
    a('clamdscan', 'descriptor-all-matches', 'Use clamdscan to scan {f}.bin by passing its file descriptor to the configured local daemon, continuing within the file after the first match.',
      'clamdscan --fdpass --allmatch {f}.bin', {'--fdpass': None, '--allmatch|-z': None}, ['{f}.bin'], 'Fdpass passes a descriptor; allmatch continues after a match; daemon is assumed configured.')
    a('mmls', 'allocated-and-metadata', 'Use mmls to show allocated and metadata volumes from disk image {f}.dd.',
      'mmls -a -m {f}.dd', {'-a': None, '-m': None}, ['{f}.dd'], 'Lowercase -a and -m select allocated and metadata volumes; not uppercase -A unallocated dev task.')
    a('mmls', 'recursive-dos-tables', 'Use mmls with DOS volume-system type on {f}.dd and recursively look for partition tables in partitions.',
      'mmls -t dos -r {f}.dd', {'-t': 'dos', '-r': None}, ['{f}.dd'], 'Help says recursive search is DOS-only; query explicitly constrains DOS.')
    a('affcompare', 'page-content-differences', 'Use affcompare to examine differences only on page {page} of {f}_original.aff and {f}_copy.aff and print differing sector contents.',
      'affcompare -P {page} -c {f}_original.aff {f}_copy.aff', {'-P': '{page}', '-c': None}, ['{f}_original.aff', '{f}_copy.aff'], 'Capital -P limits a page; -c prints sector contents rather than just numbers.')
    a('affcompare', 'quiet-image-comparison', 'Use affcompare to compare {f}_first.aff and {f}_second.aff, producing no output except errors.',
      'affcompare -q {f}_first.aff {f}_second.aff', {'-q': None}, ['{f}_first.aff', '{f}_second.aff'], 'Quiet controls reporting, distinct from data-only and sector-number dev tasks.')
    a('affinfo', 'validate-page-hashes', 'Use affinfo to validate each stored page hash in image {f}.aff when those hashes are present.',
      'affinfo -v {f}.aff', {'-v': None}, ['{f}.aff'], 'Lowercase -v validates per-page hashes, not the entire-image SHA1 dev task.')
    a('affinfo', 'single-segment-information', 'Use affinfo to show information only about segment {segment} in {f}.aff.',
      'affinfo -s {segment} {f}.aff', {'-s': '{segment}'}, ['{f}.aff'], 'Lowercase -s selects one segment and takes a name, distinct from listing all segment names.')
    a('capinfos', 'capture-file-hashes', 'Use capinfos to print SHA256 and SHA1 hashes of saved capture {f}.pcapng.',
      'capinfos -H {f}.pcapng', {'-H': None}, ['{f}.pcapng'], 'Capital -H selects the documented capture file hashes.')
    a('capinfos', 'capture-size-statistics', 'Use capinfos to show file size and total captured-packet length in bytes for {f}.pcapng.',
      'capinfos -s -d {f}.pcapng', {'-s': None, '-d': None}, ['{f}.pcapng'], 'File size and sum of packet lengths are distinct size fields.')
    a('capinfos', 'capture-endpoint-times', 'Use capinfos to show timestamps of the earliest and latest packet in {f}.pcapng.',
      'capinfos -a -e {f}.pcapng', {'-a': None, '-e': None}, ['{f}.pcapng'], 'Earliest/latest timestamps are distinct from the duration/count dev task.')
    a('mergecap', 'merge-truncated-packets', 'Use mergecap to combine {f}_left.pcapng and {f}_right.pcapng into {f}_bounded.pcapng, truncating each packet to {snaplen} bytes.',
      'mergecap -s {snaplen} -w {f}_bounded.pcapng {f}_left.pcapng {f}_right.pcapng',
      {'-s': '{snaplen}', '-w': '{f}_bounded.pcapng'}, ['{f}_left.pcapng', '{f}_right.pcapng'], 'Snaplen truncates packet bytes; -w names output; all inputs share encapsulation.')
    a('mergecap', 'merge-pcap-output', 'Use mergecap to combine same-encapsulation captures {f}_one.pcap and {f}_two.pcap into {f}_legacy.pcap, explicitly selecting pcap output format.',
      'mergecap -F pcap -w {f}_legacy.pcap {f}_one.pcap {f}_two.pcap',
      {'-F': 'pcap', '-w': '{f}_legacy.pcap'}, ['{f}_one.pcap', '{f}_two.pcap'], 'Explicit file format is different from default merging/concatenation dev tasks; same encapsulation is a stated precondition.')
    a('editcap', 'remove-recent-duplicates', 'Use editcap to remove duplicate packets from {f}.pcapng using its default five-packet comparison window; write {f}_dedup.pcapng.',
      'editcap -d {f}.pcapng {f}_dedup.pcapng', {'-d': None}, ['{f}.pcapng', '{f}_dedup.pcapng'], 'Pinned help defines -d as duplicate removal with window5; no conflicting options.')
    a('editcap', 'split-by-packet-count', 'Use editcap to split {f}.pcapng into output files based on {n} packets per file, using {f}_parts.pcapng as the output name base.',
      'editcap -c {n} {f}.pcapng {f}_parts.pcapng', {'-c': '{n}'}, ['{f}.pcapng', '{f}_parts.pcapng'], 'Editcap adds output filename infixes; query says name base rather than guaranteeing one file.')
    a('editcap', 'discard-decryption-secrets', 'Use editcap to copy {f}.pcapng into {f}_sanitized.pcapng while discarding all embedded decryption secrets.',
      'editcap --discard-all-secrets {f}.pcapng {f}_sanitized.pcapng', {'--discard-all-secrets': None}, ['{f}.pcapng', '{f}_sanitized.pcapng'], 'Discard-all-secrets removes existing secret blocks; not a query about packet selection/truncation.')
    a('netstat', 'udp-statistics', 'Use netstat on the Linux host to display UDP protocol statistics.',
      'netstat --statistics --udp', {'--statistics|-s': None, '--udp|-u': None}, [], 'Statistics plus UDP selects protocol counters rather than listening TCP/route dev tasks.')
    a('netstat', 'interface-table', 'Use netstat to show the Linux network interface table with numeric output.',
      'netstat --interfaces --numeric', {'--interfaces|-i': None, '--numeric|-n': None}, [], 'Interfaces selects interface table; numeric disables name resolution.')
    a('rabin2', 'linked-libraries', 'Use rabin2 to list linked libraries from {f}.elf in JSON, without running the binary.',
      'rabin2 -l -j {f}.elf', {'-l': None, '-j': None}, ['{f}.elf'], 'Lowercase -l lists linked libraries, distinct from imports/sections.')
    a('rabin2', 'entrypoint-json', 'Use rabin2 to show the program entrypoint from {f}.elf in JSON.',
      'rabin2 -e -j {f}.elf', {'-e': None, '-j': None}, ['{f}.elf'], 'Lowercase -e is entrypoint; JSON formatting is orthogonal.')
    a('rabin2', 'data-section-strings', 'Use rabin2 to show data-section strings from {f}.elf, restricting string lengths to {minlen} through {maxlen} characters.',
      'rabin2 -z -N {minlen}:{maxlen} {f}.elf', {'-z': None, '-N': '{minlen}:{maxlen}'}, ['{f}.elf'], 'Single -z selects strings from the data section; -N accepts min:max.')
    a('fls', 'deleted-entry-paths', 'Use fls to list deleted entries reachable through existing directories in {f}.dd recursively, displaying full paths.',
      'fls -d -r -p {f}.dd', {'-d': None, '-r': None, '-p': None}, ['{f}.dd'], 'Fls recursion cannot follow deleted directories; query states reachable through existing directories.')
    a('fls', 'allocated-file-long-list', 'Use fls to show only undeleted file entries in long format from filesystem sector offset {sector} in {f}.dd.',
      'fls -u -F -l -o {sector} {f}.dd', {'-u': None, '-F': None, '-l': None, '-o': '{sector}'}, ['{f}.dd'], 'Undeleted, file-only and long view plus sector offset are supported independent selectors.')
    a('fsstat', 'filesystem-type', 'Use fsstat to display only the filesystem type of {f}.dd.',
      'fsstat -t {f}.dd', {'-t': None}, ['{f}.dd'], 'Type-only flag is explicit in help.')
    a('fsstat', 'ntfs-filesystem-offset', 'Use fsstat to inspect the NTFS filesystem starting at sector {sector} in {f}.dd.',
      'fsstat -f ntfs -o {sector} {f}.dd', {'-f': 'ntfs', '-o': '{sector}'}, ['{f}.dd'], 'Filesystem type and image offset are explicit; image is assumed NTFS at stated location.')
    a('istat', 'inode-run-list', 'Use istat to inspect inode {inode} of {f}.dd, displaying the run list instead of individual block addresses.',
      'istat -r {f}.dd {inode}', {'-r': None}, ['{f}.dd', '{inode}'], 'Image precedes inode and -r changes block-address display to run list.')
    a('istat', 'inode-time-context', 'Use istat for inode {inode} in {f}.dd with original-machine timezone GMT and time skew {seconds} seconds.',
      'istat -z GMT -s {seconds} {f}.dd {inode}', {'-z': 'GMT', '-s': '{seconds}'}, ['{f}.dd', '{inode}'], 'Timezone and skew are contextual interpretation options, not host clock modification.')
    a('yarac', 'warnings-as-errors', 'Use yarac to compile {f}.yar into {f}.yarc and fail compilation on warnings.',
      'yarac --fail-on-warnings {f}.yar {f}.yarc', {'--fail-on-warnings': None}, ['{f}.yar', '{f}.yarc'], 'Source rule file precedes compiled output; compiler fail-on-warnings is documented.')
    a('yarac', 'external-variable-compile', 'Rules in {f}.yar declare external integer variable sensitivity. Compile them with yarac setting sensitivity to {level}, writing {f}.yarc.',
      'yarac --define sensitivity={level} {f}.yar {f}.yarc', {'--define|-d': 'sensitivity={level}'}, ['{f}.yar', '{f}.yarc'], 'Query explicitly declares integer external variable; define uses VAR=VALUE syntax.')
    a('pesec', 'certificate-pem-output', 'Use pesec to write certificates from {f}.exe to {f}_cert.pem in PEM format.',
      'pesec --certoutform pem --certout {f}_cert.pem {f}.exe',
      {'--certoutform|-c': 'pem', '--certout|-o': '{f}_cert.pem'}, ['{f}.exe'], 'PEM output form and certificate output filename are documented; assumes embedded certificates exist.')
    a('pesec', 'security-features-xml', 'Use pesec to report security features of {f}.dll in XML.',
      'pesec --format xml {f}.dll', {'--format|-f': 'xml'}, ['{f}.dll'], 'Security feature inspection with explicit XML output is supported.')
    a('rva2ofs', 'relative-to-file-offset', 'Use rva2ofs to convert relative virtual address {offset} in {f}.exe to its raw file offset.',
      'rva2ofs {offset} {f}.exe', {}, ['{offset}', '{f}.exe'], 'Usage is RVA then FILE; assumes address belongs to the mapped image.')
    a('ofs2rva', 'file-to-relative-offset', 'Use ofs2rva to convert raw file offset {offset} in {f}.exe into a relative virtual address.',
      'ofs2rva {offset} {f}.exe', {}, ['{offset}', '{f}.exe'], 'Usage is raw offset then FILE; reverse direction from rva2ofs.')
    a('img_stat', 'image-type', 'Use img_stat to display only the image type of {f}.dd.',
      'img_stat -t {f}.dd', {'-t': None}, ['{f}.dd'], 'Image type is distinct from filesystem type; correct tool is named.')
    a('img_stat', 'image-sector-size', 'Use img_stat to report image details for {f}.dd, explicitly specifying a device sector size of {bytes} bytes.',
      'img_stat -b {bytes} {f}.dd', {'-b': '{bytes}'}, ['{f}.dd'], 'Sector size is an interpretation argument; it does not modify the image.')
    a('ndisasm', 'binary-mode-origin', 'Use ndisasm to disassemble {f}.bin in 64-bit mode with origin {offset}.',
      'ndisasm -b 64 -o {offset} {f}.bin', {'-b': '64', '-o': '{offset}'}, ['{f}.bin'], 'Synopsis documents -b bits and -o origin; binary is never executed.')
    a('ndisasm', 'skip-binary-header', 'Use ndisasm to disassemble {f}.bin in 16-bit mode, skipping its {n}-byte header.',
      'ndisasm -b 16 -e {n} {f}.bin', {'-b': '16', '-e': '{n}'}, ['{f}.bin'], 'Skip-header -e and processor bits -b have explicit help descriptions.')
    return result
