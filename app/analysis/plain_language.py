"""Bounded English requirement interpretation, with explicit residual coverage.

No learned confidence scores, network calls, or document instructions executed.
Unknown words/conditions remain visible instead of turning guesses into rules.
"""
from dataclasses import dataclass, field
import re
from app.analysis.template_requirements import points
from app.models.template_analysis import (FontValue, SizeValue, SpacingValue, PageValue,
    MarginValue, BodyColumnsValue, PaperFormatValue)

NUMBER = r'\d+(?:\.\d+)?'
UNIT = r'(?:mm|millimeters?|millimetres?|cm|centimeters?|centimetres?|inches|inch|in|pts?|points?)'
FONTS = r'Times New Roman|Courier New|Arial|Calibri|Cambria|Helvetica|Georgia|Verdana'
DIRECTIVE = re.compile(r'\b(?:must|shall|should|required|use|set|font|margin|spacing|columns?|size|do not|no page numbers)\b', re.I)
FILLER = set('the a an all of for in on and with is are be to at by as from use uses using set should shall must '
    'have has required requirement requirements please font fonts family size paper page body text main normal '
    'paragraph paragraphs standard report document format formatting margin margins top bottom left right '
    'line spacing multiple factor single double point points pt pts numbered numbering number numbers '
    'upper uppercase roman numerals heading headings title titles abstract references reference justified '
    'justify alignment align column columns layout portrait landscape orientation exactly width height'.split())


def role_name(text):
    roles=[name for name,pattern in [
        ('abstract',r'\babstract\b'),('reference',r'\breferences?\b'),('title',r'\bpaper title\b'),
        ('heading',r'\b(?:main|section) headings?\b'),
        ('body',r'\b(?:body(?: text| font| paragraphs?)?|main text|standard font|normal text)\b')]
        if re.search(pattern,text,re.I)]
    return roles[0] if len(roles)==1 else None


@dataclass
class Parsed:
    values: list = field(default_factory=list)  # (scope, typed value)
    chapters: list[str] = field(default_factory=list)
    complete: bool = False
    ambiguity: str | None = None
    remaining: str = ''
    ignore_instruction: bool = False
    point_sizes_not_fonts: set[float] = field(default_factory=set)


