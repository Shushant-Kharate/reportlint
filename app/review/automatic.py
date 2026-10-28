"""Automatic preparation with immutable, source-backed clarification revisions."""
from collections import defaultdict
from hashlib import sha256
import re
from app.analysis.plain_language import interpret, DIRECTIVE
from app.analysis.template_requirements import property_key, same_value
from app.models.template_analysis import (SourceEvidence, RuleCandidate, RequirementDisposition,
    ProfileCandidate, ChapterCandidate, TemplateAnalysis)
from app.review.models import (ReviewPatch, CandidateDecision, LedgerDecision, ProfileReview,
    ChapterReview)
from app.review.service import apply_review, publish, guard_edit, ReviewError

MARKER = 'AUTOMATIC_PREPARATION_V1: explicit instructions take priority over sample appearance; unresolved instructions remain visible.'


def add_interpretation(analysis, source, parsed):
    evidence_ids={s.source_id for s in analysis.evidence}
    if source.source_id not in evidence_ids: analysis.evidence.append(source)
    ids=[]
    for scope,value in parsed.values:
        identity=source.source_id+'|'+scope+'|'+value.model_dump_json()
        cid='auto-'+sha256(identity.encode()).hexdigest()[:24]
        if not any(c.candidate_id==cid for c in analysis.candidates):
            analysis.candidates.append(RuleCandidate(candidate_id=cid,scope=scope,value=value,
                origin='EXPLICIT_PROSE',evidence_ids=[source.source_id],
                note='Parsed automatically from this instruction. This is not a learned confidence estimate.'))
        ids.append(cid)
    if parsed.chapters:
        pid='auto-chapters-'+sha256(source.source_id.encode()).hexdigest()[:16]
        if not any(p.profile_id==pid for p in analysis.profiles):
            analysis.profiles.append(ProfileCandidate(profile_id=pid,label='report',chapters=[
                ChapterCandidate(title=t,evidence_ids=[source.source_id]) for t in parsed.chapters]))
    previous=next((d for d in analysis.requirement_ledger if d.evidence_id==source.source_id),None)
    if previous:
        previous.candidate_ids=list(dict.fromkeys(previous.candidate_ids+ids))
    else:
        analysis.requirement_ledger.append(RequirementDisposition(evidence_id=source.source_id,
            status='CANDIDATES_NEED_REVIEW' if ids else 'UNCLASSIFIED',candidate_ids=ids))
    if len(analysis.candidates)>500:
        raise ReviewError('TOO_MANY_RULES','Split this format into smaller profiles; more than 500 rule proposals were found.')


def enrich(analysis,sources):
    result=analysis.model_copy(deep=True)
    if MARKER not in result.notices: result.notices.append(MARKER)
    existing={d.evidence_id for d in result.requirement_ledger}
    for source in sources:
        if not DIRECTIVE.search(source.excerpt): continue
        parsed=interpret(source.excerpt)
        if not (parsed.values or parsed.chapters or source.source_id in existing or re.search(r'\b(?:must|shall|should|required)\b|^(?:use|set|do not)\b',source.excerpt,re.I)):
            continue  # A table header such as "Font" is not itself an instruction.
        add_interpretation(result,source,parsed)
    # Suggested chapter tables must not silently become compulsory chapters.
    if result.profiles and not any(p.profile_id.startswith('auto-chapters-') for p in result.profiles):
        sid='automatic-chapter-question'
        if not any(s.source_id==sid for s in result.evidence):
            text='The format contains chapter/topic tables. Which chapters are compulsory? Explain with: Required chapters: Introduction, Methods, Results, Conclusion. Suggested topics are not automatically mandatory.'
            result.evidence.append(SourceEvidence(source_id=sid,path='chapter-profiles',excerpt=text))
            result.requirement_ledger.append(RequirementDisposition(evidence_id=sid,status='UNCLASSIFIED'))
    return TemplateAnalysis.model_validate(result.model_dump())


