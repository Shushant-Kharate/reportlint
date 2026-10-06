import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';

import 'api.dart';
import 'widgets.dart';

class CheckScreen extends StatefulWidget {
  final ReportApi api;
  final Json? initialRevision;
  const CheckScreen({super.key, required this.api, this.initialRevision});
  @override
  State<CheckScreen> createState() => _CheckScreenState();
}

class _CheckScreenState extends State<CheckScreen> with AsyncPage {
  final Map<String, String> options = {};
  String selected = '';
  PickedDoc? file;
  Json? roleReview;
  @override
  void initState() {
    super.initState();
    Future.microtask(() => run(load));
  }

  Future<void> load() async {
    final templates = objects(
      await widget.api.request('GET', '/api/v2/templates'),
    );
    final choices = <String, String>{};
    for (final t in templates) {
      final revisions = objects(
        await widget.api.request(
          'GET',
          '/api/v2/templates/${t['id']}/revisions',
        ),
      );
      for (final r in revisions.where((r) => r['status'] == 'PUBLISHED')) {
        choices['${t['id']}/${r['id']}'] =
            '${t['name']} · revision ${r['number']}';
      }
    }
    if (!mounted) return;
    setState(() {
      options.clear();
      options.addAll(choices);
      final initial = widget.initialRevision;
      if (initial != null && selected.isEmpty) {
        selected = '${initial['template_id']}/${initial['revision_id']}';
      }
      if (!options.containsKey(selected)) selected = '';
    });
  }

  Future<Json> revision() async {
    if (selected.isEmpty || file == null) {
      throw ApiException('Choose a published format and a report.');
    }
    final parts = selected.split('/');
    return object(
      await widget.api.request(
        'GET',
        '/api/v2/templates/${parts[0]}/revisions/${parts[1]}',
      ),
    );
  }

