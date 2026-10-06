import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'api.dart';
import 'widgets.dart';
import 'checking.dart';

Future<PickedDoc> demoDoc(String name) async => PickedDoc(
  name,
  (await rootBundle.load('assets/demo/$name')).buffer.asUint8List(),
);

class SimpleScreen extends StatefulWidget {
  final ReportApi api;
  const SimpleScreen({super.key, required this.api});
  @override
  State<SimpleScreen> createState() => _SimpleScreenState();
}

class _SimpleScreenState extends State<SimpleScreen> with AsyncPage {
  List<Json> templates = [];
  @override
  void initState() {
    super.initState();
    Future.microtask(() => run(load));
  }

  Future<void> load() async {
    final items = objects(await widget.api.request('GET', '/api/templates'));
    if (mounted) setState(() => templates = items);
  }

  Future<void> open(Json template) async {
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => SimpleReview(api: widget.api, template: template),
        ),
      );
    }
    await load();
  }

  Future<void> upload({bool demo = false}) async {
    final file = demo ? await demoDoc('format_template.docx') : await pickDoc();
    if (file == null) return;
    final result = object(
      await widget.api.request('POST', '/api/templates', file: file),
    );
    await open(result);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Basic checker')),
    body: AbsorbPointer(
      absorbing: busy,
      child: PageBody(
        children: [
          const Notice(
            'Basic templates infer rules from appearance. For complex written requirements, use the main Formats workflow.',
          ),
          ...status,
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton(
                onPressed: () => run(upload),
                child: const Text('Upload basic template'),
              ),
              OutlinedButton(
                onPressed: () => run(() => upload(demo: true)),
                child: const Text('Try demo template'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          ...templates.map(
            (t) => Panel(
              children: [
                Text(t['name'], style: Theme.of(context).textTheme.titleMedium),
                Text(t['status']),
                OutlinedButton(
                  onPressed: () => run(() async {
                    await open(
                      object(
                        await widget.api.request(
                          'GET',
                          '/api/templates/${t['id']}',
                        ),
                      ),
                    );
                  }),
                  child: const Text('Review and check'),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class SimpleReview extends StatefulWidget {
  final ReportApi api;
  final Json template;
  const SimpleReview({super.key, required this.api, required this.template});
  @override
  State<SimpleReview> createState() => _SimpleReviewState();
}

class _SimpleReviewState extends State<SimpleReview> with AsyncPage {
  late Json template, rules;
  bool dirty = false;
  @override
  void initState() {
    super.initState();
    template = widget.template;
    rules = object(template['ruleset']);
  }

  Future<void> save({bool publish = false}) async {
    final updated = object(
      await widget.api.request(
        'PUT',
        '/api/templates/${template['id']}/rules',
        data: rules,
      ),
    );
    setState(() {
      template = updated;
      dirty = false;
    });
    if (publish) {
      final r = object(
        await widget.api.request(
          'POST',
          '/api/templates/${template['id']}/publish',
        ),
      );
      setState(() => template = r);
    }
  }

  Future<void> check({String? demo}) async {
    if (dirty) throw ApiException('Save your template edits before checking.');
    final file = demo == null ? await pickDoc() : await demoDoc(demo);
    if (file == null) return;
    final result = object(
      await widget.api.request(
        'POST',
        '/api/templates/${template['id']}/check',
        file: file,
        fileField: 'report',
      ),
    );
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ResultsScreen(result: result)),
      );
    }
  }

  Future<void> leave() async {
    final discard = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Discard unsaved changes?'),
        content: const Text('Save your draft to keep these template changes.'),
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

  void edit(VoidCallback action) => setState(() {
    action();
    dirty = true;
  });
  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !dirty && !busy,
    onPopInvokedWithResult: (didPop, _) {
      if (!didPop && !busy) leave();
    },
    child: Scaffold(
      appBar: AppBar(title: const Text('Basic format review')),
      body: AbsorbPointer(
        absorbing: busy,
        child: PageBody(
          children: [
            Text(
              template['name'],
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            Text('${template['status']}'),
            ...status,
            const Notice(
              'Review inferred values before publishing. Checking a draft is a trial, not a published specification.',
            ),
            ...['typography_rules', 'paragraph_rules', 'page_rules'].expand(
              (group) => objects(rules[group]).map(
                (r) => Panel(
                  children: [
                    Text(
                      '${r['type']}'.replaceAll('_', ' '),
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    Text('Scope: ${r['scope']}'),
                    Text('${r['inference_note']}'),
                    ...object(r['expected_value']).entries.map(
                      (e) => e.value is bool
                          ? SwitchListTile(
                              title: Text(e.key.replaceAll('_', ' ')),
                              value: e.value,
                              onChanged: (v) => edit(() {
                                r['expected_value'][e.key] = v;
                              }),
                            )
                          : field(
                              e.key.replaceAll('_', ' '),
                              '${e.value}',
                              (v) => edit(() {
                                r['expected_value'][e.key] =
                                    (e.value is num ||
                                        const {
                                          'size_pt',
                                          'multiplier',
                                          'pt',
                                          'before_pt',
                                          'after_pt',
                                          'first_line_indent_pt',
                                          'width_pt',
                                          'height_pt',
                                          'top',
                                          'bottom',
                                          'left',
                                          'right',
                                        }.contains(e.key))
                                    ? num.tryParse(v) ?? v
                                    : v;
                              }),
                              key: ValueKey('${r['id']}-${e.key}'),
                            ),
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('I reviewed this rule'),
                      value: r['teacher_confirmed'] == true,
                      onChanged: (v) => edit(() => r['teacher_confirmed'] = v),
                    ),
                  ],
                ),
              ),
            ),
            ...objects(rules['structure_rules']).map(
              (r) => Panel(
                children: [
                  field(
                    'Section name',
                    r['canonical_name'],
                    (v) => edit(() => r['canonical_name'] = v),
                  ),
                  field(
                    'Alternative names (one per line)',
                    (r['aliases'] as List).join('\n'),
                    (v) => edit(
                      () => r['aliases'] = v
                          .split('\n')
                          .where((s) => s.trim().isNotEmpty)
                          .toList(),
                    ),
                    lines: 2,
                  ),
                  SwitchListTile(
                    title: const Text('Required section'),
                    value: r['required'],
                    onChanged: (v) => edit(() => r['required'] = v),
                  ),
                ],
              ),
            ),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                OutlinedButton(
                  onPressed: () => run(() => save()),
                  child: const Text('Save draft'),
                ),
                FilledButton(
                  onPressed: () => run(() => save(publish: true)),
                  child: const Text('Publish basic template'),
                ),
              ],
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () => run(check),
              child: const Text('Choose report and check'),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                OutlinedButton(
                  onPressed: () =>
                      run(() => check(demo: 'correct_report.docx')),
                  child: const Text('Check correct demo'),
                ),
                OutlinedButton(
                  onPressed: () =>
                      run(() => check(demo: 'formatting_errors_report.docx')),
                  child: const Text('Check error demo'),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
