import '../../../core/network/json_utils.dart';

class WorkspaceModel {
  final String id;
  final String orgId;
  final String name;
  final String? description;
  final int solutionCount;
  final String? createdAt;
  final String? updatedAt;

  WorkspaceModel({
    required this.id,
    required this.orgId,
    required this.name,
    this.description,
    this.solutionCount = 0,
    this.createdAt,
    this.updatedAt,
  });

  factory WorkspaceModel.fromJson(Map<String, dynamic> json) {
    return WorkspaceModel(
      id: asId(json['id']),
      orgId: asId(json['org_id']),
      name: pick(json, ['name'], asString, 'Unnamed Workspace'),
      description: asStringOrNull(json['description']),
      solutionCount: asInt(json['solution_count']),
      createdAt: asDisplayDate(json['created_at'], fallback: ''),
      updatedAt: asDisplayDate(json['updated_at'], fallback: ''),
    );
  }
}

class SolutionModel {
  final String id;
  final String workspaceId;
  final String title;
  final String? description;
  final String status;
  final String? approvalStatus;
  final String? createdAt;
  final String? updatedAt;
  /// Raw ISO timestamp, kept because [createdAt] is display-formatted and cannot
  /// be compared. Newest-first sorting needs the original value.
  final DateTime? createdAtUtc;

  SolutionModel({
    required this.id,
    required this.workspaceId,
    required this.title,
    this.description,
    required this.status,
    this.approvalStatus,
    this.createdAt,
    this.updatedAt,
    this.createdAtUtc,
  });

  factory SolutionModel.fromJson(Map<String, dynamic> json) {
    final createdRaw = asStringOrNull(json['created_at']);
    return SolutionModel(
      id: asId(json['id']),
      workspaceId: asId(json['workspace_id']),
      title: pick(json, ['title'], asString, 'Untitled Solution'),
      description: asStringOrNull(json['description']),
      status: pick(json, ['status'], asString, 'draft'),
      approvalStatus: asStringOrNull(json['approval_status']),
      createdAt: asDisplayDate(json['created_at'], fallback: ''),
      updatedAt: asDisplayDate(json['updated_at'], fallback: ''),
      createdAtUtc: createdRaw == null ? null : DateTime.tryParse(createdRaw),
    );
  }

  /// Solutions still being synthesized by the agent swarm.
  bool get isInFlight => const {'building', 'synthesizing', 'generating', 'pending'}
      .contains(status.toLowerCase());

  String get statusLabel => status.isEmpty ? 'DRAFT' : status.toUpperCase();
}

class ArtifactModel {
  final String id;
  final String solutionId;
  final String artifactType;
  final String title;
  final Map<String, dynamic> content;
  final String? contentText;
  final int version;
  final String? createdAt;

  ArtifactModel({
    required this.id,
    required this.solutionId,
    required this.artifactType,
    required this.title,
    required this.content,
    this.contentText,
    this.version = 1,
    this.createdAt,
  });

  factory ArtifactModel.fromJson(Map<String, dynamic> json) {
    return ArtifactModel(
      id: asId(json['id']),
      solutionId: asId(json['solution_id']),
      artifactType: pick(json, ['artifact_type'], asString, 'unknown'),
      title: pick(json, ['title'], asString, 'Artifact'),
      content: asMap(json['content']),
      contentText: asStringOrNull(json['content_text']),
      version: asInt(json['version'], fallback: 1),
      createdAt: asDisplayDate(json['created_at'], fallback: ''),
    );
  }
}

/// A gap flagged by `ai_state.requirements`.
class MissingRequirementModel {
  const MissingRequirementModel({
    required this.id,
    required this.kind,
    required this.text,
    required this.status,
    required this.priority,
    this.evidence = const [],
  });

  final String id;
  final String kind;
  final String text;
  final String status;
  final String priority;
  final List<EvidenceModel> evidence;

  factory MissingRequirementModel.fromJson(Map<String, dynamic> json) {
    return MissingRequirementModel(
      id: asId(json['id']),
      kind: pick(json, ['kind'], asString, 'requirement'),
      text: pick(json, ['text'], asString, ''),
      status: pick(json, ['status'], asString, 'missing'),
      priority: pick(json, ['priority'], asString, 'medium'),
      evidence: asList(json['evidence'])
          .map(asMap)
          .map(EvidenceModel.fromJson)
          .toList(),
    );
  }
}

