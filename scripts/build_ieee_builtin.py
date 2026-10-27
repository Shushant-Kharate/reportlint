"""Reproduce the explicitly reviewed IEEE Letter baseline from its source DOCX.

Run with: python -m scripts.build_ieee_builtin SOURCE.docx
This is a curated build utility, not automatic approval of arbitrary templates.
"""
import argparse
from pathlib import Path

from app.analysis.service import analyze_bytes
from app.analysis.template_source import paragraph_text
from app.builtin_formats import DIRECTORY
from app.models.template_analysis import SourceEvidence, RuleCandidate, BodyColumnsValue, TemplateAnalysis
from app.ooxml.constants import qn, NS
from app.ooxml.docx_loader import DocxPackage
from app.ooxml.style_resolver import EffectiveStyleResolver, StyleRegistry, get_doc_defaults
from app.review.models import ReviewRevision, ReviewPatch, CandidateDecision, LedgerDecision, AuditEvent
from app.review.service import apply_review, publish, now


def build(source):
    if (DIRECTORY/'ieee-conference-letter.v1.json').exists():
        raise RuntimeError('Revision 1 is archived. Use scripts.build_ieee_v2 for the current reviewed baseline; do not overwrite immutable history.')
    data = source.read_bytes()
    analysis = analyze_bytes(data)
    package = DocxPackage.load(str(source))
    body = next(p for p in package.document_tree.xpath('/w:document/w:body/w:p', namespaces=NS)
                if paragraph_text(p).startswith('This template, modified'))
    resolver = EffectiveStyleResolver(StyleRegistry(package.styles_tree), *get_doc_defaults(package.styles_tree))
    run = next(r for r in body.findall(qn('w:r')) if paragraph_text(r))
    resolved = resolver.resolve_run(run, 'BodyText')
    assert resolved.font_name == 'Times New Roman', 'Review the changed template body style before rebuilding'
    evidence = SourceEvidence(source_id='reviewed-ieee-body-style',path=package.document_tree.getpath(body),
        excerpt=paragraph_text(body))
    columns = next(c for c in package.document_tree.xpath('//w:sectPr/w:cols',namespaces=NS) if c.get(qn('w:num')) == '2')
    column_evidence = SourceEvidence(source_id='reviewed-ieee-body-columns',path=package.document_tree.getpath(columns),
        excerpt='The sampled main-text section stores w:cols w:num="2". Author blocks, full-width figures and tables are exceptions; this is a reviewed body-layout baseline.')
    analysis.evidence.extend([evidence,column_evidence])
    analysis.candidates.extend([
        RuleCandidate(candidate_id='reviewed-ieee-body-columns',scope='body',value=BodyColumnsValue(count=2),origin='OBSERVED_APPEARANCE',
            evidence_ids=[column_evidence.source_id],note='PDF checker measures sustained prose layout; this does not constrain author blocks or full-width figures.')])
    analysis.notices.append('Curated IEEE conference US Letter baseline. Not an IEEE-endorsed validator, venue-specific rulebook, or PDF eXpress certification. The source itself has section-specific margin variants; they remain manual.')
    analysis = TemplateAnalysis.model_validate(analysis.model_dump())
    decisions = []
    for candidate in analysis.candidates:
        approved = candidate.value.kind in {'page_size','font_family','body_columns'}
        reason = ('Reviewed against the IEEE Letter template and its main-text style; enforce only in the supported scope.' if approved else
                  'Do not promote the legacy 8 pt figure-label/spacing sample or section-specific margins to a global body requirement. Check source instructions manually.')
        decisions.append(CandidateDecision(candidate_id=candidate.candidate_id,action='APPROVE' if approved else 'REJECT',reason=reason))
    ledger = [LedgerDecision(evidence_id=e.evidence_id,action='MANUAL',
        reason='Review this IEEE instruction manually. Page size and the sampled body style/layout cover only part of the template; author layout, margins, captions, references and language instructions are not fully checked.') for e in analysis.requirement_ledger]
    revision = ReviewRevision(template_id='builtin-ieee-conference-letter',revision_id='builtin-ieee-conference-letter-v1',revision_number=1,
        name='IEEE Conference — US Letter (reviewed baseline)',analysis=analysis,audit=[AuditEvent(version=0,timestamp=now(),action='CREATE')])
    revision = apply_review(revision,ReviewPatch(expected_version=0,candidates=decisions,ledger=ledger))
    revision = publish(revision,revision.version)
    (DIRECTORY/'ieee-conference-letter.docx').write_bytes(data)
    (DIRECTORY/'ieee-conference-letter.json').write_text(revision.model_dump_json(indent=2),encoding='utf-8')
    return revision


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    revision = build(parser.parse_args().source)
    print(f'Published {len(revision.publication.rules)} reviewed rules; other requirements remain manual.')
