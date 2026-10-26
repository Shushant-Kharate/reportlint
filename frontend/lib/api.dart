import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';

typedef Json = Map<String, dynamic>;
const maxUploadMb = int.fromEnvironment('MAX_UPLOAD_MB', defaultValue: 20);
Json object(dynamic value) =>
    value is Json ? value : Map<String, dynamic>.from(value as Map);
List<Json> objects(dynamic value) =>
    (value as List? ?? []).map(object).toList();
String pretty(dynamic value) =>
    const JsonEncoder.withIndent('  ').convert(value);

class ApiException implements Exception {
  final String message;
  final List<Json> blockers;
  ApiException(this.message, [this.blockers = const []]);
  @override
  String toString() => message;
}

class PickedDoc {
  final String name;
  final Uint8List bytes;
  bool get isPdf => name.toLowerCase().endsWith('.pdf');
  PickedDoc(this.name, this.bytes, {bool allowPdf = false}) {
    if (!name.toLowerCase().endsWith('.docx') && !(allowPdf && isPdf)) {
      throw ApiException(
        allowPdf
            ? 'Choose a DOCX or PDF report.'
            : 'Choose a Word .docx document.',
      );
    }
    if (bytes.isEmpty || bytes.length > maxUploadMb * 1024 * 1024) {
      throw ApiException('Choose a nonempty document up to $maxUploadMb MB.');
    }
  }
}

class ReportApi {
  final http.Client client;
  final String base;
  final Duration requestTimeout;
  String? workspaceCookie;
  final void Function(String)? onWorkspaceCookie;
  ReportApi(
    String address, {
    http.Client? client,
    this.workspaceCookie,
    this.onWorkspaceCookie,
    this.requestTimeout = const Duration(minutes: 3),
  }) : base = normalizeAddress(address),
       client = client ?? http.Client();

  static String normalizeAddress(String address) {
    final uri = Uri.tryParse(address.trim());
    if (uri == null ||
        !['http', 'https'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/')) {
      throw ApiException(
        'Enter the server origin, for example https://reports.example.com or http://192.168.1.5:8000.',
      );
    }
    return uri.origin;
  }

  String revisionPath(Json revision) =>
      '/api/v2/templates/${revision['template_id']}/revisions/${revision['revision_id']}';

  Future<dynamic> request(
    String method,
    String path, {
    Json? data,
    PickedDoc? file,
    String fileField = 'file',
    Map<String, String>? fields,
  }) async {
    final uri = Uri.parse('$base$path');
    final http.BaseRequest request;
    if (file != null) {
      final extra = utf8.encode(jsonEncode(fields ?? {})).length + 2048;
      if (file.bytes.length + extra > maxUploadMb * 1024 * 1024) {
        throw ApiException(
          'The document and paragraph-review data together must be under $maxUploadMb MB.',
        );
      }
      request = http.MultipartRequest(method, uri)
        ..fields.addAll(fields ?? {})
        ..files.add(
          http.MultipartFile.fromBytes(
            fileField,
            file.bytes,
            filename: file.name,
          ),
        );
    } else {
      request = http.Request(method, uri);
      if (data != null) {
        (request as http.Request).body = jsonEncode(data);
        request.headers['Content-Type'] = 'application/json';
      }
    }
    request.headers['Accept'] = 'application/json';
    // Browsers handle the HttpOnly cookie themselves. Native HTTP clients need
    // to retain it explicitly, scoped to the selected server origin.
    if (!kIsWeb) {
      if (workspaceCookie != null) {
        request.headers['Cookie'] = workspaceCookie!;
      }
    }
    try {
      final response = await (() async {
        final stream = await client.send(request);
        return http.Response.fromStream(stream);
      })().timeout(requestTimeout);
      if (!kIsWeb) {
        final cookie = RegExp(r'reportlint_workspace=[a-f0-9]{64}')
            .firstMatch(response.headers['set-cookie'] ?? '')
            ?.group(0);
        if (cookie != null) {
          workspaceCookie = cookie;
          onWorkspaceCookie?.call(cookie);
        }
      }
      dynamic decoded;
      try {
        decoded = jsonDecode(response.body);
      } catch (_) {
        throw ApiException(
          response.statusCode == 413
              ? 'The document and review data exceed this server’s upload limit. Try a smaller DOCX.'
              : 'The server returned an unexpected response (${response.statusCode}). Check the server address.',
        );
      }
      if (response.statusCode >= 400) {
        final detail = decoded is Map ? decoded['detail'] : null;
        if (detail is Map) {
          final code = detail['code'];
          final message = code == 'REVISION_CONFLICT'
              ? 'This draft changed elsewhere. Your edits remain here. Reload the saved draft before retrying.'
              : code == 'STALE_ROLE_REVIEW'
              ? 'The document or format changed. Preview the paragraphs again.'
              : '${detail['message'] ?? 'Request failed (${response.statusCode}).'}';
          throw ApiException(message, objects(detail['blockers']));
        }
        throw ApiException(
          detail is String
              ? detail
              : 'The server rejected this request (${response.statusCode}). Review your inputs.',
        );
      }
      return decoded;
    } on TimeoutException {
      throw ApiException(
        'The request timed out. Refresh saved formats before retrying an upload or publication.',
      );
    } on http.ClientException {
      throw ApiException(
        'Cannot reach the server. Check its address, network connection and allowed browser origins.',
      );
    }
  }

  void close() => client.close();
}
