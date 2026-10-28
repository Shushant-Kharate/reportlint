import 'package:flutter/material.dart';

import 'api.dart';
import 'widgets.dart';
import 'checking.dart';
import 'review.dart';
import 'finding_text.dart';

class AutomaticFormatScreen extends StatefulWidget {
  final ReportApi api;
  final Json preparation;
  const AutomaticFormatScreen({
    super.key,
    required this.api,
    required this.preparation,
  });
  @override
  State<AutomaticFormatScreen> createState() => _AutomaticFormatScreenState();
}

class _AutomaticFormatScreenState extends State<AutomaticFormatScreen>
    with AsyncPage {
  late Json data;
  final explanations = <String, String>{};
  String? feedback;
  Json get revision => object(data['revision']);
  List<Json> get questions => objects(data['questions']);
  List<Json> get clarifications =>
      questions.where((q) => q['kind'] != 'MANUAL').toList();
  List<Json> get manual =>
      questions.where((q) => q['kind'] == 'MANUAL').toList();
  @override
  void initState() {
    super.initState();
    data = widget.preparation;
  }

  Future<void> clarify(String? evidenceId) async {
    final key = evidenceId ?? 'additional';
    final text = (explanations[key] ?? '').trim();
    if (text.length < 5) {
      throw ApiException('Explain the requirement in a short sentence.');
    }
    final response = object(
      await widget.api.request(
        'POST',
        '${widget.api.revisionPath(revision)}/clarify',
        data: {
          'expected_version': revision['version'],
          'explanation': text,
          'evidence_id': ?evidenceId,
        },
      ),
    );
    if (mounted) {
      setState(() {
        data = response;
        feedback =
            'Explanation saved. ${data['rule_count']} rules are ready; ${clarifications.length} need clarification and ${manual.length} remain manual.';
        explanations.remove(key);
      });
    }
  }

  Future<void> submitExplanation(String? evidenceId) async {
    await run(() => clarify(evidenceId));
    if (!mounted) return;
    ScaffoldMessenger.of(context).clearSnackBars();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(error ?? feedback ?? 'Explanation processed.'),
        duration: const Duration(seconds: 8),
      ),
    );
  }

  Widget requirementCard(Json q) => Card(
    key: ValueKey<String>('question-card-${q['evidence_id']}'),
    child: ExpansionTile(
      key: ValueKey<String>('question-${q['evidence_id']}'),
      maintainState: true,
      title: Text(
        '${q['instruction']}',
        maxLines: 3,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        q['kind'] == 'MANUAL' ? 'Manual check' : 'Needs clarification',
      ),
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              SelectableText('${q['instruction']}'),
              const SizedBox(height: 12),
              explanation('${q['evidence_id']}'),
            ],
          ),
        ),
      ],
    ),
  );

  Widget explanation(String? evidenceId) {
    final id = evidenceId ?? 'additional';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        field(
          evidenceId == null
              ? 'Describe a requirement'
              : 'Explain this instruction',
          explanations[id] ?? '',
          (v) => explanations[id] = v,
          lines: 3,
          key: ValueKey('explanation-$id-${revision['revision_id']}'),
          hint: evidenceId == null
              ? 'Example: Body text must use Arial at 12 pt with 1.5 line spacing.'
              : 'Include every requirement for this instruction. Your explanation replaces its earlier interpretation.',
        ),
        OutlinedButton.icon(
          onPressed: busy ? null : () => submitExplanation(evidenceId),
          icon: const Icon(Icons.auto_fix_high_outlined),
          label: const Text('Apply explanation'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final ready = data['ready'] == true;
    final rules = objects(object(revision['publication'] ?? {})['rules']);
    return Scaffold(
      appBar: AppBar(title: const Text('Format setup')),
      body: AbsorbPointer(
        absorbing: busy,
        child: PageBody(
          children: [
            Text(
              ready
                  ? 'Your format is ready'
                  : 'Tell us what the format requires',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 8),
            Text(
              '${revision['name']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Notice('${data['message']}'),
            ...status,
            if (feedback != null) Notice(feedback!),
            const SizedBox(height: 12),
            Text(
              '${data['rule_count']} ${data['rule_count'] == 1 ? 'rule' : 'rules'} ready',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              clarifications.isEmpty
                  ? 'No clarification is currently requested. Report evidence can still leave individual checks unresolved.'
                  : '${clarifications.length} ${clarifications.length == 1 ? 'instruction needs' : 'instructions need'} clarification. Unresolved requirements are not counted as passes.',
            ),
            if (manual.isNotEmpty)
              Text(
                '${manual.length} other instructions remain manual. You can check the supported rules now.',
              ),
            if (ready) ...[
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        CheckScreen(api: widget.api, initialRevision: revision),
                  ),
                ),
                icon: const Icon(Icons.fact_check_outlined),
                label: const Text('Check a report'),
              ),
            ],
            const SizedBox(height: 20),
            if (rules.isNotEmpty)
              ExpansionTile(
                title: const Text('See the automatic rules'),
                children: [
                  ...rules.map((r) {
                    final text = explainFinding({
                      'expected': r['value'],
                      'status': 'PASS',
                    });
                    return ListTile(
                      title: Text(text.title),
                      subtitle: Text(text.requiredValue),
                    );
                  }),
                ],
              ),
            if (clarifications.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Only unclear instructions need your input',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              const Text(
                'Explain a requirement in ordinary English. The app will extract its values, save the source, and create an updated format. Unsupported explanations remain unresolved.',
              ),
              ...clarifications.map(requirementCard),
            ],
            if (manual.isNotEmpty)
              ExpansionTile(
                title: Text(
                  'Other requirements not checked automatically (${manual.length})',
                ),
                children: [
                  const Notice(
                    'These requirements still need a manual check. You may explain a supported formatting requirement here, or explicitly say that an instruction does not apply.',
                  ),
                  ...manual.map(requirementCard),
                ],
              ),
            const SizedBox(height: 16),
            ExpansionTile(
              title: const Text('Add or correct a requirement'),
              children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: explanation(null),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) =>
                        ReviewScreen(api: widget.api, revision: revision),
                  ),
                );
                final latest = object(
                  await widget.api.request(
                    'GET',
                    '${widget.api.revisionPath(revision)}/preparation',
                  ),
                );
                if (mounted) setState(() => data = latest);
              },
              child: const Text('Advanced rule review'),
            ),
            const Notice(
              'Automatic setup uses explicit English instructions and consistent template properties. It cannot certify every requirement in an arbitrary document. Published versions stay unchanged when you add explanations.',
            ),
          ],
        ),
      ),
    );
  }
}
