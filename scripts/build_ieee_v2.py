"""Curated second IEEE baseline, preserving the original revision for replay.

The supplied Word template controls layout/style. IEEE PVSC's explicit body-size
instruction supplies the missing size in the Word style chain; its venue-specific
author, abstract-length, page-limit and deadline rules are deliberately excluded.
"""
from pathlib import Path
from app.builtin_formats import DIRECTORY
from app.models.template_analysis import (RuleCandidate, SourceEvidence, SizeValue, SpacingValue,
    MarginValue, MarginRangeValue, PaperFormatValue)
from app.review.models import ReviewRevision, AuditEvent, CandidateDecision, ReviewPatch, LedgerDecision
from app.review.service import apply_review, publish, now, snapshot_hash

GUIDE = 'https://ieee-pvsc.org/PVSC47/downloads/2020_manuscript_template_PVSC.pdf'


def build():
    original = DIRECTORY/'ieee-conference-letter.v1.json'
    if not original.exists():
        original.write_bytes((DIRECTORY/'ieee-conference-letter.json').read_bytes())
    old = ReviewRevision.model_validate_json(original.read_bytes())
    assert old.revision_number == 1 and snapshot_hash(old) == old.snapshot_sha256
    analysis = old.analysis.model_copy(deep=True)
    additions = [
        ('body-size', 'body', SizeValue(expected_pt=10.0), 'external-guideline', GUIDE+'#page=3',
         'Reviewed body-size supplement: 10 pt Times New Roman. PVSC p.3 IV-A states this explicitly; the bundled Word BodyText style omits size. Other PVSC-specific rules are not adopted.'),
        ('body-spacing', 'body', SpacingValue(multiplier=.95), 'word/styles.xml', '//w:style[@w:styleId="BodyText"]/w:pPr/w:spacing',
         'Bundled BodyText style: w:line="228", w:lineRule="auto"; 228/240 = 0.95 lines.'),
        ('top-margin', 'document', MarginValue(side='top', expected_pt=54.0), 'word/document.xml', '//w:sectPr/w:pgMar/@w:top', 'The bundled Letter sections store a 54 pt top margin.'),
        ('bottom-margin', 'document', MarginValue(side='bottom', expected_pt=72.0), 'word/document.xml', '//w:sectPr/w:pgMar/@w:bottom', 'The bundled Letter sections store a 72 pt bottom margin.'),
        *[(side+'-margin', 'document', MarginRangeValue(side=side, minimum_pt=44.5, maximum_pt=45.5), 'word/document.xml', '//w:sectPr/w:pgMar/@w:'+side,
           'Reviewed source-compatible range 44.5–45.5 pt around 0.625 inch. The unchanged Word template stores 44.65 and 45.35 pt side-margin variants; both are accepted.') for side in ('left', 'right')],
        *[(kind, 'document', PaperFormatValue(kind=kind, expected_pt=pt), 'word/styles.xml', path, description) for kind, pt, path, description in [
            ('paper_abstract_size', 9.0, '//w:style[@w:styleId="Abstract"]', 'Abstract text uses 9 pt in the bundled style.'),
            ('paper_title_size', 24.0, '//w:style[@w:styleId="papertitle"]', 'Paper title style uses 24 pt. A cover heading is not silently guessed to be the paper title.'),
            ('paper_reference_size', 8.0, '//w:style[@w:styleId="references"]', 'Reference-entry style uses 8 pt. Only the contiguous native References block is checked.')]],
        ('main-heading-size', 'document', PaperFormatValue(kind='paper_heading_size', expected_pt=10.0), 'external-guideline', GUIDE+'#page=3',
         'Reviewed 10 pt main-heading supplement from IEEE PVSC IV-A. The bundled Heading1 style omits an explicit size; component heads are excluded.'),
        *[(kind, 'document', PaperFormatValue(kind=kind), 'word/document.xml', '//w:body', description) for kind, description in [
            ('paper_heading_numbering', 'Template main text heads use uppercase Roman numerals; component heads such as References remain unnumbered.'),
            ('paper_abstract_run_in', 'The template Abstract label and abstract prose share a paragraph, separated by a dash.'),
            ('paper_keywords', 'This reviewed baseline requires the nonempty Keywords line shown after the abstract; Index Terms is accepted as an equivalent label. No word-count limit is inferred.'),
            ('paper_no_page_numbers', 'The template instructions prohibit adding pagination anywhere in the paper. Active native PAGE fields provide positive evidence of a violation; absence is not a rendered-page verdict.'),
            ('paper_body_alignment', 'The template BodyText style inherits justified paragraph alignment.'),
            ('paper_caption_numbering', 'The template uses consecutive Fig. 1. captions and Roman TABLE I labels, rather than chapter-decimal numbering.')]],
    ]
    decisions = list(old.candidate_decisions)
    for name, scope, value, part, path, excerpt in additions:
        identifier = 'ieee-v2-'+name
        analysis.evidence.append(SourceEvidence(source_id=identifier, part=part, path=path, excerpt=excerpt))
        analysis.candidates.append(RuleCandidate(candidate_id=identifier, scope=scope, value=value,
            origin='EXPLICIT_PROSE' if part == 'external-guideline' or name == 'paper_no_page_numbers' else 'OBSERVED_APPEARANCE',
            evidence_ids=[identifier], note='Curated source-specific baseline. Unresolved applicability remains visible; not IEEE certification.'))
        decisions.append(CandidateDecision(candidate_id=identifier, action='APPROVE', reason=excerpt))
    analysis.notices.append('Revision 2 adds separately sourced typography, margins and paper structure. Body size uses the documented IEEE PVSC supplement; no venue page limit or abstract word cap is inferred. Side margin range is an explicit review policy.')
    revision = ReviewRevision(template_id=old.template_id, revision_id=old.template_id+'-v2', revision_number=2,
        name=old.name, analysis=analysis, audit=[AuditEvent(version=0, timestamp=now(), action='CREATE')])
    ledger = [LedgerDecision(evidence_id=d.evidence_id, action=d.action,
        reason='Review remaining clauses in this passage manually. Executable paper rules are listed separately; their presence does not establish full coverage of language, author layout, scientific meaning, figure images or rendered geometry.') for d in old.ledger_decisions]
    revision = apply_review(revision, ReviewPatch(expected_version=0, candidates=decisions, ledger=ledger))
    revision = publish(revision, revision.version)
    current_path = DIRECTORY/'ieee-conference-letter.json'
    current = ReviewRevision.model_validate_json(current_path.read_bytes())
    if current.revision_number == 2:
        if current.model_dump(exclude={'audit', 'snapshot_sha256'}) != revision.model_dump(exclude={'audit', 'snapshot_sha256'}):
            raise RuntimeError('Revision 2 already exists with different content. Publish a new revision; do not overwrite history.')
        print('Revision 2 already matches; preserved its original snapshot and audit timestamps.')
        return current
    current_path.write_text(revision.model_dump_json(indent=2), encoding='utf8')
    print(f'Published revision 2 with {len(revision.publication.rules)} rules; revision 1 preserved.')
    return revision


if __name__ == '__main__':
    build()
