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
  final scroll = ScrollController();
  String? saveFeedback;
  bool saveNeedsAttention = false;
  bool dirty = false;
  bool get published => revision['status'] == 'PUBLISHED';
  Json get analysis => object(revision['analysis']);
  @override
  void initState() {
    super.initState();
    load(widget.revision);
  }

  @override
  void dispose() {
    scroll.dispose();
    super.dispose();
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
    blockers = [];
    saveFeedback = null;
    saveNeedsAttention = false;
  }

  void edit(VoidCallback change) => setState(() {
    change();
    dirty = true;
    saveFeedback = null;
  });
  String evidence(List<dynamic> ids) =>
      objects(analysis['evidence'])
          .where((e) => ids.contains(e['source_id']))
          .map((e) => '${e['excerpt']}')
          .join('\n\n');
  Widget source(List<dynamic> ids) => ExpansionTile(
    title: const Text('Read the format instruction'),
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
    if (!mounted) return;
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
    if (!mounted) return;
    setState(() => blockers = objects(validation['blockers']));
    if (publish && blockers.isEmpty) {
      final result = object(
        await widget.api.request(
          'POST',
          '${widget.api.revisionPath(revision)}/publish',
          data: {'expected_version': revision['version']},
        ),
      );
      if (!mounted) return;
      setState(() => load(result));
    }
  }

  String blockerSummary() {
    final counts = <String, int>{};
    for (final b in blockers) {
      final code = '${b['code']}';
      counts[code] = (counts[code] ?? 0) + 1;
    }
    return counts.entries
        .map((e) {
          switch (e.key) {
            case 'UNREVIEWED_CANDIDATE':
              return '${e.value} formatting decisions still need review';
            case 'UNREVIEWED_REQUIREMENT':
              return '${e.value} other instructions still need a handling decision';
            case 'PROFILE_REVIEW_REQUIRED':
              return 'Choose and explain a chapter profile';
            case 'CONFLICTING_APPROVALS':
              return '${e.value} conflicting approvals need resolving';
            case 'EMPTY_SPECIFICATION':
              return 'Approve at least one rule or select reviewed chapters';
            default:
              return '${e.value} ${e.key.toLowerCase().replaceAll('_', ' ')}';
          }
        })
        .join('. ');
  }

  Future<void> saveWithFeedback({bool publish = false}) async {
    if (busy) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    setState(() {
      saveFeedback = null;
      saveNeedsAttention = false;
      blockers = [];
    });
    await run(() async {
      try {
        await save(publish: publish);
      } on ApiException catch (e) {
        if (mounted && e.blockers.isNotEmpty) {
          setState(() => blockers = e.blockers);
        }
        rethrow;
      }
    });
    if (!mounted) return;
    final message = error != null
        ? error!
        : published
        ? 'Format published. You can now check a report.'
        : publish && blockers.isNotEmpty
        ? 'Draft saved, but not published. ${blockerSummary()}.'
        : 'Draft saved. Your review decisions are kept.';
    setState(() {
      saveFeedback = message;
      saveNeedsAttention = error != null || publish && blockers.isNotEmpty;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), duration: const Duration(seconds: 8)),
    );
    if (published && scroll.hasClients) {
      scroll.jumpTo(0);
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
    return ExpansionTile(
      key: ValueKey('rule-${revision['revision_id']}-$id'),
      initiallyExpanded:
          !published &&
          id == objects(analysis['candidates']).first['candidate_id'],
      maintainState: true,
      title: Text(describe(candidate['value'])),
      subtitle: Text(
        current['action'] == ''
            ? 'Not reviewed yet'
            : '${{'APPROVE': 'Approved', 'REJECT': 'Not used', 'DEFER': 'Review later'}[current['action']]}${'${current['reason'] ?? ''}'.trim().length < 5 ? ' · Add a reason' : ''}',
      ),
      childrenPadding: const EdgeInsets.fromLTRB(12, 4, 12, 16),
      children: [
        Text(
          candidate['origin'] == 'EXPLICIT_PROSE'
              ? 'Written in the format document'
              : 'Suggested from the sample’s appearance. Confirm it against the written instructions.',
        ),
        if (candidate['condition'] != 'ALWAYS')
          Notice(
            candidate['condition'] == 'HEADER_ABSENT'
                ? 'Use this margin only where there is no header.'
                : 'This rule applies only under a condition in the format document.',
          ),
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
          hint: 'Required for a selected decision (at least 5 characters).',
          enabled: !published,
          key: ValueKey('reason-$id'),
        ),
        ExpansionTile(
          title: const Text('Technical details'),
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: SelectableText(pretty(candidate)),
            ),
          ],
        ),
      ],
    );
  }

  bool completeDecision(Json? value) =>
      value != null &&
      '${value['action'] ?? ''}'.isNotEmpty &&
      '${value['reason'] ?? ''}'.trim().length >= 5;
  Widget reviewActions() {
    final candidates = objects(analysis['candidates']);
    final instructions = objects(analysis['requirement_ledger']);
    final done =
        candidates
            .where((c) => completeDecision(decisions[c['candidate_id']]))
            .length +
        instructions
            .where((e) => completeDecision(ledger[e['evidence_id']]))
            .length;
    final total = candidates.length + instructions.length;
    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: Color(0xffdce4e7))),
        ),
        padding: const EdgeInsets.fromLTRB(20, 10, 20, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '${dirty ? 'Unsaved changes' : 'Draft'} · $done of $total rule and instruction decisions complete',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton(
                  onPressed: busy ? null : () => saveWithFeedback(),
                  child: const Text('Save draft'),
                ),
                const SizedBox(width: 12),
                Flexible(
                  child: FilledButton(
                    onPressed: busy
                        ? null
                        : () => saveWithFeedback(publish: true),
                    child: const Text('Save and publish'),
                  ),
                ),
              ],
            ),
            if (busy)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: LinearProgressIndicator(),
              ),
          ],
        ),
      ),
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
      bottomNavigationBar: published ? null : reviewActions(),
      body: AbsorbPointer(
        absorbing: busy,
        child: PageBody(
          controller: scroll,
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
            if (published && saveFeedback != null) Notice(saveFeedback!),
            Notice(
              published
                  ? 'Published requirements are locked. Create a new draft to change them.'
                  : 'Review the rules, choose the required chapters, and decide how to check any remaining instructions. Save your progress at any time.',
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
              Notice('Before you publish: ${blockerSummary()}.', error: true),
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
            ExpansionTile(
              initiallyExpanded: true,
              title: const Text('1. Formatting rules'),
              subtitle: const Text(
                'Review written rules first. Open a rule to make your decision.',
              ),
              children: [
                ...objects(analysis['candidates'])
                    .where((c) => c['origin'] == 'EXPLICIT_PROSE')
                    .map(decisionCard),
                if (objects(analysis['candidates'])
                    .any((c) => c['origin'] != 'EXPLICIT_PROSE'))
                  ExpansionTile(
                    title: Text(
                      'Suggestions from sample appearance (${objects(analysis['candidates']).where((c) => c['origin'] != 'EXPLICIT_PROSE').length})',
                    ),
                    subtitle: const Text(
                      'These also need a decision. They may differ from written instructions.',
                    ),
                    children: objects(analysis['candidates'])
                        .where((c) => c['origin'] != 'EXPLICIT_PROSE')
                        .map(decisionCard)
                        .toList(),
                  ),
              ],
            ),
            Panel(
              children: [
                Text(
                  '2. Required chapters',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                choice(
                  'Chapter list',
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
                '3. Other instructions (${objects(analysis['requirement_ledger']).length})',
              ),
              subtitle: const Text(
                'Decide which instructions need manual review or do not apply.',
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
                      'How will this be checked?',
                      d['action'],
                      const {
                        '': 'Choose',
                        'COVERED': 'Represented by executable rules',
                        'ACKNOWLEDGED_PARTIAL':
                            'Partly checked by approved rules',
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
                      hint: 'Required for a selected handling decision (at least 5 characters).',
                      enabled: !published,
                    ),
                  ],
                );
              }).toList(),
            ),
            if (!published)
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (busy) const LinearProgressIndicator(),
                  if (saveFeedback != null)
                    Notice(saveFeedback!, error: saveNeedsAttention),
                  if (blockers.isNotEmpty)
                    TextButton.icon(
                      onPressed: busy
                          ? null
                          : () => scroll.animateTo(
                              0,
                              duration: const Duration(milliseconds: 300),
                              curve: Curves.easeOut,
                            ),
                      icon: const Icon(Icons.arrow_upward),
                      label: const Text('Review publication blockers'),
                    ),
                ],
              ),
            ExpansionTile(
              title: const Text('Technical details about format extraction'),
              children: [
                ...((analysis['notices'] as List?) ?? []).map(
                  (n) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      '$n',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
