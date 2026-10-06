import 'package:flutter/material.dart';

import 'api.dart';
import 'widgets.dart';
import 'checking.dart';

class ReviewScreen extends StatefulWidget {
  final ReportApi api;
  final Json revision;
  const ReviewScreen({super.key, required this.api, required this.revision});
  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> with AsyncPage {
  late Json revision;
  final Map<String, Json> decisions = {}, ledger = {};
  String profileId = '', profileReason = '';
  List<Json> chapters = [];
  List<Json> blockers = [];
  bool dirty = false;
  bool get published => revision['status'] == 'PUBLISHED';
  Json get analysis => object(revision['analysis']);
  @override
  void initState() {
    super.initState();
    load(widget.revision);
  }

  void load(Json value) {
    revision = value;
    decisions.clear();
    ledger.clear();
    for (final d in objects(value['candidate_decisions'])) {
      decisions[d['candidate_id']] = d;
    }
    for (final d in objects(value['ledger_decisions'])) {
      ledger[d['evidence_id']] = d;
    }
    final profile = value['profile_review'];
    profileId = profile == null ? '' : profile['profile_id'] ?? 'none';
    profileReason = profile?['reason'] ?? '';
    chapters = profile == null ? [] : objects(profile['chapters']);
    dirty = false;
  }

  void edit(VoidCallback change) => setState(() {
    change();
    dirty = true;
  });
  String evidence(List<dynamic> ids) =>
      objects(analysis['evidence'])
          .where((e) => ids.contains(e['source_id']))
          .map((e) => '${e['excerpt']}\n${e['path']}')
          .join('\n\n');
  Widget source(List<dynamic> ids) => ExpansionTile(
    title: const Text('Source evidence'),
    children: [
      Padding(
        padding: const EdgeInsets.all(12),
        child: SelectableText(evidence(ids)),
      ),
    ],
  );
  void selectProfile(String id) => edit(() {
    profileId = id;
    if (id == 'none' || id.isEmpty) {
      chapters = [];
      return;
    }
    final p = objects(analysis['profiles'])
        .firstWhere((p) => p['profile_id'] == id);
    chapters = objects(p['chapters'])
        .asMap()
        .entries
        .map(
          (e) => <String, dynamic>{
            'index': e.key,
            'name': e.value['title'],
            'aliases': <String>[],
            'required': null,
          },
        )
        .toList();
  });
  Json patch() {
    for (final d in [
      ...decisions.values,
      ...ledger.values,
    ].where((d) => d['action'] != '')) {
      if ('${d['reason'] ?? ''}'.trim().length < 5) {
        throw ApiException(
          'Add a reason of at least five characters for each selected decision.',
        );
      }
    }
    Json? profile;
    if (profileId.isNotEmpty) {
      if (profileReason.trim().length < 5) {
        throw ApiException('Explain your chapter profile choice.');
      }
      if (chapters.any((c) => c['required'] == null)) {
        throw ApiException('Choose required or optional for every chapter.');
      }
      profile = {
        'profile_id': profileId == 'none' ? null : profileId,
        'reason': profileReason.trim(),
        'chapters': chapters,
      };
    }
    return {
      'expected_version': revision['version'],
      'candidates': decisions.values.where((d) => d['action'] != '').toList(),
      'ledger': ledger.values.where((d) => d['action'] != '').toList(),
      'profile': profile,
    };
  }

  Future<void> save({bool publish = false}) async {
    final updated = object(
      await widget.api.request(
        'PATCH',
        widget.api.revisionPath(revision),
        data: patch(),
      ),
    );
    setState(() {
      revision = updated;
      dirty = false;
    });
    final validation = object(
      await widget.api.request(
        'GET',
        '${widget.api.revisionPath(revision)}/blockers',
      ),
    );
    setState(() => blockers = objects(validation['blockers']));
    if (publish && blockers.isEmpty) {
      final result = object(
        await widget.api.request(
          'POST',
          '${widget.api.revisionPath(revision)}/publish',
          data: {'expected_version': revision['version']},
        ),
      );
      setState(() => load(result));
    }
  }

  Future<void> leave() async {
    final discard = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Discard unsaved decisions?'),
        content: const Text('Save your draft to keep these review decisions.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Keep editing'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (discard == true && mounted) {
      setState(() => dirty = false);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) Navigator.pop(context);
      });
    }
  }

  Widget decisionCard(Json candidate) {
    final id = candidate['candidate_id'] as String;
    final current = decisions.putIfAbsent(
      id,
      () => {'candidate_id': id, 'action': '', 'reason': ''},
    );
    return Panel(
      children: [
        Text(
          describe(candidate['value']),
          style: Theme.of(context).textTheme.titleMedium,
        ),
        Text(
          '${candidate['origin'] == 'EXPLICIT_PROSE' ? 'Written instruction' : 'Observed appearance only'} · ${candidate['scope']}',
        ),
        if (candidate['condition'] != 'ALWAYS')
          Notice(
            'Conditional: ${candidate['condition']}. Check current backend support before approval.',
          ),
        if ('${candidate['note'] ?? ''}'.isNotEmpty) Text(candidate['note']),
        source(candidate['evidence_ids']),
        choice(
          'Decision',
          current['action'],
          const {
            '': 'Choose a decision',
            'APPROVE': 'Approve',
            'REJECT': 'Reject',
            'DEFER': 'Defer',
          },
          (v) => edit(() {
            current['action'] = v;
            if (v.isEmpty) {
              decisions[id] = current;
            } else {
              decisions[id] = current;
            }
          }),
          enabled: !published,
          key: ValueKey('decision-$id'),
        ),
        field(
          'Reason',
          current['reason'],
          (v) => edit(() {
            current['reason'] = v;
            if (current['action'] != '') decisions[id] = current;
          }),
          lines: 2,
          enabled: !published,
          key: ValueKey('reason-$id'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !dirty && !busy,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop && !busy) leave();
    },
    child: Scaffold(
      appBar: AppBar(title: const Text('Review format')),
      body: AbsorbPointer(
        absorbing: busy,
        child: PageBody(
          key: ValueKey('${revision['revision_id']}:${revision['status']}'),
          children: [
            Text(
              revision['name'],
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text(
              'Revision ${revision['revision_number']} · ${revision['status']}',
            ),
            ...status,
            Notice(
              published
                  ? 'Published requirements are locked. Create a new draft to change them.'
                  : 'Approve only requirements you have reviewed. Observed appearance may contradict written instructions.',
            ),
            if (published)
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  FilledButton.icon(
                    onPressed: () => Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => CheckScreen(
                          api: widget.api,
                          initialRevision: revision,
                        ),
                      ),
                    ),
                    icon: const Icon(Icons.fact_check_outlined),
                    label: const Text('Check a report'),
                  ),
                  OutlinedButton(
                    onPressed: () => run(() async {
                      final fork = object(
                        await widget.api.request(
                          'POST',
                          '${widget.api.revisionPath(revision)}/fork',
                        ),
                      );
                      setState(() => load(fork));
                    }),
                    child: const Text('Create new draft'),
                  ),
                ],
              ),
            if (blockers.isNotEmpty)
              Notice(
                'Publication needs attention:\n${blockers.map(describe).join('\n\n')}',
                error: true,
              ),
            if (objects(analysis['conflicts']).isNotEmpty)
              ExpansionTile(
                title: Text(
                  '${objects(analysis['conflicts']).length} conflicts to consider',
                ),
                children: objects(analysis['conflicts'])
                    .map(
                      (c) => Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(
                          '${c['explanation']}\n${objects(analysis['candidates']).where((p) => (c['candidate_ids'] as List).contains(p['candidate_id'])).map((p) => describe(p['value'])).join(' versus ')}',
                        ),
                      ),
                    )
                    .toList(),
              ),
            const SizedBox(height: 16),
            Text(
              'Formatting requirements',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            ...objects(analysis['candidates']).map(decisionCard),
            Panel(
              children: [
                Text(
                  'Chapter profile',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                choice(
                  'Profile',
                  profileId,
                  {
                    '': 'Choose a profile',
                    'none': 'No chapter profile',
                    for (final p in objects(analysis['profiles']))
                      p['profile_id']:
                          '${p['label']} (${objects(p['chapters']).length} chapters)',
                  },
                  selectProfile,
                  enabled: !published,
                  key: ValueKey('profile-${revision['revision_id']}'),
                ),
                field(
                  'Why this profile?',
                  profileReason,
                  (v) => edit(() => profileReason = v),
                  lines: 2,
                  enabled: !published,
                  key: ValueKey('profileReason-${revision['revision_id']}'),
                ),
                ...chapters.map(
                  (c) => Column(
                    key: ValueKey('$profileId-${c['index']}'),
                    children: [
                      field(
                        'Chapter ${c['index'] + 1}',
                        c['name'],
                        (v) => edit(() => c['name'] = v),
                        enabled: !published,
                      ),
                      field(
                        'Alternative names (one per line)',
                        (c['aliases'] as List).join('\n'),
                        (v) => edit(
                          () => c['aliases'] = v
                              .split('\n')
                              .map((s) => s.trim())
                              .where((s) => s.isNotEmpty)
                              .toList(),
                        ),
                        lines: 2,
                        enabled: !published,
                      ),
                      choice(
                        'Required?',
                        c['required'] == null ? '' : '${c['required']}',
                        const {
                          '': 'Choose',
                          'true': 'Required',
                          'false': 'Optional',
                        },
                        (v) => edit(
                          () => c['required'] = v.isEmpty ? null : v == 'true',
                        ),
                        enabled: !published,
                      ),
                      const Divider(),
                    ],
                  ),
                ),
              ],
            ),
            ExpansionTile(
              title: Text(
                'Other instructions (${objects(analysis['requirement_ledger']).length})',
              ),
              subtitle: const Text(
                'Every source instruction needs a review disposition.',
              ),
              children: objects(analysis['requirement_ledger']).map((entry) {
                final id = entry['evidence_id'] as String;
                final d = ledger.putIfAbsent(
                  id,
                  () => {'evidence_id': id, 'action': '', 'reason': ''},
                );
                return Panel(
                  children: [
                    SelectableText(evidence([id])),
                    choice(
                      'Handling',
                      d['action'],
                      const {
                        '': 'Choose',
                        'ACKNOWLEDGED_PARTIAL':
                            'Partly covered by approved rules',
                        'DEFERRED': 'Defer',
                        'MANUAL': 'Check manually',
                        'OUT_OF_SCOPE': 'Outside this report’s scope',
                      },
                      (v) => edit(() {
                        d['action'] = v;
                        if (v.isEmpty) {
                          ledger[id] = d;
                        } else {
                          ledger[id] = d;
                        }
                      }),
                      enabled: !published,
                    ),
                    field(
                      'Reason',
                      d['reason'],
                      (v) => edit(() {
                        d['reason'] = v;
                        if (d['action'] != '') ledger[id] = d;
                      }),
                      lines: 2,
                      enabled: !published,
                    ),
                  ],
                );
              }).toList(),
            ),
            if (!published)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    OutlinedButton(
                      onPressed: () => run(() => save()),
                      child: const Text('Save draft'),
                    ),
                    FilledButton(
                      onPressed: () => run(() => save(publish: true)),
                      child: const Text('Save and publish'),
                    ),
                  ],
                ),
              ),
            ...((analysis['notices'] as List?) ?? []).map(
              (n) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text('$n', style: Theme.of(context).textTheme.bodySmall),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
