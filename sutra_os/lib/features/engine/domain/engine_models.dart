import '../../../core/network/json_utils.dart';

/// Mirrors `GET /api/v1/opencode/health`.
class EngineHealthModel {
  final bool healthy;
  final bool sidecarHealthy;
  final String mode;
  final String? version;
  final String? model;
  final int? latencyMs;

  const EngineHealthModel({
    required this.healthy,
    required this.sidecarHealthy,
    required this.mode,
    this.version,
    this.model,
    this.latencyMs,
  });

  factory EngineHealthModel.fromJson(Map<String, dynamic> json) {
    return EngineHealthModel(
      healthy: asBool(json['healthy']),
      sidecarHealthy: asBool(json['sidecar_healthy']),
      mode: pick(json, ['mode'], asString, 'unknown'),
      version: asStringOrNull(json['version']),
      model: asStringOrNull(json['model']),
      latencyMs: asIntOrNull(json['latency_ms']),
    );
  }

  /// The service can serve requests either through the sidecar or the
  /// integrated synthesizer fallback.
  bool get isOnline => healthy;

  String get statusLabel => isOnline ? 'ONLINE' : 'OFFLINE';
}

class EngineCheckModel {
  final String name;
  final String status;
  final String? detail;
  final String? fix;

  const EngineCheckModel({
    required this.name,
    required this.status,
    this.detail,
    this.fix,
  });

  factory EngineCheckModel.fromJson(Map<String, dynamic> json) {
    return EngineCheckModel(
      name: pick(json, ['name', 'check', 'label'], asString, 'check'),
      status: pick(json, ['status', 'state'], asString, 'unknown'),
      detail: asStringOrNull(json['detail']) ??
          asStringOrNull(json['message']) ??
          asStringOrNull(json['hint']),
      // Actionable remedy the backend attaches to a failing check.
      fix: asStringOrNull(json['fix']),
    );
  }

  bool get passed => const {'ok', 'pass', 'passed', 'healthy', 'success'}
      .contains(status.toLowerCase());
}

/// Mirrors `GET /api/v1/opencode/diagnose`.
class EngineDiagnosisModel {
  final bool ok;
  final String? model;
  final String? version;
  final List<EngineCheckModel> checks;

  const EngineDiagnosisModel({
    required this.ok,
    this.model,
    this.version,
    required this.checks,
  });

  factory EngineDiagnosisModel.fromJson(Map<String, dynamic> json) {
    return EngineDiagnosisModel(
      ok: asBool(json['ok']),
      model: asStringOrNull(json['model']),
      version: asStringOrNull(json['version']),
      checks: asList(json['checks'])
          .map(asMap)
          .map(EngineCheckModel.fromJson)
          .toList(),
    );
  }
}

/// Mirrors `GET /api/v1/system/resources`.
class SystemResourcesModel {
  final double? cpuPercent;
  final int? cpuCount;
  final double? memoryPercent;
  final double? memoryUsedMb;
  final double? memoryTotalMb;
  final double? diskPercent;
  final double? diskTotalBytes;
  final double? diskFreeBytes;

  const SystemResourcesModel({
    this.cpuPercent,
    this.cpuCount,
    this.memoryPercent,
    this.memoryUsedMb,
    this.memoryTotalMb,
    this.diskPercent,
    this.diskTotalBytes,
    this.diskFreeBytes,
  });

  factory SystemResourcesModel.fromJson(Map<String, dynamic> json) {
    final memory = asMap(json['memory']);
    return SystemResourcesModel(
      cpuPercent: asDoubleOrNull(json['cpu_percent']),
      cpuCount: asIntOrNull(json['cpu_count']),
      memoryPercent: asDoubleOrNull(memory['percent']),
      memoryUsedMb: asDoubleOrNull(memory['used_mb']),
      memoryTotalMb: asDoubleOrNull(memory['total_mb']),
      diskPercent: asDoubleOrNull(json['disk_percent']),
      diskTotalBytes: asDoubleOrNull(json['disk_total_bytes']),
      diskFreeBytes: asDoubleOrNull(json['disk_free_bytes']),
    );
  }
}
