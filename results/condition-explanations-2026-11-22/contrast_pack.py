"""Four training probes per previously admitted source. The contrast reverses one input requirement."""
PROBES={
 '6137':[
 ('original','Generate a minimal schema from temp.mdb that only includes table definitions without constraints, indexes, or comments. Omit field defaults.','omit'),
 ('same','For catalog.mdb, print table definitions only. Suppress constraints, indexes, comments and default values.','omit'),
 ('opposite','For catalog.mdb, print table definitions only. Suppress constraints, indexes and comments, but preserve field defaults.','retain'),
 ('distractor','For catalog.mdb, print table definitions only. Suppress constraints, indexes and comments, but preserve field defaults. The catalog was delivered on a Tuesday.','retain')],
 '7293':[
 ('original','List all functions present in a bitcode file read from stdin by invoking llvm-c-test with the appropriate option.','functions'),
 ('same','A new bitcode module is arriving on standard input. Use llvm-c-test to report the functions it contains.','functions'),
 ('opposite','A new bitcode module is arriving on standard input. Use llvm-c-test to print the entire module as textual IR.','module'),
 ('distractor','A new bitcode module is arriving on standard input. Use llvm-c-test to print the entire module as textual IR. The report will be archived on Tuesday.','module')]}
