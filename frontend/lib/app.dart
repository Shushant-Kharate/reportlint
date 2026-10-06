import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'widgets.dart';
import 'review.dart';
import 'checking.dart';
import 'simple.dart';

void main() => runApp(const ReportLintApp());

class ReportLintApp extends StatefulWidget {
  const ReportLintApp({super.key});
  @override
  State<ReportLintApp> createState() => _ReportLintAppState();
}

class _ReportLintAppState extends State<ReportLintApp> {
  ReportApi? api;
  String? startupError;
  @override
  void initState() {
    super.initState();
    configure();
  }

  Future<void> configure() async {
    const configured = String.fromEnvironment('API_URL');
    final fallback = configured.isNotEmpty
        ? configured
        : kIsWeb
        ? Uri.base.origin
        : defaultTargetPlatform == TargetPlatform.android
        ? 'http://10.0.2.2:8000'
        : 'http://127.0.0.1:8000';
    String address = fallback;
    try {
      address =
          (await SharedPreferences.getInstance()).getString(
            'reportlint.server',
          ) ??
          fallback;
    } catch (_) {
      /* Storage can be unavailable in private browsing. */
    }
    try {
      final next = ReportApi(address);
      if (mounted) setState(() => api = next);
    } catch (e) {
      if (mounted) setState(() => startupError = '$e');
    }
  }

  Future<void> changeServer(String address) async {
    final next = ReportApi(address);
    await next.request('GET', '/debug/health');
    try {
      await (await SharedPreferences.getInstance()).setString(
        'reportlint.server',
        next.base,
      );
    } catch (_) {
      /* The connection still works without persistence. */
    }
    api?.close();
    setState(() => api = next);
  }

  @override
  void dispose() {
    api?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'ReportLint',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      fontFamily: 'ReportLint',
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff087f72)),
      scaffoldBackgroundColor: const Color(0xfff6f8fa),
      appBarTheme: const AppBarTheme(
        backgroundColor: Color(0xfff6f8fa),
        centerTitle: false,
      ),
      cardTheme: const CardThemeData(elevation: 0, color: Colors.white),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size(48, 50)),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
      ),
    ),
    home: api == null
        ? Scaffold(
            body: Center(
              child: startupError == null
                  ? const CircularProgressIndicator()
                  : Text(startupError!),
            ),
          )
        : HomeScreen(
            key: ValueKey(api!.base),
            api: api!,
            changeServer: changeServer,
          ),
  );
}

class HomeScreen extends StatefulWidget {
  final ReportApi api;
  final Future<void> Function(String) changeServer;
  const HomeScreen({super.key, required this.api, required this.changeServer});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with AsyncPage {
  List<Json> templates = [];
  @override
  void initState() {
    super.initState();
    Future.microtask(() => run(load));
  }

  Future<void> load() async {
    final data = objects(await widget.api.request('GET', '/api/v2/templates'));
    if (mounted) setState(() => templates = data);
  }

  Future<void> open(Json t) async {
    final revisions = objects(
      await widget.api.request('GET', '/api/v2/templates/${t['id']}/revisions'),
    );
    if (!mounted) return;
    final id = await showModalBottomSheet<String>(
      context: context,
      builder: (c) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(title: Text('Choose a revision')),
            ...revisions.map(
              (r) => ListTile(
                title: Text('Revision ${r['number']}'),
                subtitle: Text(r['status']),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => Navigator.pop(c, r['id']),
              ),
            ),
          ],
        ),
      ),
    );
    if (id == null) return;
    final r = object(
      await widget.api.request(
        'GET',
        '/api/v2/templates/${t['id']}/revisions/$id',
      ),
    );
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ReviewScreen(api: widget.api, revision: r),
        ),
      );
    }
    await load();
  }

  Future<void> upload() async {
    final file = await pickDoc();
    if (file == null || !mounted) return;
    final name = TextEditingController(
      text: file.name.replaceAll(RegExp(r'\.docx$', caseSensitive: false), ''),
    );
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Name this format'),
        content: TextField(
          controller: name,
          maxLength: 120,
          decoration: const InputDecoration(labelText: 'Format name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Upload and review'),
          ),
        ],
      ),
    );
    final text = name.text;
    name.dispose();
    if (confirmed != true) return;
    final r = object(
      await widget.api.request(
        'POST',
        '/api/v2/templates',
        file: file,
        fields: {'name': text},
      ),
    );
    if (mounted) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ReviewScreen(api: widget.api, revision: r),
        ),
      );
    }
    await load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text(
        'ReportLint',
        style: TextStyle(fontWeight: FontWeight.w800),
      ),
      actions: [
        IconButton(
          tooltip: 'Server settings',
          onPressed: busy
              ? null
              : () => Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => SettingsScreen(
                      address: widget.api.base,
                      onSave: widget.changeServer,
                    ),
                  ),
                ),
          icon: const Icon(Icons.settings_outlined),
        ),
      ],
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: 0,
      onDestinationSelected: busy
          ? null
          : (i) {
              if (i == 1) {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => CheckScreen(api: widget.api),
                  ),
                );
              }
            },
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.folder_outlined),
          label: 'Formats',
        ),
        NavigationDestination(
          icon: Icon(Icons.fact_check_outlined),
          label: 'Check report',
        ),
      ],
    ),
    body: AbsorbPointer(
      absorbing: busy,
      child: PageBody(
        children: [
          Text(
            'A clearer path to a better report.',
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 12),
          const Text(
            'Review the format once. Check your report against the published requirements.',
          ),
          ...status,
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () => run(upload),
            icon: const Icon(Icons.add),
            label: const Text('Add format document'),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: Text(
                  'Your formats',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton(
                tooltip: 'Refresh',
                onPressed: () => run(load),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          if (templates.isEmpty && !busy)
            const Notice(
              'Start by adding your teacher’s format document (.docx).',
            ),
          ...templates.map(
            (t) => Panel(
              children: [
                Text(t['name'], style: Theme.of(context).textTheme.titleMedium),
                Text(
                  'Latest revision ${t['latest_revision_number']} · ${t['published_revision_id'] == null ? 'Needs review' : 'Published format available'}',
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: () => run(() => open(t)),
                  child: const Text('Open format'),
                ),
              ],
            ),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.bolt_outlined),
            title: const Text('Basic checker and demo files'),
            subtitle: const Text(
              'Simple templates and the original three-file demonstration',
            ),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => SimpleScreen(api: widget.api)),
            ),
          ),
        ],
      ),
    ),
  );
}

class SettingsScreen extends StatefulWidget {
  final String address;
  final Future<void> Function(String) onSave;
  const SettingsScreen({
    super.key,
    required this.address,
    required this.onSave,
  });
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> with AsyncPage {
  late String address;
  @override
  void initState() {
    super.initState();
    address = widget.address;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Server settings')),
    body: PageBody(
      children: [
        const Text(
          'ReportLint checks documents on your Python server. Use the address of a server you trust.',
        ),
        ...status,
        field(
          'Server address',
          address,
          (v) => address = v,
          hint: 'Example: http://192.168.1.5:8000',
        ),
        FilledButton(
          onPressed: busy
              ? null
              : () => run(() async {
                  await widget.onSave(address);
                  if (context.mounted) Navigator.pop(context);
                }),
          child: const Text('Test and save connection'),
        ),
        const Notice(
          'Android emulator: http://10.0.2.2:8000\nPhysical phone: use your computer’s LAN address.\nWeb: use the same origin or configure allowed browser origins on the backend.\nFor deployment, use HTTPS.',
        ),
      ],
    ),
  );
}
