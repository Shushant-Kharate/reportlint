import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reportlint_flutter/api.dart';
import 'package:reportlint_flutter/app.dart';
import 'package:reportlint_flutter/review.dart';
import 'package:reportlint_flutter/checking.dart';

Json draft() => {
  'name': 'Fictional format',
  'template_id': 't',
  'revision_id': 'r',
  'revision_number': 1,
  'version': 0,
  'status': 'DRAFT',
  'candidate_decisions': [],
  'ledger_decisions': [],
  'profile_review': null,
  'analysis': {
    'candidates': [
      {
        'candidate_id': 'c',
        'scope': 'body',
        'origin': 'EXPLICIT_PROSE',
        'condition': 'ALWAYS',
        'note': '',
        'value': {'kind': 'font_size', 'expected_pt': 12},
        'evidence_ids': ['e'],
      },
    ],
    'conflicts': [],
    'profiles': [],
    'requirement_ledger': [],
    'notices': [],
    'evidence': [
      {
        'source_id': 'e',
        'excerpt': 'Body font must be 12 pt.',
        'path': 'example',
      },
    ],
  },
};

void main() {
  testWidgets('Connection failure remains actionable', (tester) async {
    final api = ReportApi(
      'http://localhost:8000',
      client: MockClient((_) async => throw http.ClientException('offline')),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: HomeScreen(api: api, changeServer: (_) async {}),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('Cannot reach the server'), findsOneWidget);
    expect(find.text('Add format document'), findsOneWidget);
    api.close();
  });
  testWidgets(
    'Review retains a reason entered before its decision and publishes explicit choices',
    (tester) async {
      Json? sent;
      bool published = false;
      final revision = draft();
      final api = ReportApi(
        'http://localhost:8000',
        client: MockClient((request) async {
          if (request.method == 'PATCH') {
            sent = object(jsonDecode(request.body));
            revision['version'] = 1;
            return http.Response(jsonEncode(revision), 200);
          }
          if (request.url.path.endsWith('/blockers')) {
            return http.Response('{"blockers":[]}', 200);
          }
          if (request.url.path.endsWith('/publish')) {
            published = true;
            revision['status'] = 'PUBLISHED';
            return http.Response(jsonEncode(revision), 200);
          }
          return http.Response('{}', 404);
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: ReviewScreen(api: api, revision: revision),
        ),
      );
      await tester.enterText(
        find.byKey(const ValueKey('reason-c')),
        'Verified against the written instruction.',
      );
      await tester.tap(find.text('Choose a decision'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Approve').last);
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Save and publish'),
        350,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Save and publish'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save and publish'));
      await tester.pumpAndSettle();
      expect(published, isTrue);
      expect(sent!['expected_version'], 0);
      expect(
        sent!['candidates'][0]['reason'],
        'Verified against the written instruction.',
      );
      expect(sent!['candidates'][0]['action'], 'APPROVE');
      expect(find.text('Create new draft'), findsOneWidget);
      api.close();
    },
  );
  testWidgets(
    'Mobile results distinguish unchecked findings and never invent a percentage',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: ResultsScreen(
            result: {
              'items': [
                {
                  'status': 'NOT_CHECKED',
                  'message': 'Needs human review',
                  'evidence_ids': [],
                },
              ],
              'counts': {
                'PASS': 0,
                'FAIL': 0,
                'NOT_CHECKED': 1,
                'OUT_OF_SCOPE': 0,
              },
              'outcome': 'INDETERMINATE',
              'checker_version': '0.4.0',
              'role_decisions': [],
              'limitations': [],
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Some requirements remain unchecked'), findsOneWidget);
      expect(find.textContaining('not a percentage'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  test(
    'Grouping repeated failures preserves every original item and scope',
    () {
      final items = <Json>[
        {
          'item_id': 'a',
          'rule_id': 'margin',
          'status': 'FAIL',
          'code': 'MARGIN_FAIL',
          'message': 'Wrong margin',
          'expected': {'kind': 'margin'},
          'section_index': 0,
        },
        {
          'item_id': 'b',
          'rule_id': 'margin',
          'status': 'FAIL',
          'code': 'MARGIN_FAIL',
          'message': 'Wrong margin',
          'expected': {'kind': 'margin'},
          'section_index': 1,
        },
        {
          'item_id': 'c',
          'rule_id': 'margin',
          'status': 'NOT_CHECKED',
          'code': 'UNKNOWN',
          'message': 'Unresolved',
          'expected': {'kind': 'margin'},
          'section_index': 2,
        },
      ];
      final groups = findingGroups(items);
      expect(groups.length, 2);
      expect(groups.first.length, 2);
      expect(groups.expand((g) => g).map((i) => i['item_id']), ['a', 'b', 'c']);
      expect(findingGroups(items, enabled: false).length, 3);
    },
  );
  testWidgets('Grouped mobile results expose every affected location', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final items = [
      for (final section in [8, 9])
        {
          'item_id': 's$section',
          'rule_id': 'r',
          'status': 'FAIL',
          'code': 'MARGIN_FAIL',
          'expected': {'kind': 'margin', 'side': 'left', 'expected_pt': 80},
          'actual': {'margin_pt': 72},
          'message': 'Wrong stored margin',
          'section_index': section,
          'source_path': '/section/$section',
        },
    ];
    await tester.pumpWidget(
      MaterialApp(
        home: ResultsScreen(
          result: {
            'items': items,
            'outcome': 'FAIL',
            'counts': {'PASS': 0, 'FAIL': 2},
            'role_decisions': [],
            'checker_version': '0.5.0',
            'limitations': [],
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('Every affected location'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.ensureVisible(find.text('Every affected location'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Every affected location'));
    await tester.pumpAndSettle();
    expect(find.text('Section 9'), findsOneWidget);
    expect(find.text('Section 10'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
