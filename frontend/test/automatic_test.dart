import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reportlint_flutter/api.dart';
import 'package:reportlint_flutter/automatic.dart';

Json prepared({bool ready = true, bool question = true}) => {
  'ready': ready,
  'reused': false,
  'rule_count': ready ? 1 : 0,
  'message': ready
      ? 'Supported rules are ready.'
      : 'Explain a requirement to start.',
  'questions': [
    if (question)
      {
        'evidence_id': 'e',
        'instruction': 'Body text must use Arial or Times New Roman.',
        'reason': 'Conflicting alternatives.',
      },
  ],
  'revision': {
    'template_id': 't',
    'revision_id': 'r',
    'name': 'Automatic test format',
    'version': 2,
    'status': ready ? 'PUBLISHED' : 'DRAFT',
    'revision_number': 1,
    'candidate_decisions': [],
    'ledger_decisions': [],
    'profile_review': null,
    'publication': ready
        ? {
            'rules': [
              {
                'value': {'kind': 'font_size', 'expected_pt': 12},
              },
            ],
          }
        : null,
    'analysis': {
      'candidates': [],
      'profiles': [],
      'evidence': [],
      'requirement_ledger': [],
      'notices': [],
    },
  },
};

Future<void> openQuestion(WidgetTester tester) async {
  final question = find
      .text('Body text must use Arial or Times New Roman.')
      .first;
  await tester.scrollUntilVisible(
    find.byKey(const ValueKey<String>('question-e')),
    200,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.tap(question);
  await tester.pumpAndSettle();
  await tester.scrollUntilVisible(
    find.byType(TextFormField).first,
    150,
    scrollable: find.byType(Scrollable).first,
  );
}

void main() {
  testWidgets(
    'Automatic setup exposes checking without mandatory decisions or reasons',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final api = ReportApi(
        'http://example.test',
        client: MockClient((r) async => http.Response('{}', 200)),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: AutomaticFormatScreen(api: api, preparation: prepared()),
        ),
      );
      expect(find.text('Your format is ready'), findsOneWidget);
      expect(find.text('Check a report'), findsOneWidget);
      expect(find.text('1 rule ready'), findsOneWidget);
      expect(find.text('Reason'), findsNothing);
      expect(find.text('Decision'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'One plain-language explanation sends the target and bound version',
    (tester) async {
      Json? sent;
      final api = ReportApi(
        'http://example.test',
        client: MockClient((r) async {
          sent = object(jsonDecode(r.body));
          expect(r.url.path.endsWith('/clarify'), isTrue);
          final next = prepared(question: false);
          object(next['revision'])['revision_id'] = 'r2';
          return http.Response(jsonEncode(next), 200);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: AutomaticFormatScreen(api: api, preparation: prepared()),
        ),
      );
      await openQuestion(tester);
      await tester.enterText(
        find.byType(TextFormField).first,
        'Body text must use Arial at 12 pt.',
      );
      await tester.ensureVisible(find.text('Apply explanation').first);
      await tester.tap(find.text('Apply explanation').first);
      await tester.pumpAndSettle();
      expect(sent?['evidence_id'], 'e');
      expect(sent?['expected_version'], 2);
      expect(sent?['explanation'], 'Body text must use Arial at 12 pt.');
      expect(sent?.containsKey('reason'), isFalse);
      expect(find.textContaining('Explanation saved.'), findsOneWidget);
      expect(
        find.text('Only unclear instructions need your input'),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Unsupported explanations retain the entered text and show the server explanation',
    (tester) async {
      final api = ReportApi(
        'http://example.test',
        client: MockClient(
          (r) async => http.Response(
            jsonEncode({
              'detail': {
                'code': 'CLARIFICATION_UNRESOLVED',
                'message':
                    'This instruction still needs a supported role and value.',
              },
            }),
            422,
          ),
        ),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: AutomaticFormatScreen(api: api, preparation: prepared()),
        ),
      );
      await openQuestion(tester);
      await tester.enterText(
        find.byType(TextFormField).first,
        'Use a beautiful font.',
      );
      await tester.ensureVisible(find.text('Apply explanation').first);
      await tester.tap(find.text('Apply explanation').first);
      await tester.pumpAndSettle();
      expect(
        find.text('This instruction still needs a supported role and value.'),
        findsWidgets,
      );
      await tester.scrollUntilVisible(
        find.byType(TextFormField).first,
        100,
        scrollable: find.byType(Scrollable).first,
      );
      expect(
        tester.widget<TextField>(find.byType(TextField).first).controller?.text,
        'Use a beautiful font.',
      );
    },
  );

  testWidgets('Zero executable rules does not enable report checking', (
    tester,
  ) async {
    final api = ReportApi(
      'http://example.test',
      client: MockClient((r) async => http.Response('{}', 200)),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: AutomaticFormatScreen(
          api: api,
          preparation: prepared(ready: false),
        ),
      ),
    );
    expect(find.text('Check a report'), findsNothing);
    expect(find.text('Tell us what the format requires'), findsOneWidget);
  });
}
