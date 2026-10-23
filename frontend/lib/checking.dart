import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';

import 'api.dart';
import 'widgets.dart';
import 'finding_text.dart';

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

List<List<Json>> findingGroups(List<Json> items, {bool enabled = true}) {
  if (!enabled) return items.map((i) => [i]).toList();
  final grouped = <String, List<Json>>{};
  for (final item in items) {
    final key = jsonEncode([
      item['rule_id'],
      item['status'],
      item['code'],
      item['expected'],
      item['message'],
    ]);
    grouped.putIfAbsent(key, () => []).add(item);
  }
  return grouped.values.toList();
}

String findingLocation(Json item) => item['paragraph_index'] != null
    ? 'Paragraph ${item['paragraph_index'] + 1}'
    : item['section_index'] != null
    ? 'Section ${item['section_index'] + 1}'
    : 'Document';

class _ResultsScreenState extends State<ResultsScreen> with AsyncPage {
  String filter = 'FAIL';
  int limit = 20;
  bool groupRepeated = true;
  final search = TextEditingController();
  bool get complex => widget.result.containsKey('items');
  @override
  void initState() {
    super.initState();
    if (complex &&
        objects(widget.result['items']).every((i) => i['status'] != 'FAIL')) {
      filter =
          objects(widget.result['items'])
              .any((i) => i['status'] == 'NOT_CHECKED')
          ? 'NOT_CHECKED'
          : 'PASS';
    }
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

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
    final all = objects(r[complex ? 'items' : 'violations']);
    final query = search.text.trim().toLowerCase();
    final items = all.where((i) {
      if (complex && filter != 'ALL' && i['status'] != filter) return false;
      final copy = explainFinding(i);
      return query.isEmpty ||
          '${copy.title} ${copy.requiredValue} ${copy.foundValue} ${locationSummary([i])}'
              .toLowerCase()
              .contains(query);
    }).toList();
    final groups = findingGroups(items, enabled: complex && groupRepeated);
    int total(String status) =>
        findingGroups(all.where((i) => i['status'] == status).toList()).length;
    final fixes = total('FAIL'), reviews = total('NOT_CHECKED');
    final titles = {
      'FAIL': 'Needs fixing',
      'NOT_CHECKED': 'Needs review',
      'PASS': 'Passed',
      'OUT_OF_SCOPE': 'Not applicable',
      'WARNING': 'Warnings',
    };
    final heading = !complex
        ? 'Basic check result'
        : r['outcome'] == 'FAIL'
        ? 'Here’s what to fix'
        : r['outcome'] == 'INDETERMINATE'
        ? 'Some requirements remain unchecked'
        : 'Supported checks passed';
    return Scaffold(
      appBar: AppBar(title: const Text('Report results')),
      body: PageBody(
        children: [
          Text(heading, style: Theme.of(context).textTheme.headlineMedium),
          const SizedBox(height: 8),
          if (widget.revision != null)
            Text(
              'Compared with ${widget.revision!['name']}',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          const SizedBox(height: 16),
          ...status,
          if (complex)
            LayoutBuilder(
              builder: (context, constraints) => Row(
                children: [
                  Expanded(
                    child: _ResultTotal(
                      number: fixes,
                      label: 'Issue groups',
                      detail: 'Changes to make',
                      color: const Color(0xffa63b28),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _ResultTotal(
                      number: reviews,
                      label: 'Review groups',
                      detail: 'Need a human check',
                      color: const Color(0xff946200),
                    ),
                  ),
                ],
              ),
            ),
          const Notice(
            'This is not a percentage or a grade. The app checks supported rules; anything marked “Needs review” still needs a human check.',
          ),
          if (!complex)
            Text(
              'Basic engine score: ${r['overall_score']}% (limited legacy scoring, not full compliance).',
            ),
          if (complex)
            choice(
              'Show',
              filter,
              {'ALL': 'All results', ...titles},
              (v) => setState(() {
                filter = v;
                limit = 20;
              }),
            ),
          TextField(
            controller: search,
            decoration: const InputDecoration(
              labelText: 'Find an issue',
              hintText: 'Try margins, page numbers, or font',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
            onChanged: (_) => setState(() => limit = 20),
          ),
          const SizedBox(height: 20),
          Text(
            '${groups.length} ${groupRepeated && complex ? (groups.length == 1 ? 'result group' : 'result groups') : (groups.length == 1 ? 'result' : 'results')}${query.isEmpty ? '' : ' matching your search'}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          ...groups
              .take(limit)
              .map(
                (members) => ReadableFindingCard(
                  key: ValueKey(
                    '$filter:${members.first['item_id'] ?? members.first['code']}:${groups.indexOf(members)}',
                  ),
                  members: members,
                  revision: widget.revision,
                ),
              ),
          if (items.isEmpty)
            const Notice(
              'No results here. Try another category or search term.',
            ),
          if (groups.length > limit)
            OutlinedButton(
              onPressed: () => setState(() => limit += 20),
              child: const Text('Show more results'),
            ),
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: busy ? null : () => run(export),
            icon: const Icon(Icons.download_outlined),
            label: const Text('Download results'),
          ),
          ExpansionTile(
            title: const Text('About this check'),
            children: [
              const ListTile(
                title: Text('What the numbers mean'),
                subtitle: Text(
                  'Repeated findings are grouped by the same rule and message. A group can affect many locations. Word sections and paragraph numbers are not rendered page numbers.',
                ),
              ),
              if (complex)
                ListTile(
                  title: const Text('Original check counts'),
                  subtitle: Text(
                    '''${object(r['counts']).entries.map((e) => '${titles[e.key] ?? e.key}: ${e.value}').join(' · ')}
These counts include repeated sections and text segments; they are not a compliance score.''',
                  ),
                ),
              if (complex)
                SwitchListTile(
                  title: const Text('Group repeated findings'),
                  subtitle: const Text(
                    'Turn off to inspect each original check separately.',
                  ),
                  value: groupRepeated,
                  onChanged: (v) => setState(() {
                    groupRepeated = v;
                    limit = 20;
                  }),
                ),
              if (complex)
                ExpansionTile(
                  title: const Text('Technical details'),
                  children: [
                    ListTile(
                      title: Text('Checker ${r['checker_version']}'),
                      subtitle: Text(
                        '${objects(r['role_decisions']).length} paragraph-role decisions',
                      ),
                    ),
                    ...((r['limitations'] as List?) ?? []).map(
                      (x) => ListTile(title: Text('$x')),
                    ),
                  ],
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ResultTotal extends StatelessWidget {
  final int number;
  final String label, detail;
  final Color color;
  const _ResultTotal({
    required this.number,
    required this.label,
    required this.detail,
    required this.color,
  });
  @override
  Widget build(BuildContext context) => Panel(
    children: [
      Text(
        '$number',
        style: Theme.of(context).textTheme.headlineLarge
            ?.copyWith(color: color, fontWeight: FontWeight.w600),
      ),
      Text(label, style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 4),
      Text(detail, style: Theme.of(context).textTheme.bodySmall),
    ],
  );
}

class ReadableFindingCard extends StatefulWidget {
  final List<Json> members;
  final Json? revision;
  const ReadableFindingCard({super.key, required this.members, this.revision});
  @override
  State<ReadableFindingCard> createState() => _ReadableFindingCardState();
}

class _ReadableFindingCardState extends State<ReadableFindingCard> {
  int shown = 5;
  @override
  Widget build(BuildContext context) {
    final members = widget.members, item = members.first;
    final copy = explainFinding(item);
    final status = findingStatus(item);
    final color = status == 'FAIL'
        ? const Color(0xffa63b28)
        : status == 'PASS'
        ? const Color(0xff087f72)
        : const Color(0xff946200);
    final label =
        {
          'FAIL': 'Needs fixing',
          'PASS': 'Passed',
          'NOT_CHECKED': 'Needs review',
          'OUT_OF_SCOPE': 'Not applicable',
        }[status] ??
        'Review';
    final actuals = members.map((i) => explainFinding(i).foundValue).toSet();
    final found = actuals.length == 1
        ? actuals.first
        : 'Values differ across locations. See the affected locations below.';
    final evidence = objects(widget.revision?['analysis']?['evidence'])
        .where(
          (e) =>
              ((item['evidence_ids'] as List?) ?? []).contains(e['source_id']),
        )
        .toList();
    Widget value(String title, String text) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.labelLarge
                ?.copyWith(color: const Color(0xff52616b)),
          ),
          const SizedBox(height: 3),
          Text(text, style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    );
    return Panel(
      children: [
        Row(
          children: [
            Icon(
              status == 'PASS'
                  ? Icons.check_circle_outline
                  : status == 'FAIL'
                  ? Icons.error_outline
                  : Icons.help_outline,
              color: color,
              size: 20,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(color: color, fontWeight: FontWeight.w600),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          copy.title,
          style: Theme.of(context).textTheme.titleLarge
              ?.copyWith(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 5),
        Text(
          locationSummary(members),
          style: Theme.of(context).textTheme.bodyMedium
              ?.copyWith(color: const Color(0xff52616b)),
        ),
        const SizedBox(height: 10),
        LayoutBuilder(
          builder: (context, c) => c.maxWidth >= 550
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: value('Required', copy.requiredValue)),
                    const SizedBox(width: 20),
                    Expanded(child: value('Found', found)),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    value('Required', copy.requiredValue),
                    value('Found', found),
                  ],
                ),
        ),
        const SizedBox(height: 6),
        Text(
          status == 'FAIL'
              ? 'How to fix it'
              : status == 'PASS' || status == 'OUT_OF_SCOPE'
              ? 'What this means'
              : 'What to check',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 4),
        Text(copy.action),
        if (members.length > 1)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('Show affected locations'),
            subtitle: Text(
              '${members.map(findingLocation).toSet().length} affected locations',
            ),
            children: [
              ...members
                  .take(shown)
                  .map(
                    (m) => ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(findingLocation(m)),
                      subtitle: Text(explainFinding(m).foundValue),
                    ),
                  ),
              if (members.length > shown)
                TextButton(
                  onPressed: () => setState(() => shown += 20),
                  child: Text(
                    'Show more locations (${members.length - shown} remaining)',
                  ),
                ),
            ],
          ),
        if (evidence.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('What the format says'),
            children: evidence
                .map(
                  (e) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: SelectableText('${e['excerpt']}'),
                  ),
                )
                .toList(),
          ),
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('Technical details'),
          subtitle: const Text(
            'Original checker message and document references',
          ),
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: SelectableText(pretty({'checks': members})),
            ),
          ],
        ),
      ],
    );
  }
}