def prepare_draft(revision, expected_version):
    guard_edit(revision,expected_version)
    evidence={s.source_id:s for s in revision.analysis.evidence}
    instruction_ids={d.evidence_id for d in revision.analysis.requirement_ledger} | {sid for c in revision.analysis.candidates if c.origin=='EXPLICIT_PROSE' for sid in c.evidence_ids}
    sources={sid:interpret(s.excerpt) for sid,s in evidence.items() if sid in instruction_ids and s.part!='word/styles.xml' and not sid.startswith('automatic-')}
    groups=defaultdict(list)
    for c in revision.analysis.candidates:
        if c.origin=='EXPLICIT_PROSE' and c.condition=='ALWAYS' and not any(sources.get(sid) and sources[sid].ambiguity for sid in c.evidence_ids):
            groups[property_key(c)].append(c)
    explicit_keys={property_key(c) for c in revision.analysis.candidates if c.origin=='EXPLICIT_PROSE'}
    from app.analysis.template_baseline import BASELINE
    ambiguous_source=any(p.ambiguity for p in sources.values())
    baselines={c.candidate_id for c in revision.analysis.candidates if not ambiguous_source and c.note.startswith(BASELINE) and property_key(c) not in explicit_keys}
    for c in revision.analysis.candidates:
        if c.candidate_id in baselines:groups[property_key(c)].append(c)
    conflicting=set()
    for values in groups.values():
        if any(not same_value(values[0],v) for v in values[1:]):
            conflicting.update(v.candidate_id for v in values)
    decisions=[]
    for c in revision.analysis.candidates:
        explicit=c.origin=='EXPLICIT_PROSE' or c.candidate_id in baselines
        ambiguous=c.candidate_id in conflicting or c.condition!='ALWAYS' or any(sources.get(sid) and sources[sid].ambiguity for sid in c.evidence_ids)
        action='REJECT' if not explicit else 'DEFER' if ambiguous else 'APPROVE'
        reason=('Automatically applied a consistent named-role/section example baseline; explicit prose takes priority.' if c.candidate_id in baselines and action=='APPROVE' else
                'Automatically applied the explicit, unconflicted instruction; source evidence is retained.' if action=='APPROVE' else
                'Needs explanation: conflicting values, conditional applicability or ambiguous wording.' if action=='DEFER' else
                'Sample appearance is not treated as a written requirement; dominant caption/guidance formatting may be misleading.')
        decisions.append(CandidateDecision(candidate_id=c.candidate_id,action=action,reason=reason))
    approved={d.candidate_id for d in decisions if d.action=='APPROVE'}
    ledger=[]
    for entry in revision.analysis.requirement_ledger:
        parsed=sources.get(entry.evidence_id)
        represented=bool(entry.candidate_ids) and set(entry.candidate_ids)<=approved
        complete=parsed and parsed.complete and represented
        ledger.append(LedgerDecision(evidence_id=entry.evidence_id,action='COVERED' if complete else 'MANUAL',
            reason='This complete instruction is represented by executable rules.' if complete else
            'Supported clauses were applied where possible. Explain the remaining instruction; unsupported requirements are not counted as passes.'))
    profile=ProfileReview(profile_id=None,reason='No suggested chapter table was promoted to a mandatory profile automatically.')
    chapter_profiles=[p for p in revision.analysis.profiles if p.profile_id.startswith('auto-chapters-')]
    if len(chapter_profiles)==1:
        p=chapter_profiles[0]
        profile=ProfileReview(profile_id=p.profile_id,reason='The instruction explicitly identifies these chapters as required.',
            chapters=[ChapterReview(index=i,name=c.title,required=True) for i,c in enumerate(p.chapters)])
        for d in ledger:
            if d.evidence_id in p.chapters[0].evidence_ids: d.action='COVERED'
    result=apply_review(revision,ReviewPatch(expected_version=expected_version,candidates=decisions,ledger=ledger,profile=profile))
    if approved or profile.chapters: result=publish(result,result.version)
    return result


def automatic_change(revision, argument):
    version, analysis=argument
    guard_edit(revision,version)
    result=revision.model_copy(deep=True);result.analysis=analysis
    return prepare_draft(result,version)


def questions(revision):
    evidence={e.source_id:e for e in revision.analysis.evidence}
    deferred={d.candidate_id for d in revision.candidate_decisions if d.action=='DEFER'}
    unclear={sid for c in revision.analysis.candidates if c.candidate_id in deferred for sid in c.evidence_ids}
    automatic=MARKER in revision.analysis.notices
    return [{'evidence_id':d.evidence_id,'instruction':evidence[d.evidence_id].excerpt,
             'reason':d.reason,'kind':'CLARIFICATION' if d.evidence_id in unclear or d.evidence_id.startswith('automatic-') or automatic and interpret(evidence[d.evidence_id].excerpt).ambiguity else 'MANUAL'} for d in revision.ledger_decisions
            if d.action not in {'COVERED','OUT_OF_SCOPE'} and d.evidence_id in evidence]


def summary(revision, *, reused=False):
    rules=revision.publication.rules if revision.publication else []
    pending=questions(revision)
    return {'revision':revision,'reused':reused,'rule_count':len(rules),'questions':pending,
            'ready':revision.status=='PUBLISHED',
            'message':('Recognized this format and reused its published rules.' if reused and revision.status=='PUBLISHED' else
                       'Found your unfinished format. Its saved explanations and open questions are retained.' if reused else
                       'The supported rules are ready. You can check a report now; unclear instructions remain visible.' if rules else
                       'No reliable checking rules could be established yet. Explain a requirement below to start.')}


def recognized(repository,source_hash):
    # Built-ins and this private workspace only; no cross-user content lookup.
    from app.builtin_formats import BUILTINS,builtin
    for entry in repository.list_templates():
        if entry.get('builtin'):continue
        rid=entry.get('published_revision_id')
        if not rid:rid=repository.list_revisions(entry['id'])[0]['id']
        r=repository.get(entry['id'],rid)
        if r.analysis.source_sha256==source_hash and (r.status=='PUBLISHED' or MARKER in r.analysis.notices):return r
    for identifier in BUILTINS:
        r=builtin(identifier)
        if r.analysis.source_sha256==source_hash:return r
    return None


