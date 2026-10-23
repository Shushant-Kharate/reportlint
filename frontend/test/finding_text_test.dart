import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:reportlint_flutter/api.dart';
import 'package:reportlint_flutter/checking.dart';
import 'package:reportlint_flutter/finding_text.dart';

Json footer(int section) => {
  'item_id': 'footer-$section',
  'rule_id': 'align',
  'status': 'FAIL',
  'code': 'PAGE_NUMBER_ALIGNMENT_FAIL',
  'section_index': section,
  'message': 'Compared active inherited footer PAGE-field settings.',
  'expected': {'kind': 'page_number_alignment', 'alignment': 'center'},
  'actual': {
    'value': 'right',
    'footer_variant': 'default',
    'field_instruction': r'PAGE \* MERGEFORMAT',
  },
  'source_path': '/w:ftr/w:sdt/w:sdtContent/w:p',
};

void main() {
  test('Word footer internals become an actionable alignment explanation without changing evidence', () {
    final item = footer(10), original = jsonEncode(footer(10));
    final copy = explainFinding(item);
    expect(copy.title, 'Page number alignment');
    expect(copy.requiredValue, 'Centered');
    expect(copy.foundValue, 'Right-aligned');
    expect(copy.action, contains('footer'));
    expect(
      '${copy.title} ${copy.requiredValue} ${copy.foundValue} ${copy.action}',
      isNot(contains('MERGEFORMAT')),
    );
    expect(jsonEncode(item), original);
    expect(locationSummary(List.generate(37, footer)), 'Word sections 1–37');
  });

  test('Ambiguous image captions and unresolved values never become confirmed missing-caption errors', () {
    final copy = explainFinding({
      'status': 'NOT_CHECKED',
      'code': 'FIGURE_CAPTIONS_NOT_CHECKED',
      'expected': {'kind': 'figure_captions'},
      'actual': {'native_caption_found': false},
    });
    expect(copy.foundValue, contains('confirmed in editable text'));
    expect(copy.action, contains('embedded'));
    final unknown = explainFinding({
      'status': 'NOT_CHECKED',
      'expected': {'kind': 'font_size', 'expected_pt': 12},
      'actual': {'value': null},
    });
    expect(unknown.foundValue, contains('could not be confirmed'));
    expect(unknown.action, contains('manually'));
  });

  test(
    'Basic-check values remain readable and exact in the exported source',
    () {
      final basic = <String, dynamic>{
        'category': 'TYPOGRAPHY',
        'severity': 'ERROR',
        'expected': {'size_pt': 12},
        'actual': {'size_pt': 14},
      };
      final saved = jsonEncode(basic), copy = explainFinding(basic);
      expect(copy.requiredValue, '12 pt');
      expect(copy.foundValue, '14 pt');
      expect(jsonEncode(basic), saved);
      expect(pointsToMm(72), '25.4 mm');
    },
  );

  testWidgets(
    'Expanded locations stay readable while raw Word data is opt-in',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: ReadableFindingCard(members: [footer(10), footer(11)]),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Centered'), findsOneWidget);
      expect(find.text('Right-aligned'), findsOneWidget);
      expect(find.textContaining('MERGEFORMAT'), findsNothing);
      await tester.ensureVisible(find.text('Show affected locations'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Show affected locations'));
      await tester.pumpAndSettle();
      expect(find.text('Section 11'), findsOneWidget);
      expect(find.text('Section 12'), findsOneWidget);
      expect(find.textContaining('/w:ftr'), findsNothing);
      await tester.ensureVisible(find.text('Technical details'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Technical details'));
      await tester.pumpAndSettle();
      expect(find.textContaining('MERGEFORMAT'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