/// A clarification from `ai_state.open_questions`.
class OpenQuestionModel {
  const OpenQuestionModel({
    required this.id,
    required this.question,
    required this.category,
    required this.whyItMatters,
    this.suggestedAnswers = const [],
  });

  final String id;
  final String question;
  final String category;
  final String whyItMatters;
  final List<String> suggestedAnswers;

  factory OpenQuestionModel.fromJson(Map<String, dynamic> json) {
    return OpenQuestionModel(
      id: asId(json['id']),
      question: pick(json, ['question'], asString, ''),
      category: pick(json, ['category'], asString, ''),
      whyItMatters: pick(
        json,
        ['why_it_matters', 'whyItMatters'],
        asString,
        '',
      ),
      suggestedAnswers: asList(json['suggested_answers'] ?? json['suggestedAnswers'])
          .map((e) => e.toString())
          .toList(),
    );
  }
}

class SolutionDetailModel {
  final SolutionModel solution;
  final List<ArtifactModel> artifacts;
  final Map<String, dynamic>? aiState;
  final List<dynamic>? conversationHistory;

  SolutionDetailModel({
    required this.solution,
    required this.artifacts,
    this.aiState,
    this.conversationHistory,
  });

  factory SolutionDetailModel.fromJson(Map<String, dynamic> json) {
    final artifacts = asList(json['artifacts'])
        .map(asMap)
        .map(ArtifactModel.fromJson)
        .toList();

    final aiState = json['ai_state'];
    final history = json['conversation_history'];

    return SolutionDetailModel(
      // The API nests the solution under `solution`, but tolerate a flat payload
      // too — otherwise the title silently falls back to "Untitled Solution".
      solution: SolutionModel.fromJson(
        asMap(json['solution'] ?? json),
      ),
      artifacts: artifacts,
      aiState: aiState == null ? null : asMap(aiState),
      conversationHistory:
          history == null ? null : asList(history).map(asMap).toList(),
    );
  }

  String get title => solution.title;
  String? get description => solution.description;

  /// Non-functional requirement / compliance gap flagged by the gap analyzer.
  List<MissingRequirementModel> get missingRequirements => asList(
        aiState?['requirements'],
      )
          .map(asMap)
          .map(MissingRequirementModel.fromJson)
          .where((r) => r.status == 'missing' || r.status == 'suggested')
          .toList();

  /// Clarification the agent still needs answered, with the business impact.
  List<OpenQuestionModel> get openQuestions => asList(
        aiState?['open_questions'],
      )
          .map(asMap)
          .map(OpenQuestionModel.fromJson)
          .toList();

  bool get hasGaps => missingRequirements.isNotEmpty || openQuestions.isNotEmpty;

  /// The blueprint is frozen once approved, so the approval controls hide.
  bool get isApproved =>
      solution.approvalStatus == 'approved' || solution.status == 'approved';

  /// Input -> Clarify -> Blueprint -> Approve, derived from the same fields the
  /// web `GuidedStepper` uses.
  String get guidedStage {
    if (isApproved) return 'approve';
    switch (solution.status) {
      case 'clarifying':
        return 'clarify';
      case 'draft':
        return 'input';
      default:
        return 'blueprint';
    }
  }

  List<String> get completedGuidedStages {
    final done = <String>['input', 'clarify'];
    if (isApproved) {
      done
        ..add('blueprint')
        ..add('approve');
    }
    return done;
  }

  String? get dbSchemaSql {
    for (final a in artifacts) {
      final t = a.artifactType.toLowerCase();
      if (t.contains('schema') || t.contains('ddl') || t.contains('database') || t.contains('sql')) {
        if (a.contentText != null && a.contentText!.isNotEmpty) {
          return a.contentText;
        }
        if (a.content.containsKey('sql')) {
          return a.content['sql']?.toString();
        }
        if (a.content.containsKey('schema')) {
          return a.content['schema']?.toString();
        }
      }
    }
    return null;
  }

  String? get apiSpecOpenapi {
    for (final a in artifacts) {
      final t = a.artifactType.toLowerCase();
      if (t.contains('openapi') || t.contains('api') || t.contains('router')) {
        if (a.contentText != null && a.contentText!.isNotEmpty) {
          return a.contentText;
        }
        if (a.content.containsKey('spec')) {
          return a.content['spec']?.toString();
        }
        if (a.content.containsKey('openapi')) {
          return a.content['openapi']?.toString();
        }
      }
    }
    return null;
  }
}

class MVPFileEntryModel {
  final String path;
  final int size;
  final bool isDir;

