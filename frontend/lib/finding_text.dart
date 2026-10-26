import 'api.dart';

String findingStatus(Json item) =>
    switch ('${item['status'] ?? item['severity'] ?? ''}'.toUpperCase()) {
      'ERROR' => 'FAIL',
      final value => value,
    };

String readableNumber(dynamic value) {
  if (value is! num) return 'Not confirmed';
  return value.toStringAsFixed(3).replaceFirst(RegExp(r'\.?0+$'), '');
}

String pointsToMm(dynamic value) => value is num
    ? '${(value * 25.4 / 72).toStringAsFixed(1)} mm'
    : 'Not confirmed';

String alignmentName(dynamic value) => switch (value) {
  'center' => 'Centered',
  'right' => 'Right-aligned',
  'left' => 'Left-aligned',
  'both' => 'Justified',
  _ => 'Not confirmed',
};

String numeralName(dynamic value) => switch (value) {
  'decimal' => '1, 2, 3… (Arabic numbers)',
  'lowerRoman' => 'i, ii, iii… (lowercase Roman)',
  'upperRoman' => 'I, II, III… (uppercase Roman)',
  _ => 'Not confirmed',
};

class FindingText {
  final String title, requiredValue, foundValue, action;
  const FindingText(
    this.title,
    this.requiredValue,
    this.foundValue,
    this.action,
  );
}