  Future<void> preview() async {
    final r = await revision();
    final p = object(
      await widget.api.request(
        'POST',
        '${widget.api.revisionPath(r)}/role-preview',
        file: file,
      ),
    );
    if (!mounted) return;
    final reviewed = await Navigator.push<Json>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            RolesScreen(preview: p, revision: r, previous: roleReview),
      ),
    );
    if (reviewed != null && mounted) setState(() => roleReview = reviewed);
  }

  Future<void> check() async {
    final r = await revision();
    final result = object(
      await widget.api.request(
        'POST',
        '${widget.api.revisionPath(r)}/check',
        file: file,
        fields: roleReview == null
            ? null
            : {'role_review': jsonEncode(roleReview)},
      ),
    );
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ResultsScreen(result: result, revision: r),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Check report'),
      actions: [
        IconButton(
          tooltip: 'Refresh formats',
          onPressed: busy ? null : () => run(load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: AbsorbPointer(
      absorbing: busy,
      child: PageBody(
        children: [
          Text(
            'Does your report follow the format?',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 12),
          const Text(
            'Choose a reviewed format, upload your Word report, and see exactly what needs attention.',
          ),
          ...status,
          if (options.isEmpty && !busy)
            const Notice(
              'No published formats yet. Add and review a format from the Formats screen.',
            ),
          choice(
            'Published format',
            selected,
            {'': 'Choose a format', ...options},
            (v) => setState(() {
              selected = v;
              roleReview = null;
            }),
            key: ValueKey('formats-$selected-${options.length}'),
          ),
          Panel(
            children: [
              const Icon(Icons.upload_file_outlined, size: 40),
              const SizedBox(height: 12),
              Text(file?.name ?? 'Select your report (.docx)'),
              const Text(
                'Up to 20 MB. Your report is not retained by the checking API.',
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: () => run(() async {
                  final f = await pickDoc();
                  if (f != null && mounted) {
                    setState(() {
                      file = f;
                      roleReview = null;
                    });
                  }
                }),
                child: const Text('Choose report'),
              ),
            ],
          ),
          FilledButton.icon(
            onPressed: () => run(check),
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Check report'),
          ),
          const SizedBox(height: 16),
          OutlinedButton(
            onPressed: () => run(preview),
            child: const Text('Review paragraph roles'),
          ),
          if (roleReview != null)
            Notice(
              '${objects(roleReview!['decisions']).length} explicit paragraph decisions will be applied.',
            ),
          const Notice(
            'A check covers supported requirements only. Unchecked items need review; item counts are not a compliance percentage.',
          ),
        ],
      ),
    ),
  );
}

class RolesScreen extends StatefulWidget {
  final Json preview, revision;
  final Json? previous;
  const RolesScreen({
    super.key,
    required this.preview,
    required this.revision,
    this.previous,
  });
  @override
  State<RolesScreen> createState() => _RolesScreenState();
}

class _RolesScreenState extends State<RolesScreen> {
  final Map<int, Json> decisions = {};
  String search = '', filter = 'reviewable';
  int limit = 30;
  String? error;
  @override
  void initState() {
    super.initState();
    final p = widget.previous;
    if (p != null &&
        p['report_sha256'] == widget.preview['report_sha256'] &&
        p['snapshot_sha256'] == widget.preview['snapshot_sha256']) {
      for (final d in objects(p['decisions'])) {
        decisions[d['paragraph_index']] = Map<String, dynamic>.from(d);
      }
    }
  }

  void finish() {
    if (decisions.values.any(
      (d) =>
          '${d['reason'] ?? ''}'.trim().length < 5 ||
          (d['role'] == 'CHAPTER' && d['chapter_index'] == null),
    )) {
      setState(
        () => error = 'Every changed role needs a reason and chapter headings need a chapter selection.',
      );
      return;
    }
    Navigator.pop(context, {
      'report_sha256': widget.preview['report_sha256'],
      'snapshot_sha256': widget.preview['snapshot_sha256'],
      'decisions': decisions.values.toList(),
    });
  }

  @override
  Widget build(BuildContext context) {
    final paragraphs = objects(widget.preview['paragraphs'])
        .where(
          (p) =>
              (filter == 'all' || p['reviewable'] == true) &&
              '${p['excerpt']}'.toLowerCase().contains(search.toLowerCase()),
        )
        .toList();
    final chapters = objects(
      widget.revision['publication']?['profile']?['chapters'],
    );
    return Scaffold(
      appBar: AppBar(title: const Text('Paragraph roles')),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: FilledButton(
            onPressed: finish,
            child: Text('Apply ${decisions.length} decisions'),
          ),
        ),
      ),
      body: PageBody(
        children: [
          const Notice(
            'Suggestions are not approvals. Change only roles you can verify in the document. Back cancels unsaved role edits.',
          ),
          if (error != null) Notice(error!, error: true),
          field(
            'Search paragraph text',
            search,
            (v) => setState(() {
              search = v;
              limit = 30;
            }),
          ),
          choice(
            'Show',
            filter,
            const {
              'reviewable': 'Reviewable paragraphs',
              'all': 'All paragraphs',
            },
            (v) => setState(() {
              filter = v;
              limit = 30;
            }),
          ),
          Text(
            '${paragraphs.length} paragraphs · ${decisions.length} decisions',
          ),
          ...paragraphs.take(limit).map((p) {
            final index = p['paragraph_index'] as int;
            final d =
                decisions[index] ??
                <String, dynamic>{
                  'paragraph_index': index,
                  'source_path': p['source_path'],
                  'role': '',
                  'chapter_index': null,
                  'reason': '',
                };
            return Panel(
              key: ValueKey(index),
              children: [
                Text(
                  'Paragraph ${index + 1} · ${p['detected_role']}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                SelectableText('${p['excerpt']}'),
                Text('${p['proposal_reason']}'),
                if (p['excerpt_truncated'] == true)
                  const Text(
                    'Excerpt shortened; refer to the original document.',
                  ),
                if (p['suggested_role'] != null)
                  Text('Suggestion: ${p['suggested_role']}'),
                if (p['reviewable'] == true) ...[
                  choice(
                    'Confirmed role',
                    d['role'],
                    const {
                      '': 'Keep detected role',
                      'BODY': 'Body prose',
                      'CHAPTER': 'Chapter heading',
                      'EXCLUDE': 'Exclude',
                    },
                    (v) => setState(() {
                      d['role'] = v;
                      if (v != 'CHAPTER') d['chapter_index'] = null;
                      if (v.isEmpty) {
                        decisions.remove(index);
                      } else {
                        decisions[index] = d;
                      }
                    }),
                  ),
                  if (d['role'] == 'CHAPTER')
                    choice(
                      'Chapter',
                      d['chapter_index']?.toString() ?? '',
                      {
                        '': 'Choose chapter',
                        for (final c in chapters)
                          '${c['index']}': '${c['name']}',
                      },
                      (v) => setState(() {
                        d['chapter_index'] = int.tryParse(v);
                        decisions[index] = d;
                      }),
                    ),
                  if (d['role'] != '')
                    field('Reason', d['reason'], (v) {
                      d['reason'] = v;
                      decisions[index] = d;
                    }, lines: 2),
                ],
              ],
            );
          }),
          if (paragraphs.length > limit)
            OutlinedButton(
              onPressed: () => setState(() => limit += 30),
              child: const Text('Show more paragraphs'),
            ),
        ],
      ),
    );
  }
}

class ResultsScreen extends StatefulWidget {
  final Json result;
  final Json? revision;
  const ResultsScreen({super.key, required this.result, this.revision});
  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> with AsyncPage {
  String filter = 'FAIL';
  int limit = 30;
  bool get complex => widget.result.containsKey('items');
  Future<void> export() async {
    await FilePicker.saveFile(
      dialogTitle: 'Save check result',
      fileName: 'reportlint-result.json',
      type: FileType.custom,
      allowedExtensions: ['json'],
      bytes: Uint8List.fromList(
        utf8.encode(
          pretty({'result': widget.result, 'revision': widget.revision}),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.result;
    final items = objects(r[complex ? 'items' : 'violations'])
        .where((i) => !complex || filter == 'ALL' || i['status'] == filter)
        .toList();
    final counts = complex
        ? object(r['counts'])
        : <String, dynamic>{
            'PASS': r['total_checks_passed'],
            'FAIL': r['total_errors'],
            'WARNING': r['total_warnings'],
          };
    final titles = {
      'PASS': 'Passed',
      'FAIL': 'Issues',
      'NOT_CHECKED': 'Not checked',
      'OUT_OF_SCOPE': 'Excluded',
      'WARNING': 'Warnings',
    };
    final heading = !complex
        ? 'Basic check result'
        : r['outcome'] == 'FAIL'
        ? 'Formatting issues found'
        : r['outcome'] == 'INDETERMINATE'
        ? 'Some requirements remain unchecked'
        : 'Supported checks passed';
    return Scaffold(
      appBar: AppBar(title: const Text('Results')),
      body: PageBody(
        children: [
          Text(heading, style: Theme.of(context).textTheme.headlineSmall),
          ...status,
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: counts.entries
                .map(
                  (e) => SizedBox(
                    width: 145,
                    child: Panel(
                      children: [
                        Text(
                          '${e.value}',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        Text(titles[e.key] ?? e.key),
                      ],
                    ),
                  ),
                )
                .toList(),
          ),
          const Notice(
            'These are check-item counts, not a percentage of document compliance. Passing supported checks does not certify the whole report.',
          ),
          if (!complex)
            Text(
              'Basic engine score: ${r['overall_score']}% (limited legacy scoring, not full compliance).',
            ),
          if (complex)
            Text(
              'Checker ${r['checker_version']} · ${objects(r['role_decisions']).length} manual role decisions',
            ),
          if (widget.revision != null)
            Text(
              '${widget.revision!['name']} · revision ${widget.revision!['revision_number']}',
            ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: busy ? null : () => run(export),
            icon: const Icon(Icons.download_outlined),
            label: const Text('Export result and evidence'),
          ),
          if (complex)
            choice(
              'Show findings',
              filter,
              {'ALL': 'All findings', ...titles},
              (v) => setState(() {
                filter = v;
                limit = 30;
              }),
            ),
          Text('${items.length} findings'),
          ...items.take(limit).map((i) {
            final location = i['paragraph_index'] != null
                ? 'Paragraph ${i['paragraph_index'] + 1}'
                : i['section_index'] != null
                ? 'Section ${i['section_index'] + 1}'
                : 'Document';
            return Panel(
              children: [
                Text(
                  '${titles[i['status']] ?? i['severity'] ?? ''} · $location',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text('${i['message']}'),
                ExpansionTile(
                  title: const Text('Expected and actual'),
                  children: [
                    ListTile(
                      title: const Text('Expected'),
                      subtitle: SelectableText(describe(i['expected'])),
                    ),
                    ListTile(
                      title: const Text('Actual'),
                      subtitle: SelectableText(describe(i['actual'])),
                    ),
                  ],
                ),
                ExpansionTile(
                  title: const Text('Evidence and location'),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: SelectableText(
                        '${i['source_path'] ?? describe(i['location'])}\n${objects(widget.revision?['analysis']?['evidence']).where((e) => ((i['evidence_ids'] as List?) ?? []).contains(e['source_id'])).map((e) => e['excerpt']).join('\n\n')}',
                      ),
                    ),
                  ],
                ),
              ],
            );
          }),
          if (items.isEmpty) const Notice('No findings in this category.'),
          if (items.length > limit)
            OutlinedButton(
              onPressed: () => setState(() => limit += 30),
              child: const Text('Show more findings'),
            ),
          if (complex)
            ExpansionTile(
              title: const Text('Limits of this check'),
              children: ((r['limitations'] as List?) ?? [])
                  .map((x) => ListTile(title: Text('$x')))
                  .toList(),
            ),
        ],
      ),
    );
  }
}
