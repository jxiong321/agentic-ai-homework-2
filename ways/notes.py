"""Part G: progress notes and compaction, isolated from the measured planned way."""
from __future__ import annotations
import copy
import json
import re
from harness import ROOT
from harness.scripted import estimate_tokens
from harness.trace import read_trace
from tools.search_repo import EXCLUDED_DIRS
from ways.planned import PlannedExecutor, prepare_plan

COMPACT_AT = 600

def parse_memory_answers(text):
    """Normalize six explicit answers without guessing or grading them."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        values = json.loads(cleaned)
    except (ValueError, TypeError):
        values = None
    if isinstance(values, list) and len(values) == 6:
        answers = []
        for value in values:
            if isinstance(value, bool):
                answers.append("yes" if value else "no")
            elif isinstance(value, str) and value.lower().strip() in ("yes", "no", "true", "false"):
                answers.append("yes" if value.lower().strip() in ("yes", "true") else "no")
            else:
                raise ValueError("Memory probe contains an unsupported answer")
        return answers
    # The prompt explicitly allows one uniform yes/no for all questions.
    if cleaned.lower() in ("yes", "no"):
        return [cleaned.lower()] * 6
    answers = re.findall(r"\b(?:yes|no)\b", cleaned.lower())
    if len(answers) == 6:
        return answers
    raise ValueError("Memory probe did not return six yes/no answers")


class DeferredEnd:
    """Hold the terminal event until the memory questions have been recorded."""
    def __init__(self, trace):
        self.trace = trace
        self.pending = None
    def __getattr__(self, name): return getattr(self.trace, name)
    def end(self, terminal_reason, detail=''):
        self.pending = (terminal_reason, detail)
    def finish(self):
        if self.pending is not None:
            self.trace.end(*self.pending)

class NotesExecutor(PlannedExecutor):
    def __init__(self, ctx, plan):
        super().__init__(ctx, plan)
        self.compactions = 0
        self.asked = False
        self.steps_done = []
        self.seen_paths = []
        self.write_progress()

    def write_progress(self):
        self.ctx.progress_path.parent.mkdir(parents=True, exist_ok=True)
        self.ctx.progress_path.write_text(json.dumps({
            'about': 'Steps executed and repository paths this run has already seen; not a to-do list.',
            'steps_done': self.steps_done, 'paths': self.seen_paths,
        }, indent=2)+'\n')

    def include_notes(self, messages, call_kind):
        if self.ctx.notes == 'on':
            text = self.ctx.progress_path.read_text()
            messages.append({'role':'user','content':text})
            self.ctx.trace.event('notes_context', call_kind=call_kind,
                                 estimated_tokens=estimate_tokens(text))
        return messages

    def compact(self, force=False):
        tokens = estimate_tokens(self.history)
        if not force and tokens <= COMPACT_AT:
            return
        # Retain the newest result verbatim whenever an older entry exists.
        split = max(1, len(self.history)-1)
        older, recent = self.history[:split], self.history[split:]
        response = self.ctx.client.create(
            system=(ROOT/'prompts/compact_history.md').read_text(),
            messages=[{'role':'user','content':json.dumps(older)}], tools=None)
        self.ctx.trace.model_call(0,response)
        self.history = [{'summary':response.text}] + recent
        self.compactions += 1
        self.ctx.trace.event('compaction', threshold=COMPACT_AT,tokens=tokens,
                             summary_tokens=estimate_tokens(response.text),
                             retained_entries=len(recent))

    def messages_for(self, step):
        self.compact()
        return self.include_notes(super().messages_for(step),'execute')

    def after_step(self, step, result):
        self.steps_done.append(step['id'])
        for path in self.step_results[-1]['paths']:
            if path not in self.seen_paths: self.seen_paths.append(path)
        self.write_progress()
        self.compact()

    def fill_arguments(self, number, step, template):
        if step['tool']=='post_comment': self.ask_questions()
        return super().fill_arguments(number,step,template)

    def before_comment(self, step, args):
        self.ask_questions()
        return args  # Part G always has review off.

    def ask_questions(self):
        if self.asked: return
        if not self.compactions: self.compact(force=True)
        else: self.compact()
        # Ground the question selection in the trace, not model claims.
        seen = []
        for row in read_trace(self.ctx.trace.path):
            if row.get('type')=='tool_call':
                for path in row.get('paths',[]):
                    if path not in seen: seen.append(path)
        repo = self.ctx.root/'fixtures/repo'
        unseen = [p.relative_to(repo).as_posix() for p in sorted(repo.rglob('*'))
                  if p.is_file() and not (set(p.relative_to(repo).parts) & EXCLUDED_DIRS)
                  and p.relative_to(repo).as_posix() not in seen]
        paths = seen[:3] + unseen[:6-len(seen[:3])]
        # Interleave positives and negatives so their order does not disclose truth.
        paths = sorted(paths)
        if len(paths)!=6: raise ValueError('Need six distinct repository paths for the memory probe')
        questions=[f'Has this run seen {path}: did a search return it, or did you read it?' for path in paths]
        messages=[{'role':'user','content':json.dumps({'history':self.history,'questions':questions})}]
        response=self.ctx.client.create(system=(ROOT/'prompts/memory_questions.md').read_text(),
                                        messages=self.include_notes(messages,'questions'),tools=None)
        self.ctx.trace.model_call(0,response)
        answers=parse_memory_answers(response.text)
        for path,answer in zip(paths,answers):
            self.ctx.trace.event('question',path=path,answer=answer)
        self.asked=True


def run(ctx):
    local=copy.copy(ctx)
    local.critique='off'
    deferred=DeferredEnd(ctx.trace)
    local.trace=deferred
    plan=prepare_plan(local)
    executor=NotesExecutor(local,plan if plan is not None else {'steps':[]})
    if plan is not None: executor.run()
    executor.ask_questions()
    deferred.finish()