FindingText explainFinding(Json item) {
  final expected = item['expected'] is Map
      ? <String, dynamic>{...object(item['expected'])}
      : <String, dynamic>{};
  final actual = item['actual'] is Map
      ? <String, dynamic>{...object(item['actual'])}
      : <String, dynamic>{};
  if (item['category'] != null && expected['kind'] == null) {
    if (expected.containsKey('font')) {
      expected['kind'] = 'font_family';
      actual['value'] = actual['font'];
    } else if (expected.containsKey('size_pt')) {
      expected['kind'] = 'font_size';
      expected['expected_pt'] = expected['size_pt'];
      actual['value'] = actual['size_pt'];
    } else if (expected.containsKey('multiplier')) {
      expected['kind'] = 'line_spacing_multiple';
      actual['rule'] = actual['mode'] ?? 'auto';
      actual['points'] = actual['pt'];
    } else if (expected.containsKey('width_pt') &&
        expected.containsKey('height_pt')) {
      expected['kind'] = 'page_size';
    } else if (expected.keys.any(
      (k) => ['top', 'bottom', 'left', 'right'].contains(k),
    )) {
      final side = expected.keys.firstWhere(
        (k) => ['top', 'bottom', 'left', 'right'].contains(k),
      );
      expected['kind'] = 'margin';
      expected['side'] = side;
      expected['expected_pt'] = expected[side];
      actual['margin_pt'] = actual[side];
    }
  }
  final kind = expected['kind'];
  final code = '${item['code'] ?? ''}';
  final status = findingStatus(item);
  final needsReview = status == 'NOT_CHECKED';
  String title = 'Formatting requirement';
  String required = 'Follow the reviewed format';
  String found = 'Not confirmed automatically';
  String action = 'Compare this part of the report with the format document.';
  if (item['category'] != null && kind == null) {
    // Older basic checks use short, human-written messages instead of typed
    // rule values. Preserve that explanation, without dumping key/value data.
    title = 'Basic formatting requirement';
    if (expected['alignment'] != null) {
      title = 'Paragraph alignment';
      required = alignmentName(expected['alignment']);
      found = alignmentName(actual['alignment']);
    } else if (expected['section'] != null) {
      title = 'Required section';
      required = '${expected['section']}';
      found = actual['matched_heading'] == null
          ? 'No matching heading confirmed'
          : '${actual['matched_heading']}';
    } else if (expected['bold'] != null) {
      title = 'Bold text';
      required = expected['bold'] == true ? 'Bold' : 'Regular weight';
      found = actual['bold'] == null
          ? 'Not confirmed'
          : actual['bold'] == true
          ? 'Bold'
          : 'Regular weight';
    } else if (expected['italic'] != null) {
      title = 'Italic text';
      required = expected['italic'] == true ? 'Italic' : 'Not italic';
      found = actual['italic'] == null
          ? 'Not confirmed'
          : actual['italic'] == true
          ? 'Italic'
          : 'Not italic';
    } else if (expected['order'] is List) {
      title = 'Section order';
      required = (expected['order'] as List).join(' → ');
    } else {
      for (final key in ['before_pt', 'after_pt', 'first_line_pt', 'pt']) {
        if (expected[key] != null) {
          title = {
            'before_pt': 'Space before paragraphs',
            'after_pt': 'Space after paragraphs',
            'first_line_pt': 'First-line indent',
            'pt': 'Fixed line spacing',
          }[key]!;
          required = '${readableNumber(expected[key])} pt';
          found = '${readableNumber(actual[key])} pt';
          break;
        }
      }
    }
  }
  switch (kind) {
    case 'page_size':
      title = 'Paper size';
      required =
          '${pointsToMm(expected['width_pt'])} × ${pointsToMm(expected['height_pt'])}';
      found =
          '${pointsToMm(actual['width_pt'])} × ${pointsToMm(actual['height_pt'])}';
      action = 'In Word, use Layout → Size and choose the required paper size for the affected sections.';
    case 'margin':
      final side = '${expected['side'] ?? ''}';
      title =
          '${side.isEmpty ? 'Page' : side[0].toUpperCase() + side.substring(1)} margin';
      required = pointsToMm(expected['expected_pt']);
      found = pointsToMm(actual['margin_pt']);
      action =
          'In Word, open Layout → Margins → Custom Margins. Set the $side margin in each affected section.';
    case 'body_columns':
      title = 'Body column layout';
      required = '${expected['count']} columns';
      found = actual['observed_columns'] == null
          ? 'Column layout needs review'
          : '${actual['observed_columns']} columns in the measured prose';
      action = 'Compare the main text columns with the template. Full-width figures and tables may be allowed.';
    case 'font_family':
      title = 'Body text font';
      required = '${expected['font']}';
      found = actual['value'] is String
          ? actual['value']
          : 'Font could not be confirmed';
      action = 'Select the affected body text and choose the required font on Word’s Home tab.';
    case 'font_size':
    case 'chapter_font_size':
    case 'section_font_size':
      title = kind == 'chapter_font_size'
          ? 'Chapter title size'
          : kind == 'section_font_size'
          ? '${expected['depth'] == 3 ? 'Subsection' : 'Section'} heading size'
          : 'Body text size';
      required = '${readableNumber(expected['expected_pt'])} pt';
      final sizes =
          (actual['sizes_pt'] as List?) ??
          [if (actual['value'] != null) actual['value']];
      found = sizes.isEmpty
          ? 'Text size could not be confirmed'
          : sizes.map((s) => '${readableNumber(s)} pt').join(', ');
      action =
          'Select the affected ${kind == 'font_size' ? 'text' : 'headings'} and set the font size to $required on Word’s Home tab.';
    case 'line_spacing_multiple':
      title = 'Line spacing';
      required = '${readableNumber(expected['multiplier'])} line spacing';
      found = actual['rule'] == 'auto' && actual['multiplier'] is num
          ? '${readableNumber(actual['multiplier'])} line spacing'
          : actual['points'] is num
          ? '${readableNumber(actual['points'])} pt fixed spacing'
          : 'Spacing could not be confirmed';
      action = 'Select the affected paragraphs. Open Paragraph → Line spacing and apply the required spacing.';
      if (code == 'BODY_SPACING_TOLERANCE_REVIEW') {
        action = 'This is a small difference. Ask the reviewer which rounding tolerance is acceptable before changing it.';
      }
    case 'page_number_alignment':
    case 'contents_page_alignment':
      title = kind == 'page_number_alignment'
          ? 'Page number alignment'
          : 'Contents page-number alignment';
      required = alignmentName(expected['alignment']);
      found = alignmentName(
        actual[kind == 'page_number_alignment' ? 'value' : 'alignment'],
      );
      action = kind == 'page_number_alignment'
          ? 'Open the footer in Word, select the page number, and center its paragraph. Check linked and separate section footers.'
          : 'Select the page-number entries in the contents and right-align their paragraphs.';
    case 'body_page_number_format':
    case 'front_page_number_format':
      title = kind == 'front_page_number_format'
          ? 'Front-matter page numbers'
          : 'Main report page numbers';
      required = numeralName(expected['format']);
      found = numeralName(actual['value']);
      action = 'Open Page Number → Format Page Numbers in Word. Choose the required number style for this part of the report.';
    case 'introduction_numbering':
      title = 'Introduction page numbering';
      required = 'Start at 1; hide the number on the first page';
      found = actual.isEmpty
          ? 'Section settings could not be confirmed'
          : '${actual['start'] == '1' || actual['start'] == 1 ? 'Starts at 1' : 'Restart at 1 not set'}; ${actual['different_first_page'] == true && actual['first_page_fields'] == 0 ? 'first number hidden' : 'first-number suppression not confirmed'}';
      action = 'Use a separate Introduction section. Set page numbering to start at 1, enable Different First Page, and leave its first-page footer number blank.';
    case 'chapter_bold':
      title = 'Chapter titles in bold';
      required = 'Bold chapter number and title';
      final values = actual['bold_runs'] as List?;
      found = values == null || values.isEmpty
          ? 'Bold formatting could not be confirmed'
          : values.every((v) => v == true)
          ? 'Bold'
          : 'Some title text is not confirmed as bold';
      action = 'Select the chapter number and title and apply Bold in Word.';
    case 'chapter_case':
      title = 'Chapter title capitalization';
      required = 'Uppercase and lowercase letters';
      found = actual['caps_or_small_caps'] == true
          ? 'All-caps or small-caps formatting'
          : actual['title'] is String
          ? '“${actual['title']}”'
          : 'Title capitalization could not be confirmed';
      action = 'Use mixed case, such as “Introduction”, and turn off All caps and Small caps in Word’s Font settings.';
    case 'abstract_word_count':
      title = 'Abstract length';
      required = '${expected['expected_words']} words';
      found = actual['word_count'] == null
          ? 'Word count could not be confirmed'
          : '${actual['word_count']} words';
      action = 'Revise the abstract to meet the reviewed word-count requirement. The heading and labeled keywords are counted separately.';
    case 'abstract_keywords':
      title = 'Abstract keywords';
      required = 'A Keywords: line with keywords';
      found = actual['keyword_label_found'] == true
          ? 'Keywords line found'
          : actual['keyword_label_found'] == false
          ? 'No nonempty Keywords: line found'
          : 'Keywords could not be confirmed';
      action = 'Add a “Keywords:” line with the relevant terms inside the abstract section.';
    case 'contents_structure':
      title = actual['numbering_format'] == 'bullet'
          ? 'Contents section numbering'
          : 'Contents page references';
      required = actual.containsKey('entry')
          ? 'Decimal section numbers, such as 1.1 and 1.1.1'
          : 'One page reference for each contents entry';
      found = actual['numbering_format'] == 'bullet'
          ? 'Bullet points instead of decimal section numbers'
          : actual['entry'] is String
          ? '“${actual['entry']}”'
          : actual['page_reference'] is String
          ? 'Page reference: ${actual['page_reference']}'
          : 'Not confirmed automatically';
      action = 'Use decimal numbering for sections and subsections, and give each contents entry its own page reference. Check that all headings and page references are correct.';
    case 'illustration_lists':
      final tables = actual['list'] == 'list of tables';
      title = tables
          ? 'List of Tables'
          : actual['list'] == 'list of figures'
          ? 'List of Figures'
          : 'Lists of figures and tables';
      required = 'A separate list after the contents';
      found = actual['front_headings'] == 0
          ? 'No list heading found before the main report'
          : actual['front_headings'] is num
          ? '${actual['front_headings']} list heading(s) found; position was also checked'
          : 'List position could not be confirmed';
      action =
          'Place a separate $title after the contents and before the main chapters. Include each object’s number, title and page.';
    case 'figure_captions':
    case 'table_titles':
      final figure = kind == 'figure_captions';
      title = figure ? 'Figure captions' : 'Table titles';
      required = figure
          ? 'A numbered caption below each figure'
          : 'A numbered title above each table';
      found = actual['native_caption_found'] == false
          ? 'No matching numbered ${figure ? 'caption below the figure' : 'title above the table'} was confirmed in editable text'
          : actual['native_caption_found'] == true
          ? 'Numbered text found; chapter number and duplicates were also checked'
          : 'Caption numbering could not be confirmed';
      action = figure && needsReview
          ? 'Inspect the image: its caption might be embedded in the picture. Confirm it before adding another caption.'
          : 'Check the ${figure ? 'caption below the figure' : 'title above the table'}. Use the chapter number, such as “${figure ? 'Fig' : 'Table'} 3.1”, and avoid duplicate numbers.';
  }
  if (code == 'INCOMPLETE_BODY_SCOPE' || code == 'BODY_SCOPE_REVIEW') {
    title = 'Confirm which text this rule applies to';
    found = code == 'INCOMPLETE_BODY_SCOPE'
        ? 'Some paragraphs could not be safely identified as body text'
        : 'This text may belong to front matter, an appendix, or a sign-off';
    action = 'Use “Review paragraph roles” before checking again, or ask the reviewer whether this text should follow the body-text rules.';
  } else if (code == 'NUMBERED_BODY_UNSUPPORTED') {
    found = 'The numbered paragraph’s full formatting could not be resolved';
    action = 'Check this numbered paragraph manually against the required formatting.';
  } else if (code.startsWith('CHAPTER_ORDER_')) {
    title = 'Chapter order';
    required = 'The order in the reviewed chapter list';
    found = status == 'PASS'
        ? 'Matched chapters are in the required order'
        : 'The full chapter order could not be confirmed';
    action = 'Compare your chapter order with the reviewed format.';
  } else if (code.startsWith('CHAPTER_') ||
      code == 'MISSING_CHAPTER' ||
      code == 'AMBIGUOUS_CHAPTER' ||
      code == 'DUPLICATE_CHAPTER') {
    if (expected['kind'] == null) {
      title = code == 'CHAPTER_TITLE_VARIANT_REVIEW'
          ? 'Check a chapter title’s spelling'
          : 'Required chapter';
      required = expected['name'] is String
          ? '${expected['name']}'
          : 'The reviewed chapter title';
      found = code == 'CHAPTER_PRESENT'
          ? 'Chapter found'
          : code == 'MISSING_CHAPTER'
          ? 'No matching chapter found'
          : code == 'DUPLICATE_CHAPTER'
          ? 'More than one matching chapter found'
          : 'Chapter identity or title needs confirmation';
      action = 'Compare the chapter title and spelling with the required name. Use paragraph-role review if the chapter was identified incorrectly.';
    }
  } else if (code.startsWith('REQUIREMENT_')) {
    title = 'Instruction to check manually';
    required = 'Review the original instruction below';
    action = 'Read “What the format says” and check this instruction in the report. The automatic check has not established whether it is followed.';
  }
  if (status == 'PASS') action = 'This supported check matched the reviewed requirement. No change is suggested here.';
  if (status == 'OUT_OF_SCOPE') {
    found = 'This rule does not apply in this location';
    action = 'No change is suggested for this item. A different conditional rule may apply.';
  } else if (needsReview &&
      kind != null &&
      !code.contains('SCOPE') &&
      !code.contains('TOLERANCE') &&
      kind != 'figure_captions' &&
      kind != 'contents_structure') {
    action = 'The app could not confirm this requirement. Check this part manually before deciding whether to change it.';
  }
  if (code.startsWith('PDF_')) {
    if (code == 'PDF_SOURCE_PROPERTY_REVIEW') {
      found = actual['prose_sample_sizes_pt'] is Map && kind == 'font_size'
          ? 'Prose samples: ${object(actual['prose_sample_sizes_pt']).keys.join(', ')} pt; body roles need review'
          : actual['prose_sample_fonts'] is Map && kind == 'font_family'
          ? 'Prose samples: ${object(actual['prose_sample_fonts']).keys.join(', ')}; font identity needs review'
          : 'Not established from the PDF';
    }
    action = status == 'FAIL'
        ? 'Correct the page size or main text layout in the source document, then export a new PDF.'
        : status == 'PASS'
        ? 'This PDF measurement matched. Other formatting requirements may still need review.'
        : 'Review this requirement in the PDF and its source document. No automatic violation has been established.';
  }
  return FindingText(title, required, found, action);
}