def interpret(text):
    text = re.sub(r'\s+', ' ', text).strip()
    result = Parsed()
    if not text or len(text) > 12000:
        result.ambiguity = 'Instruction is empty or too long; split it into shorter requirements.'
        return result
    if re.fullmatch(r'(?:this (?:instruction|requirement) (?:does not apply|is not required)(?: to this report)?|this (?:image|picture) is (?:only |just )?(?:decorative|a logo)|this is (?:only |just )?an example,? not a requirement)[.!]?',text,re.I):
        result.ignore_instruction=True;result.complete=True
        return result
    # Do not flatten alternatives, negation, ranges or conditional scope.
    if re.search(r'\b(?:either|unless|except|when|if|depending|between|approximately|about|at least|at most|maximum|minimum)\b|\bor\b', text, re.I):
        result.ambiguity = 'This instruction contains an alternative, condition, range or tolerance that needs clarification.'
        return result
    remaining = list(text)
    fixed_spacing=list(re.finditer(rf'\b(?:line spacing|paragraph spacing|space before(?: paragraphs)?|space after(?: paragraphs)?|indent(?:ation)?)\s*(?:(?:shall|must|should)\s+be|of|is|to|:)?\s*({NUMBER})\s*(?:pt|pts|points?)\b',text,re.I))
    result.point_sizes_not_fonts={float(m[1]) for m in fixed_spacing}
    def fixed_property(match):
        return any(match.start()<s.end() and match.end()>s.start() for s in fixed_spacing)
    def consume(match):
        for i in range(match.start(), match.end()): remaining[i] = ' '
    def add(scope, value, match):
        if not any(scope == s and value == v for s, v in result.values): result.values.append((scope, value))
        consume(match)

    chapters = re.fullmatch(r'(?:the\s+)?required chapters?\s*(?:are|:|must be)\s*(.+?)[.]?', text, re.I)
    if chapters:
        names = [n.strip(' .') for n in re.split(r'[,;]|\s+and\s+', chapters[1]) if n.strip(' .')]
        if 1 <= len(names) <= 40 and all(1 <= len(n) <= 120 and re.fullmatch(r'[\w /&()\-]+', n) for n in names):
            result.chapters = names; result.complete = True
            return result

    role = role_name(text)
    # Multiple font roles in one clause need separate explanations.
    roles = sum(bool(re.search(p, text, re.I)) for p in [r'\bbody\b|\bmain text\b|\bstandard font\b',r'\babstract\b',r'\breferences?\b',r'\bpaper title\b',r'\b(?:main|section) headings?\b'])
    if roles > 1:
        result.ambiguity = 'Explain body, title, abstract, heading and reference requirements separately.'
        return result
    if re.search(r'\b(?:first|last|odd|even)\s+pages?\b|\b(?:cover|appendix|front matter|footnotes?)\b',text,re.I) or role=='body' and re.search(r'\b(?:numbered paragraphs|bulleted|lists|chapter\s+(?:\d+|one|two|three))\b',text,re.I):
        result.ambiguity = 'This requirement applies to a specific document region that the automatic rule contract cannot safely represent. Explain its scope separately.'
        return result

    for m in re.finditer(r'\b(A4|(?:US\s+)?Letter)\b', text, re.I):
        if not re.search(r'\b(?:paper|page|size)\b', text, re.I): continue
        width, height = (210*72/25.4,297*72/25.4) if m[1].casefold() == 'a4' else (612.,792.)
        if 'landscape' in text.casefold(): width,height=height,width
        add('document', PageValue(width_pt=width,height_pt=height),m)
    dimensions={key:re.search(rf'\b{key}\s*[:=]?\s*({NUMBER})\s*({UNIT})\b',text,re.I) for key in ('width','height')}
    if all(dimensions.values()) and re.search(r'\b(?:paper|page)\b',text,re.I):
        width=points(dimensions['width'][1],dimensions['width'][2]);height=points(dimensions['height'][1],dimensions['height'][2])
        if 100 <= width <= 2000 and 100 <= height <= 2000:
            add('document',PageValue(width_pt=width,height_pt=height),dimensions['width']);consume(dimensions['height'])

    margin_spans=[]
    for m in re.finditer(rf'\b(top|bottom|left|right)\s+(?:margin\s*)?(?:(?:shall|must|should)\s+be\s*|is\s*|[:=]\s*)?({NUMBER})\s*({UNIT})\b', text, re.I):
        if 'margin' not in text.casefold(): continue
        amount=points(m[2],m[3])
        if 0 <= amount <= 300:
            add('document',MarginValue(side=m[1].lower(),expected_pt=amount),m);margin_spans.append((m.start(),m.end()))
    for m in re.finditer(rf'\ball margins?\s*(?:(?:shall|must|should)\s+be\s*|are\s*|is\s*|[:=]\s*)?({NUMBER})\s*({UNIT})\b',text,re.I):
        amount=points(m[1],m[2])
        if 0 <= amount <= 300:
            for side in ('top','bottom','left','right'):add('document',MarginValue(side=side,expected_pt=amount),m)
            margin_spans.append((m.start(),m.end()))

    if role == 'body':
        for m in re.finditer(r'\b('+FONTS+r')\b',text,re.I):
            canonical=next(n for n in FONTS.split('|') if n.casefold()==m[1].casefold())
            add('body',FontValue(font=canonical),m)
        for m in re.finditer(rf'\b({NUMBER})\s*[- ]?\s*(?:pt|pts|points?)\b',text,re.I):
            if fixed_property(m):continue
            if any(start <= m.start() < end for start,end in margin_spans):continue
            if 1 <= float(m[1]) <= 96:add('body',SizeValue(expected_pt=float(m[1])),m)
        for m in re.finditer(rf'\b(?:font\s*)?size\s*(?:(?:shall|must|should)\s+be|of|is|to|:)?\s*({NUMBER})\b',text,re.I):
            if 1 <= float(m[1]) <= 96:add('body',SizeValue(expected_pt=float(m[1])),m)
        for m in re.finditer(rf'\b({NUMBER})\s*(?:x\s*)?line spacing\b|\bline spacing\s*(?:(?:shall|must|should)\s+be|:|of|is|to)?\s*({NUMBER})\b|\b(single|double)[- ](?:spaced|spacing)\b',text,re.I):
            if fixed_property(m):continue
            multiplier=float(m[1] or m[2]) if m[1] or m[2] else 1. if m[3].lower()=='single' else 2.
            if .5 <= multiplier <= 4:add('body',SpacingValue(multiplier=multiplier),m)
        for m in re.finditer(r'\b(one|two|three|[123])[- ]columns?\b',text,re.I):
            count={'one':1,'two':2,'three':3}.get(m[1].lower()) or int(m[1])
            add('body',BodyColumnsValue(count=count),m)
        for m in re.finditer(r'\bjustified\b|\bjustify\b',text,re.I):add('document',PaperFormatValue(kind='paper_body_alignment'),m)
    elif role in {'abstract','reference','title','heading'}:
        for m in re.finditer(rf'\b({NUMBER})\s*[- ]?\s*(?:pt|pts|points?)\b',text,re.I):
            if fixed_property(m):continue
            if 1 <= float(m[1]) <= 96:
                kind={'abstract':'paper_abstract_size','reference':'paper_reference_size','title':'paper_title_size','heading':'paper_heading_size'}[role]
                add('document',PaperFormatValue(kind=kind,expected_pt=float(m[1])),m)
        if role=='heading':
            for m in re.finditer(r'\b(?:upper(?:case)?[- ]?Roman|Roman\s+(?:numerals|numbers)\s+in\s+upper\s*case)\b',text,re.I):
                add('document',PaperFormatValue(kind='paper_heading_numbering'),m)

    for m in re.finditer(r'\b(?:no (?:added )?(?:page numbers?|pagination)|do not (?:add|include|use) (?:any (?:kind of )?)?(?:page numbers?|pagination))\b',text,re.I):
        add('document',PaperFormatValue(kind='paper_no_page_numbers'),m)
    # Other negative instructions must not be interpreted as positive rules.
    residue=''.join(remaining)
    if re.search(r'\b(?:not|never|no)\b',residue,re.I):
        result.values=[];result.ambiguity='This negative instruction is not supported automatically; explain the intended requirement.'
        return result
    result.remaining=' '.join(w for w in re.findall(r'[\w]+',residue) if w.casefold() not in FILLER)
    result.complete=bool(result.values) and not result.remaining
    return result