def clarify_draft(revision, argument):
    expected_version, source, parsed, target=argument
    guard_edit(revision,expected_version)
    result=revision.model_copy(deep=True)
    add_interpretation(result.analysis,source,parsed)
    decisions={d.candidate_id:d for d in result.candidate_decisions}
    new=[c for c in result.analysis.candidates if source.source_id in c.evidence_ids]
    for c in result.analysis.candidates:
        if c in new:
            decisions[c.candidate_id]=CandidateDecision(candidate_id=c.candidate_id,action='APPROVE',reason='Applied your plain-language clarification; its exact text is retained as the source.')
        elif (target and parsed.complete and target in c.evidence_ids) or any(property_key(c)==property_key(n) and not same_value(c,n) for n in new):
            decisions[c.candidate_id]=CandidateDecision(candidate_id=c.candidate_id,action='REJECT',reason='Superseded by your explicit clarification; other published revisions retain the earlier instruction.')
        elif decisions.get(c.candidate_id) and decisions[c.candidate_id].action=='DEFER' and c.origin=='EXPLICIT_PROSE' and c.condition=='ALWAYS' and any(property_key(c)==property_key(n) and same_value(c,n) for n in new):
            sources=[e for e in result.analysis.evidence if e.source_id in c.evidence_ids]
            if all(not interpret(e.excerpt).ambiguity for e in sources):
                decisions[c.candidate_id]=CandidateDecision(candidate_id=c.candidate_id,action='APPROVE',reason='Your clarification resolves the earlier conflict and corroborates this same explicit value.')
    ledger={d.evidence_id:d for d in result.ledger_decisions}
    if parsed.ignore_instruction:
        ledger[source.source_id]=LedgerDecision(evidence_id=source.source_id,action='OUT_OF_SCOPE',reason='You explicitly explained that this item is decorative or does not apply.')
        ledger[target]=LedgerDecision(evidence_id=target,action='OUT_OF_SCOPE',reason='Excluded by your explanation recorded in '+source.source_id+'.')
        for c in result.analysis.candidates:
            if target in c.evidence_ids:
                decisions[c.candidate_id]=CandidateDecision(candidate_id=c.candidate_id,action='REJECT',reason='You explicitly explained that this instruction does not apply.')
        updated=apply_review(result,ReviewPatch(expected_version=expected_version,candidates=list(decisions.values()),ledger=list(ledger.values()),profile=result.profile_review))
        return publish(updated,updated.version) if any(d.action=='APPROVE' for d in decisions.values()) or result.profile_review and result.profile_review.chapters else updated
    for c in result.analysis.candidates:
        if c not in new and c.candidate_id in decisions and decisions[c.candidate_id].action=='REJECT' and any(property_key(c)==property_key(n) and not same_value(c,n) for n in new):
            for sid in c.evidence_ids:
                if sid in ledger and ledger[sid].action=='COVERED' and sid!=target:
                    ledger[sid]=LedgerDecision(evidence_id=sid,action='OUT_OF_SCOPE',reason='The previous instruction was superseded by your newer explanation. Other approved clauses remain executable.')
    ledger[source.source_id]=LedgerDecision(evidence_id=source.source_id,action='COVERED' if parsed.complete else 'MANUAL',
        reason='Your explanation is represented by executable rules.' if parsed.complete else 'Some clauses were applied; explain the remaining unsupported wording.')
    if target and parsed.complete:
        ledger[target]=LedgerDecision(evidence_id=target,action='COVERED',reason='You replaced this instruction with the complete explanation recorded in '+source.source_id+'.')
    for d in ledger.values():
        if d.action!='MANUAL':continue
        original=next(e for e in result.analysis.evidence if e.source_id==d.evidence_id)
        candidates=[c for c in result.analysis.candidates if d.evidence_id in c.evidence_ids]
        if candidates and interpret(original.excerpt).complete and all(decisions.get(c.candidate_id) and decisions[c.candidate_id].action=='APPROVE' for c in candidates):
            d.action='COVERED';d.reason='Your clarification resolves the conflict; this instruction is now represented by executable rules.'
    profile=result.profile_review
    if parsed.chapters:
        p=next(p for p in result.analysis.profiles if p.profile_id=='auto-chapters-'+sha256(source.source_id.encode()).hexdigest()[:16])
        profile=ProfileReview(profile_id=p.profile_id,reason='Required chapters specified in your explanation.',chapters=[ChapterReview(index=i,name=c.title,required=True) for i,c in enumerate(p.chapters)])
    updated=apply_review(result,ReviewPatch(expected_version=expected_version,candidates=list(decisions.values()),ledger=list(ledger.values()),profile=profile))
    return publish(updated,updated.version)