  MVPFileEntryModel({
    required this.path,
    required this.size,
    this.isDir = false,
  });

  factory MVPFileEntryModel.fromJson(Map<String, dynamic> json) {
    return MVPFileEntryModel(
      path: pick(json, ['path'], asString, ''),
      size: asInt(json['size']),
      isDir: asBool(json['is_dir']),
    );
  }
}

/// One step in the backend's ordered build stepper (`BUILD_STEPS` in
/// `app/api/mvp.py`). Keys match the `phase` emitted by the chat SSE stream so
/// both surfaces stay in sync.
class MVPProgressStepModel {
  const MVPProgressStepModel({
    required this.key,
    required this.label,
    required this.status,
  });

  final String key;
  final String label;

  /// `completed` | `active` | `pending`.
  final String status;

  factory MVPProgressStepModel.fromJson(Map<String, dynamic> json) {
    return MVPProgressStepModel(
      key: pick(json, ['key'], asString, ''),
      label: pick(json, ['label'], asString, ''),
      status: pick(json, ['status'], asString, 'pending'),
    );
  }
}

class MVPProgressModel {
  const MVPProgressModel({
    required this.stage,
    required this.step,
    required this.totalSteps,
    required this.percentage,
    required this.message,
    required this.steps,
  });

  final String stage;
  final int step;
  final int totalSteps;
  final int percentage;
  final String message;
  final List<MVPProgressStepModel> steps;

  factory MVPProgressModel.fromJson(Map<String, dynamic> json) {
    return MVPProgressModel(
      stage: pick(json, ['stage'], asString, ''),
      step: asInt(json['step'], fallback: 1),
      totalSteps: asInt(json['total_steps'], fallback: 5),
      percentage: asInt(json['percentage']),
      message: pick(json, ['message'], asString, ''),
      steps: asList(json['steps'])
          .map(asMap)
          .map(MVPProgressStepModel.fromJson)
          .toList(),
    );
  }
}

/// Acceptance-test outcome produced while the agent verified the generated app.
class MVPQualityModel {
  const MVPQualityModel({
    required this.passed,
    required this.total,
    required this.repairLoops,
  });

  final int passed;
  final int total;
  final int repairLoops;

  bool get isPassing => total > 0 && passed >= total;

  factory MVPQualityModel.fromJson(Map<String, dynamic> json) {
    return MVPQualityModel(
      passed: asInt(json['passed']),
      total: asInt(json['total']),
      repairLoops: asInt(json['repair_loops'], fallback: asInt(json['repairs'])),
    );
  }
}

class MVPBuildModel {
  final String buildId;
  final String solutionId;
  final int buildNumber;
  final String status;
  final String workspacePath;
  final int fileCount;
  final String? repoUrl;
  final String? renderServiceUrl;
  final String? frontendUrl;
  final String? backendUrl;
  final String? renderDeployStatus;
  final String? errorMessage;
  final MVPProgressModel? progress;
  final MVPQualityModel? quality;
  final String? renderDashboardUrl;
  final List<MVPFileEntryModel> files;

  MVPBuildModel({
    required this.buildId,
    required this.solutionId,
    required this.buildNumber,
    required this.status,
    required this.workspacePath,
    this.fileCount = 0,
    this.repoUrl,
    this.renderServiceUrl,
    this.frontendUrl,
    this.backendUrl,
    this.renderDeployStatus,
    this.errorMessage,
    this.progress,
    this.quality,
    this.renderDashboardUrl,
    this.files = const [],
  });

  factory MVPBuildModel.fromJson(Map<String, dynamic> json) {
    final filesList = asList(json['files'])
        .map(asMap)
        .map(MVPFileEntryModel.fromJson)
        .toList();

    // The list endpoint flattens a few fields; the status endpoint nests the
    // extras under app_config. Read both so one model covers either payload.
    final config = asMap(json['app_config']);

    MVPProgressModel? progress;
    final rawProgress = json['progress'] ?? config['progress'];
    if (rawProgress is Map) {
      progress = MVPProgressModel.fromJson(asMap(rawProgress));
    }

    MVPQualityModel? quality;
    final rawQuality = config['quality'];
    if (rawQuality is Map) {
      quality = MVPQualityModel.fromJson(asMap(rawQuality));
    }

    return MVPBuildModel(
      buildId: asId(json['build_id']),
      solutionId: asId(json['solution_id']),
      buildNumber: asInt(json['build_number'], fallback: 1),
      status: pick(json, ['status'], asString, 'pending'),
      workspacePath: pick(json, ['workspace_path'], asString, ''),
      fileCount: asInt(json['file_count']),
      repoUrl: asStringOrNull(json['repo_url'] ?? config['repo_url']),
      renderServiceUrl:
          asStringOrNull(json['render_service_url'] ?? config['render_service_url']),
      frontendUrl: asStringOrNull(json['frontend_url'] ?? config['frontend_url']),
      backendUrl: asStringOrNull(json['backend_url'] ?? config['backend_url']),
      renderDeployStatus:
          asStringOrNull(json['render_deploy_status'] ?? config['render_deploy_status']),
      errorMessage: asStringOrNull(json['error_message']),
      progress: progress,
      quality: quality,
      renderDashboardUrl: asStringOrNull(config['render_dashboard_url']),
      files: filesList,
    );
  }