String locationSummary(List<Json> members) {
  String ranges(String key, String label) {
    final indices = <int>{};
    for (final member in members) {
      final location = member['location'] is Map
          ? object(member['location'])
          : <String, dynamic>{};
      final index = member[key] ?? location[key];
      if (index is int) indices.add(index + (key == 'page_number' ? 0 : 1));
      if (key == 'paragraph_index') {
        for (final i in (member['affected_paragraph_indices'] as List?) ?? []) {
          if (i is int) indices.add(i + 1);
        }
      }
    }
    final values = indices.toList()..sort();
    if (values.isEmpty) return '';
    final parts = <String>[];
    for (var i = 0; i < values.length; i++) {
      final start = values[i];
      var end = start;
      while (i + 1 < values.length && values[i + 1] == end + 1) {
        end = values[++i];
      }
      parts.add(start == end ? '$start' : '$start–$end');
    }
    return '$label ${parts.take(6).join(', ')}${parts.length > 6 ? ', …' : ''}';
  }

  final sections = ranges('section_index', 'Word sections');
  final paragraphs = ranges('paragraph_index', 'Paragraphs');
  final pages = ranges('page_number', 'PDF pages');
  return [
        pages,
        sections,
        paragraphs,
      ].where((s) => s.isNotEmpty).join(' · ').isEmpty
      ? 'Whole document'
      : [pages, sections, paragraphs].where((s) => s.isNotEmpty).join(' · ');
}
