"""Versioned decoding guard: repeated token n-grams inside generated output only.

No prompt tokens, task IDs, tool names, labels or reference answers are inspected.
This is a decoding-protocol change, not a claim that raw model weights improved.
"""


def banned_next_tokens(tokens, size=8):
    if size<2:raise ValueError('An n-gram of at least two tokens is required')
    if len(tokens)+1<size:return set()
    prefix=tuple(tokens[-(size-1):])
    return {tokens[i+size-1] for i in range(len(tokens)-size+1)
            if tuple(tokens[i:i+size-1])==prefix}


class CommandNGramGuard:
    def __init__(self,tokenizer,prompt_length,size=8):
        self.tokenizer=tokenizer;self.prompt_length=prompt_length;self.size=size
        self.starts=None;self.markers=None;self.events=[]

    def __call__(self,input_ids,scores):
        rows=input_ids.detach().cpu().tolist()
        if self.starts is None:self.starts=[None]*len(rows);self.markers=[-1]*len(rows)
        if len(rows)!=len(self.starts):raise ValueError('This guard is validated for greedy decoding only')
        for index,row in enumerate(rows):
            text=self.tokenizer.decode(row[self.prompt_length:],skip_special_tokens=False)
            marker=text.rfind('<output>')
            if marker<0:continue
            if marker!=self.markers[index]:
                self.markers[index]=marker;self.starts[index]=len(row)
            if text.rfind('</output>')>marker:self.starts[index]=None
            start=self.starts[index]
            if start is None:continue
            banned=banned_next_tokens(row[start:],self.size)
            if banned:
                top=int(scores[index].argmax())
                scores[index,list(banned)]=-float('inf')
                if len(self.events)<512:self.events.append({'row':index,'generated_tokens':len(row)-self.prompt_length,
                    'banned_ids':sorted(banned),'changed_greedy_choice':top in banned})
        return scores
