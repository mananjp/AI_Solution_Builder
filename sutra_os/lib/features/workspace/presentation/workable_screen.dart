import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';
import '../../../core/widgets/sutra_button.dart';
import '../data/workspace_repository.dart';
import '../domain/workspace_models.dart';
import 'workspace_providers.dart';

/// Workable Systems preview: provision the solution's live app, seed demo
/// rows, and browse its modules/entities.
///
/// The web app exposes this as the "Mounted Live App" panel. Without a screen
/// here, the `workable/*` endpoints the repository already wraps were
/// unreachable from the app.
class WorkableScreen extends ConsumerStatefulWidget {
  const WorkableScreen({super.key});

  @override
  ConsumerState<WorkableScreen> createState() => _WorkableScreenState();
}

class _WorkableScreenState extends ConsumerState<WorkableScreen> {
  String? _module;
  String? _entity;
  bool _busy = false;
  String? _message;

  @override
  Widget build(BuildContext context) {
    final solutionId = ref.watch(effectiveSolutionIdProvider);
    final repo = ref.watch(workspaceRepositoryProvider);

    if (solutionId == null) {
      return const Scaffold(
        body: Center(child: Text('No blueprint selected')),
      );
    }

    return Scaffold(
      backgroundColor: AppColors.lightBackground,
      appBar: AppBar(
        backgroundColor: AppColors.lightSurface,
        surfaceTintColor: Colors.transparent,
        title:
            Text('Live App', style: AppTextStyles.serifHeading(fontSize: 20)),
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: repo.fetchWorkableModules(solutionId),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(color: AppColors.gold),
            );
          }
          if (snapshot.hasError) {
            return _notProvisioned(solutionId, '${snapshot.error}');
          }

          final data = snapshot.data ?? const <String, dynamic>{};
          final modules = _asModuleList(data);
          if (modules.isEmpty) {
            return _notProvisioned(solutionId, null);
          }

          final module = _module != null && modules.contains(_module)
              ? _module!
              : modules.first;
          final entities = _entitiesFor(data, module);

          if (_entity == null || !entities.contains(_entity)) {
            _entity = entities.isNotEmpty ? entities.first : null;
          }

          return ListView(
            padding: const EdgeInsets.all(AppSpacing.md),
            children: [
              Text(
                'MOUNTED LIVE APP',
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 10,
                  color: AppColors.gold,
                  letterSpacing: 1.6,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    child: SutraButton.outline(
                      label: _busy ? 'Seeding...' : 'Seed demo data',
                      height: 38,
                      onPressed: _busy
                          ? null
                          : () => _seed(solutionId, module),
                    ),
                  ),
                ],
              ),
              if (_message != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  _message!,
                  style: AppTextStyles.bodySmall(
                    fontSize: 11,
                    color: AppColors.lightTextSecondary,
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              if (modules.length > 1)
                _chipRow(modules, _module ?? module, (v) {
                  setState(() {
                    _module = v;
                    _entity = null;
                  });
                }),
              const SizedBox(height: AppSpacing.md),
              if (_entity != null)
                _chipRow(entities, _entity!, (v) => setState(() => _entity = v)),
              const SizedBox(height: AppSpacing.md),
              if (_entity == null)
                Text(
                  'This module exposes no entities.',
                  style: AppTextStyles.bodySmall(
                    color: AppColors.lightTextSecondary,
                  ),
                )
              else
                _Records(
                  solutionId: solutionId,
                  moduleName: module,
                  entityName: _entity!,
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _chipRow(List<String> values, String selected, ValueChanged<String> onTap) {
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final value in values)
          GestureDetector(
            onTap: () => onTap(value),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: value == selected
                    ? AppColors.blackButton
                    : AppColors.lightSurface,
                borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                border: Border.all(
                  color: value == selected
                      ? AppColors.blackButton
                      : AppColors.lightBorder,
                ),
              ),
              child: Text(
                value.toUpperCase(),
                style: AppTextStyles.smallCapsLabel(
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  color: value == selected
                      ? Colors.white
                      : AppColors.lightTextPrimary,
                ),
              ),
            ),
          ),
      ],
    );
  }

  /// The modules payload is keyed either as a map of module name to entities or
  /// as a `{"modules": [...]}` list, depending on backend version.
  List<String> _asModuleList(Map<String, dynamic> data) {
    final direct = data['modules'];
    if (direct is List) {
      return direct
          .map((e) => e is Map ? '${e['name'] ?? e['module']}' : '$e')
          .where((e) => e.isNotEmpty && e != 'null')
          .toList();
    }
    return data.keys
        .where((k) => k != 'ok' && k != 'message' && k != 'status')
        .toList();
  }

  List<String> _entitiesFor(Map<String, dynamic> data, String module) {
    final value = data[module];
    if (value is List) {
      return value
          .map((e) => e is Map ? '${e['name'] ?? e['entity']}' : '$e')
          .where((e) => e.isNotEmpty && e != 'null')
          .toList();
    }
    if (value is Map) return value.keys.map((k) => '$k').toList();
    return const [];
  }

  Widget _notProvisioned(String solutionId, String? error) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        const SizedBox(height: AppSpacing.xl),
        const Icon(Icons.rocket_launch_outlined,
            size: 40, color: AppColors.gold),
        const SizedBox(height: AppSpacing.md),
        Center(
          child: Text(
            'No live app mounted',
            style: AppTextStyles.serifHeading(fontSize: 19),
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Center(
          child: Text(
            error ?? 'Provision Workable Systems to browse this solution\'s '
                'live data model.',
            textAlign: TextAlign.center,
            style: AppTextStyles.bodySmall(
              color: AppColors.lightTextSecondary,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        SutraButton(
          label: _busy ? 'Provisioning...' : 'Provision',
          isLoading: _busy,
          width: double.infinity,
          onPressed: _busy ? null : () => _provision(solutionId),
        ),
      ],
    );
  }

  Future<void> _provision(String solutionId) async {
    setState(() => _busy = true);
    try {
      await ref.read(workspaceRepositoryProvider).provisionWorkable(solutionId);
      ref.invalidate(workspaceRepositoryProvider);
      if (mounted) {
        setState(() {});
        _toast('Live app provisioned.');
      }
    } catch (e) {
      if (mounted) _toast('Could not provision: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _seed(String solutionId, String module) async {
    setState(() => _busy = true);
    try {
      await ref.read(workspaceRepositoryProvider).seedWorkable(solutionId);
      if (mounted) {
        setState(() => _message = 'Seeded demo rows into $module.');
        _toast('Demo data seeded.');
      }
    } catch (e) {
      if (mounted) _toast('Seed failed: $e', isError: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _toast(String message, {bool isError = false}) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: isError ? AppColors.statusErrorRed : null,
        ),
      );
  }
}

class _Records extends ConsumerStatefulWidget {
  const _Records({
    required this.solutionId,
    required this.moduleName,
    required this.entityName,
  });

  final String solutionId;
  final String moduleName;
  final String entityName;

  @override
  ConsumerState<_Records> createState() => _RecordsState();
}

class _RecordsState extends ConsumerState<_Records> {
  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(workspaceRepositoryProvider);

    return FutureBuilder<List<WorkableRecordModel>>(
      future: repo.fetchWorkableRecords(
        widget.solutionId,
        widget.moduleName,
        widget.entityName,
      ),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.all(AppSpacing.lg),
            child: Center(
              child: CircularProgressIndicator(color: AppColors.gold),
            ),
          );
        }
        if (snapshot.hasError) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
            child: Text(
              '${snapshot.error}',
              style: AppTextStyles.bodySmall(
                color: AppColors.statusErrorRed,
              ),
            ),
          );
        }
        final records = snapshot.data ?? const <WorkableRecordModel>[];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  '${records.length} ROWS',
                  style: AppTextStyles.smallCapsLabel(
                    fontSize: 9,
                    color: AppColors.lightTextMuted,
                  ),
                ),
                const Spacer(),
                // Seeding is a demo shortcut; this is the real create path.
                TextButton.icon(
                  onPressed: () => _openEditor(null),
                  icon: const Icon(Icons.add, size: 14),
                  label: Text(
                    'NEW ROW',
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 9,
                      color: AppColors.gold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            if (records.isEmpty)
              Text(
                'No rows in ${widget.entityName}. Add one, or use '
                '"Seed demo data".',
                style: AppTextStyles.bodySmall(
                  color: AppColors.lightTextSecondary,
                ),
              ),
            for (final record in records)
              Container(
                margin: const EdgeInsets.only(bottom: 6),
                padding: const EdgeInsets.all(AppSpacing.sm),
                decoration: BoxDecoration(
                  color: AppColors.lightSurface,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
                  border: Border.all(color: AppColors.lightBorder),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (final column in record.columnNames)
                            Padding(
                              padding: const EdgeInsets.only(bottom: 2),
                              child: Text(
                                '$column: ${record.valueOf(column)}',
                                style: AppTextStyles.mono(
                                  fontSize: 11,
                                  color: AppColors.lightTextPrimary,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                    IconButton(
                      tooltip: 'Edit',
                      iconSize: 16,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: () => _openEditor(record),
                      icon: const Icon(
                        Icons.edit_outlined,
                        color: AppColors.lightTextSecondary,
                      ),
                    ),
                    IconButton(
                      tooltip: 'Delete',
                      iconSize: 16,
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(),
                      onPressed: () => _delete(record),
                      icon: const Icon(
                        Icons.delete_outline,
                        color: AppColors.statusErrorRed,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }

  /// Creates a row when [record] is null, otherwise replaces its values.
  Future<void> _openEditor(WorkableRecordModel? record) async {
    final columns = record?.columnNames ?? const <String>[];
    final controller = TextEditingController(
      text: record == null
          ? ''
          : '{${columns.map((c) => '"$c": ${jsonEncode(record.valueOf(c))}').join(', ')}}',
    );

    final payload = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(record == null ? 'New row' : 'Edit row'),
        content: TextField(
          controller: controller,
          maxLines: 8,
          style: AppTextStyles.mono(fontSize: 12),
          decoration: const InputDecoration(
            labelText: 'JSON object of column values',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final text = controller.text.trim();
              if (text.isEmpty) {
                Navigator.of(dialogContext).pop(<String, dynamic>{});
                return;
              }
              try {
                final decoded = jsonDecode(text);
                if (decoded is Map<String, dynamic>) {
                  Navigator.of(dialogContext).pop(decoded);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Must be a JSON object.')),
                  );
                }
              } catch (_) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('That is not valid JSON.')),
                );
              }
            },
            child: Text(record == null ? 'Create' : 'Save'),
          ),
        ],
      ),
    );

    controller.dispose();
    if (payload == null || !mounted) return;

    final repo = ref.read(workspaceRepositoryProvider);
    try {
      if (record == null) {
        await repo.createWorkableRecord(
          widget.solutionId,
          widget.moduleName,
          widget.entityName,
          payload,
        );
      } else {
        await repo.updateWorkableRecord(
          widget.solutionId,
          widget.moduleName,
          widget.entityName,
          record.id,
          payload,
        );
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(record == null ? 'Row created.' : 'Row saved.')),
        );
      }
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Save failed: $e')),
        );
      }
    }
  }

  Future<void> _delete(WorkableRecordModel record) async {
    final id = record.id;
    if (id.isEmpty) return;
    try {
      await ref.read(workspaceRepositoryProvider).deleteWorkableRecord(
            widget.solutionId,
            widget.moduleName,
            widget.entityName,
            id,
          );
      setState(() {});
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Delete failed: $e'),
            backgroundColor: AppColors.statusErrorRed,
          ),
        );
      }
    }
  }
}
