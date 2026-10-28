"""Infer consistent named-role and stored-section baselines, never dominant text."""
from hashlib import sha256
from app.models.template_analysis import (RuleCandidate, SourceEvidence, FontValue, SizeValue,
    SpacingValue, PageValue, MarginValue, BodyColumnsValue)
from app.checking.roles import inventory, scalar_run, paragraph_spacing
from app.checking.word_structure import text_runs, section_map
from app.checking.columns import body_samples, column_count
from app.checking.service import integer_attribute
from app.ooxml.constants import NS, qn

BASELINE = 'CONSISTENT_TEMPLATE_BASELINE: '


def add_baselines(analysis, package):
    paragraphs,registry,uncertain=inventory(package)
    if uncertain:return analysis
    def add(scope,value,part,path,description):
        identifier='baseline-'+sha256((scope+value.model_dump_json()).encode()).hexdigest()[:20]
        if any(c.candidate_id==identifier for c in analysis.candidates):return
        analysis.evidence.append(SourceEvidence(source_id=identifier,part=part,path=path,excerpt=description))
        analysis.candidates.append(RuleCandidate(candidate_id=identifier,scope=scope,value=value,
            origin='OBSERVED_APPEARANCE',evidence_ids=[identifier],note=BASELINE+description))
    body=[p for p in paragraphs if p.role=='BODY' and not p.scope_uncertain and p.reviewable]
    for kind,cls in [('font_family',FontValue),('font_size',SizeValue)]:
        values=[scalar_run(package,registry,p,r,kind) for p in body for r in text_runs(p)]
        distinct=set(values)
        if values and None not in distinct and len(distinct)==1:
            value=cls(font=values[0]) if kind=='font_family' else cls(expected_pt=values[0])
            add('body',value,'word/styles.xml','named-body-role',
                'Named Body Text paragraphs consistently resolve to '+str(values[0])+'. This is an observed example baseline, subordinate to explicit instructions.')
    spacing=[paragraph_spacing(package,p) for p in body]
    multiples=[v['multiplier'] if v and v['rule']=='auto' else None for v in spacing]
    if multiples and None not in multiples and len(set(multiples))==1:
        add('body',SpacingValue(multiplier=multiples[0]),'word/styles.xml','named-body-role/spacing',
            'Named Body Text paragraphs consistently use '+str(multiples[0])+' line spacing; explicit prose takes priority.')
    root=package.document_tree.getroot()
    sections=root.xpath('w:body/w:p/w:pPr/w:sectPr | w:body/w:sectPr',namespaces=NS)
    if len(sections)!=len(root.xpath('.//w:sectPr',namespaces=NS)) or root.xpath('.//w:sectPrChange',namespaces=NS):return analysis
    sizes=[(integer_attribute(s.find(qn('w:pgSz')),'w:w',positive=True),integer_attribute(s.find(qn('w:pgSz')),'w:h',positive=True)) for s in sections]
    if sizes and len(set(sizes))==1 and None not in sizes[0]:
        add('document',PageValue(width_pt=sizes[0][0],height_pt=sizes[0][1]),'word/document.xml','//w:sectPr/w:pgSz',
            'Every source section has the same stored page dimensions. This observed baseline does not override written paper instructions.')
    settings=package.settings_tree
    mirrored=settings is not None and bool(settings.xpath('//w:mirrorMargins | //w:bookFoldPrinting | //w:gutterAtTop',namespaces=NS))
    if not mirrored:
        for side in ('top','bottom','left','right'):
            margins=[s.find(qn('w:pgMar')) for s in sections]
            values=[integer_attribute(m,'w:'+side) for m in margins]
            if values and None not in values and len(set(values))==1 and all(integer_attribute(m,'w:gutter') in (None,0) for m in margins):
                add('document',MarginValue(side=side,expected_pt=values[0]),'word/document.xml','//w:sectPr/w:pgMar',
                    'Every source section has the same stored '+side+' margin. Written instructions take priority over this example setting.')
    _,groups=section_map(package,paragraphs)
    counts=[column_count(section)[0] for section,group in zip(sections,groups) if body_samples(group)[0]]
    if counts and None not in counts and len(set(counts))==1 and counts[0]<=6:
        add('body',BodyColumnsValue(count=counts[0]),'word/document.xml','//w:sectPr/w:cols',
            'All substantive body-text sections share this column count. Title/author blocks and sparse sections are excluded.')
    return analysis
