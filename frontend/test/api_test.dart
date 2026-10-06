import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:reportlint_flutter/api.dart';

void main() {
  test('Rejects empty, oversized and non-docx uploads', () {
    expect(
      () => PickedDoc('report.pdf', Uint8List(2)),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => PickedDoc('report.docx', Uint8List(0)),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => PickedDoc('report.docx', Uint8List(20 * 1024 * 1024 + 1)),
      throwsA(isA<ApiException>()),
    );
  });
  test('Server setting accepts origins only', () {
    expect(
      ReportApi.normalizeAddress('http://localhost:8000/'),
      'http://localhost:8000',
    );
    for (final value in [
      'file:///tmp',
      'https://user:secret@example.com',
      'https://example.com/api',
      'https://example.com?q=x',
    ]) {
      expect(
        () => ReportApi.normalizeAddress(value),
        throwsA(isA<ApiException>()),
      );
    }
  });
  test('Multipart check preserves bound role review and filename', () async {
    final api = ReportApi(
      'http://localhost:8000',
      client: MockClient((r) async {
        expect(r.method, 'POST');
        expect(r.url.path, '/api/v2/templates/t/revisions/r/check');
        expect(r.body, contains('filename="report.docx"'));
        expect(r.body, contains('name="role_review"'));
        expect(r.body, contains('exact-report-hash'));
        return http.Response('{"outcome":"FAIL"}', 200);
      }),
    );
    final data = await api.request(
      'POST',
      '/api/v2/templates/t/revisions/r/check',
      file: PickedDoc('report.docx', Uint8List.fromList([1, 2, 3])),
      fields: {
        'role_review': jsonEncode({'report_sha256': 'exact-report-hash'}),
      },
    );
    expect(data['outcome'], 'FAIL');
    api.close();
  });
  test(
    'Stale review errors are explained and publication blockers retained',
    () async {
      final api = ReportApi(
        'http://localhost:8000',
        client: MockClient(
          (r) async => http.Response(
            jsonEncode({
              'detail': {
                'code': 'REVISION_CONFLICT',
                'message': 'stale',
                'blockers': [
                  {'code': 'UNREVIEWED_CANDIDATE'},
                ],
              },
            }),
            409,
          ),
        ),
      );
      try {
        await api.request('PATCH', '/test', data: {});
        fail('Expected failure');
      } on ApiException catch (e) {
        expect(e.message, contains('Your edits remain'));
        expect(e.blockers.single['code'], 'UNREVIEWED_CANDIDATE');
      }
      api.close();
    },
  );
}