  /// Uppercased status for the history rows, e.g. `COMPLETE`.
  String get statusLabel => status.isEmpty ? 'UNKNOWN' : status.toUpperCase();

  bool get isFailed => status == 'failed' || status == 'cancelled';

  /// A live public URL to open, preferring the frontend deployment.
  String? get liveAppUrl =>
      (frontendUrl != null && frontendUrl!.isNotEmpty) ? frontendUrl : renderServiceUrl;
}

class MVPTemplateModel {
  final String slug;
  final String title;
  final String description;
  final String appName;
  final String industry;

  MVPTemplateModel({
    required this.slug,
    required this.title,
    required this.description,
    required this.appName,
    required this.industry,
  });

  factory MVPTemplateModel.fromJson(Map<String, dynamic> json) {
    return MVPTemplateModel(
      slug: pick(json, ['slug'], asString, ''),
      title: pick(json, ['title'], asString, ''),
      description: pick(json, ['description'], asString, ''),
      appName: pick(json, ['app_name'], asString, ''),
      industry: pick(json, ['industry'], asString, ''),
    );
  }
}

/// Mirrors `GET /mvp/builds/{id}/env-plan`: which environment variables a
/// deploy needs, split into required / optional / auto-injected.
/// `GET /mvp/builds/{id}/env-plan` returns a single `env` list plus
/// auto-injected values — not the `required`/`optional` arrays this model used
/// to assume, which silently produced an empty deploy-prep screen.
class MVPEnvPlanModel {
  final List<MVPEnvVarModel> vars;
  final String? appName;
  final Map<String, String> injected;

  const MVPEnvPlanModel({
    this.vars = const [],
    this.appName,
    this.injected = const {},
  });

  factory MVPEnvPlanModel.fromJson(Map<String, dynamic> json) {
    // Tolerate the old grouped shape too, in case an older backend answers.
    final flat = asList(json['env']).map(asMap).map(MVPEnvVarModel.fromJson);
    if (flat.isNotEmpty) {
      return MVPEnvPlanModel(
        vars: flat.toList(),
        appName: asStringOrNull(json['app_name']),
        injected: asMap(json['injected']).map(
          (k, v) => MapEntry(k, v.toString()),
        ),
      );
    }
    List<MVPEnvVarModel> read(String key) => asList(json[key])
        .map(asMap)
        .map(MVPEnvVarModel.fromJson)
        .toList();
    return MVPEnvPlanModel(
      vars: [...read('required'), ...read('optional'), ...read('auto_injected')],
      injected: asMap(json['injected']).map(
        (k, v) => MapEntry(k, v.toString()),
      ),
    );
  }

  List<MVPEnvVarModel> get required =>
      vars.where((v) => v.required && !v.autoInjected).toList();

  List<MVPEnvVarModel> get optional =>
      vars.where((v) => !v.required && !v.autoInjected).toList();

  List<MVPEnvVarModel> get autoInjected =>
      vars.where((v) => v.autoInjected).toList();

  bool get hasRequired => required.isNotEmpty;
}

class MVPEnvVarModel {
  final String name;
  final String? description;
  final String? defaultValue;
  final String? current;
  final bool required;
  final bool autoInjected;
  final String? kind;

  const MVPEnvVarModel({
    required this.name,
    this.description,
    this.defaultValue,
    this.current,
    this.required = false,
    this.autoInjected = false,
    this.kind,
  });

  factory MVPEnvVarModel.fromJson(Map<String, dynamic> json) {
    return MVPEnvVarModel(
      name: pick(json, ['key', 'name'], asString, ''),
      description: asStringOrNull(json['description']),
      defaultValue: asStringOrNull(json['default']) ??
          asStringOrNull(json['default_value']),
      current: asStringOrNull(json['current']),
      required: asBool(json['required']),
      autoInjected: asBool(json['auto_injected']),
      kind: asStringOrNull(json['kind']),
    );
  }

