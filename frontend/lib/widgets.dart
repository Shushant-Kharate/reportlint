import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';

import 'api.dart';

Future<PickedDoc?> pickDoc() async {
  final file = await FilePicker.pickFile(
    type: FileType.custom,
    allowedExtensions: ['docx'],
  );
  if (file == null) return null;
  final size = await file.length();
  if (size != null && size > 20 * 1024 * 1024) {
    throw ApiException('Choose a document up to 20 MB.');
  }
  return PickedDoc(file.name, await file.readAsBytes());
}

String describe(dynamic value) {
  if (value == null) return 'Not resolved';
  if (value is! Map) return '$value';
  final v = object(value);
  switch (v['kind']) {
    case 'font_family':
      return 'Font: ${v['font']}';
    case 'font_size':
      return 'Text size: ${v['expected_pt']} pt';
    case 'chapter_font_size':
      return 'Chapter title size: ${v['expected_pt']} pt';
    case 'chapter_case':
      return 'Chapter titles: upper and lowercase';
    case 'abstract_word_count':
      return 'Abstract: ${v['expected_words']} words';
    case 'abstract_keywords':
      return 'Abstract: labeled keywords required';
    case 'line_spacing_multiple':
      return 'Line spacing: ${v['multiplier']}×';
    case 'margin':
      return '${v['side']} margin: ${((v['expected_pt'] as num) * 25.4 / 72).toStringAsFixed(1)} mm';
    case 'page_size':
      return 'Page: ${((v['width_pt'] as num) * 25.4 / 72).toStringAsFixed(1)} × ${((v['height_pt'] as num) * 25.4 / 72).toStringAsFixed(1)} mm';
  }
  return v.entries
      .map(
        (e) =>
            '${e.key.replaceAll('_', ' ')}: ${e.value is Map ? describe(e.value) : e.value}',
      )
      .join('\n');
}

Widget field(
  String label,
  String value,
  ValueChanged<String> changed, {
  int lines = 1,
  String? hint,
  bool enabled = true,
  Key? key,
}) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 8),
  child: TextFormField(
    key: key,
    initialValue: value,
    enabled: enabled,
    minLines: lines,
    maxLines: lines == 1 ? 1 : lines + 3,
    decoration: InputDecoration(
      labelText: label,
      helperText: hint,
      helperMaxLines: 3,
      border: const OutlineInputBorder(),
    ),
    onChanged: changed,
  ),
);

Widget choice(
  String label,
  String value,
  Map<String, String> options,
  ValueChanged<String> changed, {
  bool enabled = true,
  Key? key,
}) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 8),
  child: DropdownButtonFormField<String>(
    key: key,
    initialValue: value,
    isExpanded: true,
    decoration: InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
    ),
    items: options.entries
        .map(
          (e) => DropdownMenuItem(
            value: e.key,
            child: Text(e.value, overflow: TextOverflow.ellipsis),
          ),
        )
        .toList(),
    onChanged: enabled
        ? (v) {
            if (v != null) changed(v);
          }
        : null,
  ),
);

class Notice extends StatelessWidget {
  final String text;
  final bool error;
  const Notice(this.text, {super.key, this.error = false});
  @override
  Widget build(BuildContext context) => Container(
    width: double.infinity,
    margin: const EdgeInsets.symmetric(vertical: 12),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      color: error ? const Color(0xffffefed) : const Color(0xffedf7f4),
      borderRadius: BorderRadius.circular(12),
    ),
    child: Text(
      text,
      style: TextStyle(
        color: error ? const Color(0xff9b2525) : const Color(0xff175f55),
      ),
    ),
  );
}

class Panel extends StatelessWidget {
  final List<Widget> children;
  const Panel({super.key, required this.children});
  @override
  Widget build(BuildContext context) => Card(
    margin: const EdgeInsets.only(bottom: 16),
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    ),
  );
}

class PageBody extends StatelessWidget {
  final List<Widget> children;
  const PageBody({super.key, required this.children});
  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 820),
      child: ListView(padding: const EdgeInsets.all(20), children: children),
    ),
  );
}

mixin AsyncPage<T extends StatefulWidget> on State<T> {
  bool busy = false;
  String? error;
  Future<void> run(Future<void> Function() action) async {
    if (!mounted || busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await action();
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e is ApiException
              ? e.message
              : 'Something went wrong. Please retry. $e';
        });
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  List<Widget> get status => [
    if (busy) const LinearProgressIndicator(),
    if (error != null) Notice(error!, error: true),
  ];
}