  /// Prefill for the deploy form: what the build already knows about.
  String get effectiveValue {
    if (current != null && current!.isNotEmpty) return current!;
    if (defaultValue != null && defaultValue!.isNotEmpty) return defaultValue!;
    return '';
  }
}

/// `POST /mvp/builds/{id}/deploy` result.
class MVPDeployResultModel {
  final String repoUrl;
  final String? cloneUrl;
  final String? branch;
  final int fileCount;
  final String? renderServiceUrl;
  final String? frontendUrl;
  final String? backendUrl;
  final String? renderDeployUrl;
  final String? renderDeployStatus;

  const MVPDeployResultModel({
    required this.repoUrl,
    this.cloneUrl,
    this.branch,
    this.fileCount = 0,
    this.renderServiceUrl,
    this.frontendUrl,
    this.backendUrl,
    this.renderDeployUrl,
    this.renderDeployStatus,
  });

  factory MVPDeployResultModel.fromJson(Map<String, dynamic> json) {
    return MVPDeployResultModel(
      repoUrl: asString(json['repo_url']),
      cloneUrl: asStringOrNull(json['clone_url']),
      branch: asStringOrNull(json['branch']),
      fileCount: asInt(json['file_count']),
      renderServiceUrl: asStringOrNull(json['render_service_url']),
      frontendUrl: asStringOrNull(json['frontend_url']),
      backendUrl: asStringOrNull(json['backend_url']),
      renderDeployUrl: asStringOrNull(json['render_deploy_url']),
      renderDeployStatus: asStringOrNull(json['render_deploy_status']),
    );
  }
}

/// One Render service inside the deploy status `services` map.
class MVPDeployServiceModel {
  const MVPDeployServiceModel({
    required this.name,
    this.status = 'building',
    this.url,
    this.dashboardUrl,
    this.error,
  });

  final String name;
  final String status;
  final String? url;
  final String? dashboardUrl;
  final String? error;

  bool get isLive => status == 'live' || status == 'succeeded';
  bool get isFailed => status == 'failed' || status == 'canceled';

  factory MVPDeployServiceModel.fromJson(String name, dynamic raw) {
    final json = asMap(raw);
    return MVPDeployServiceModel(
      name: pick(json, ['name'], asString, name),
      status: pick(json, ['status'], asString, 'building'),
      url: asStringOrNull(json['url']),
      dashboardUrl: asStringOrNull(json['dashboard_url']),
      error: asStringOrNull(json['error']),
    );
  }
}

/// `GET /mvp/builds/{id}/deploy/status` — the real Render state.
class MVPDeployStatusModel {
  final String overall;
  final String? repoUrl;
  final String? frontendUrl;
  final String? backendUrl;
  final String? deployUrl;
  final Map<String, String> injectedEnv;
  final List<MVPDeployServiceModel> services;

  const MVPDeployStatusModel({
    this.overall = 'unknown',
    this.repoUrl,
    this.frontendUrl,
    this.backendUrl,
    this.deployUrl,
    this.injectedEnv = const {},
    this.services = const [],
  });

  factory MVPDeployStatusModel.fromJson(Map<String, dynamic> json) {
    return MVPDeployStatusModel(
      overall: pick(json, ['overall'], asString, 'unknown'),
      repoUrl: asStringOrNull(json['repo_url']),
      frontendUrl: asStringOrNull(json['frontend_url']),
      backendUrl: asStringOrNull(json['backend_url']),
      deployUrl: asStringOrNull(json['deploy_url']),
      injectedEnv:
          asMap(json['injected_env']).map((k, v) => MapEntry(k, v.toString())),
      services: asMap(json['services']).entries
          .map((e) => MVPDeployServiceModel.fromJson(e.key, e.value))
          .toList(),
    );
  }

  bool get isLive => overall == 'live';
  bool get isInFlight => overall == 'queued' || overall == 'building';
}

/// `POST /mvp/builds/{id}/edit` — the sandbox AI editor response.
class MVPChatEditModel {
  final String status;
  final String message;
  final List<String> updatedFiles;
  final List<MVPFileEntryModel> allFiles;
  final String buildId;
  final int buildNumber;

  const MVPChatEditModel({
    this.status = 'ok',
    this.message = '',
    this.updatedFiles = const [],
    this.allFiles = const [],
    this.buildId = '',
    this.buildNumber = 0,
  });

  factory MVPChatEditModel.fromJson(Map<String, dynamic> json) {
    return MVPChatEditModel(
      status: pick(json, ['status'], asString, 'ok'),
      message: asString(json['message']),
      updatedFiles: asList(json['updated_files'])
          .map(asMap)
          .map((m) => pick(m, ['path'], asString, ''))
          .where((p) => p.isNotEmpty)
          .toList(),
      allFiles: asList(json['all_files'])
          .map(asMap)
          .map(MVPFileEntryModel.fromJson)
          .toList(),
      buildId: pick(json, ['build_id'], asString, ''),
      buildNumber: asInt(json['build_number']),
    );
  }
}

/// `GET /artifacts/{id}/explain` — the "Why?" decision log.
class ExplainabilityModel {
  final String artifactId;
  final String artifactType;
  final String title;
  final List<DecisionModel> decisions;
  final List<String> assumptions;
  final List<EvidenceModel> evidence;
  final double confidence;

  const ExplainabilityModel({
    this.artifactId = '',
    this.artifactType = '',
    this.title = '',
    this.decisions = const [],
    this.assumptions = const [],
    this.evidence = const [],
    this.confidence = 0,
  });

  factory ExplainabilityModel.fromJson(Map<String, dynamic> json) {
    return ExplainabilityModel(
      artifactId: pick(json, ['artifact_id'], asString, ''),
      artifactType: pick(json, ['artifact_type'], asString, ''),
      title: pick(json, ['title'], asString, ''),
      decisions:
          asList(json['decisions']).map(asMap).map(DecisionModel.fromJson).toList(),
      assumptions: asList(json['assumptions'])
          .map((e) => e.toString())
          .where((s) => s.isNotEmpty)
          .toList(),
      evidence: asList(json['evidence'])
          .map((e) => asMap(e))
          .map(EvidenceModel.fromJson)
          .toList(),
      confidence: asDouble(json['confidence']),
    );
  }

  bool get isEmpty =>
      decisions.isEmpty && assumptions.isEmpty && evidence.isEmpty;
}

class DecisionModel {
  final String id;
  final String topic;
  final String choice;
  final String rationale;
  final List<String> alternatives;
  final List<String> assumptions;
  final List<EvidenceModel> evidence;
  final double confidence;
  final String impact;

  const DecisionModel({
    this.id = '',
    this.topic = '',
    this.choice = '',
    this.rationale = '',
    this.alternatives = const [],
    this.assumptions = const [],
    this.evidence = const [],
    this.confidence = 0,
    this.impact = '',
  });

  factory DecisionModel.fromJson(Map<String, dynamic> json) {
    return DecisionModel(
      id: pick(json, ['id'], asString, ''),
      topic: pick(json, ['topic'], asString, ''),
      choice: pick(json, ['choice'], asString, ''),
      rationale: pick(json, ['rationale'], asString, ''),
      alternatives: asList(json['alternatives'])
          .map((e) => e.toString())
          .toList(),
      assumptions: asList(json['assumptions'])
          .map((e) => e.toString())
          .toList(),
      evidence: asList(json['evidence'])
          .map((e) => asMap(e))
          .map(EvidenceModel.fromJson)
          .toList(),
      confidence: asDouble(json['confidence']),
      impact: pick(json, ['impact'], asString, ''),
    );
  }
}

class EvidenceModel {
  final String source;
  final String excerpt;

  const EvidenceModel({this.source = '', this.excerpt = ''});

  factory EvidenceModel.fromJson(Map<String, dynamic> json) {
    return EvidenceModel(
      source: pick(json, ['source'], asString, ''),
      excerpt: pick(json, ['excerpt'], asString, ''),
    );
  }
}

/// One row of a mounted Workable system's entity table.
class WorkableRecordModel {
  final String id;  final Map<String, dynamic> fields;

  const WorkableRecordModel({required this.id, required this.fields});

  factory WorkableRecordModel.fromJson(Map<String, dynamic> json) {
    // The API returns the row columns inline; `id` is part of that payload, so
    // it is read from the map rather than assumed to be separate.
    return WorkableRecordModel(
      id: asId(json['id']),
      fields: Map<String, dynamic>.from(json),
    );
  }

  /// Column names minus the primary key, for building an editable row.
  List<String> get columnNames =>
      fields.keys.where((k) => k != 'id').toList();

  String valueOf(String column) => asString(fields[column]);
}
