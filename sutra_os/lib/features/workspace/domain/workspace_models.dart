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
      id: json['id']?.toString() ?? '',
      orgId: json['org_id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Unnamed Workspace',
      description: json['description']?.toString(),
      solutionCount: json['solution_count'] is int ? json['solution_count'] : 0,
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
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

  SolutionModel({
    required this.id,
    required this.workspaceId,
    required this.title,
    this.description,
    required this.status,
    this.approvalStatus,
    this.createdAt,
    this.updatedAt,
  });

  factory SolutionModel.fromJson(Map<String, dynamic> json) {
    return SolutionModel(
      id: json['id']?.toString() ?? '',
      workspaceId: json['workspace_id']?.toString() ?? '',
      title: json['title']?.toString() ?? 'Untitled Solution',
      description: json['description']?.toString(),
      status: json['status']?.toString() ?? 'draft',
      approvalStatus: json['approval_status']?.toString(),
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
    );
  }
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
      id: json['id']?.toString() ?? '',
      solutionId: json['solution_id']?.toString() ?? '',
      artifactType: json['artifact_type']?.toString() ?? 'unknown',
      title: json['title']?.toString() ?? 'Artifact',
      content: json['content'] is Map<String, dynamic>
          ? json['content'] as Map<String, dynamic>
          : <String, dynamic>{},
      contentText: json['content_text']?.toString(),
      version: json['version'] is int ? json['version'] : 1,
      createdAt: json['created_at']?.toString(),
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
    final solution = SolutionModel.fromJson(json);
    final rawArtifacts = json['artifacts'];
    final artifacts = <ArtifactModel>[];
    if (rawArtifacts is List) {
      for (final a in rawArtifacts) {
        if (a is Map<String, dynamic>) {
          artifacts.add(ArtifactModel.fromJson(a));
        }
      }
    }

    return SolutionDetailModel(
      solution: solution,
      artifacts: artifacts,
      aiState: json['ai_state'] is Map<String, dynamic>
          ? json['ai_state'] as Map<String, dynamic>
          : null,
      conversationHistory: json['conversation_history'] is List
          ? json['conversation_history'] as List<dynamic>
          : null,
    );
  }

  String get title => solution.title;
  String? get description => solution.description;

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
      path: json['path']?.toString() ?? '',
      size: json['size'] is int ? json['size'] : 0,
      isDir: json['is_dir'] == true,
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
    this.files = const [],
  });

  factory MVPBuildModel.fromJson(Map<String, dynamic> json) {
    final rawFiles = json['files'];
    final filesList = <MVPFileEntryModel>[];
    if (rawFiles is List) {
      for (final f in rawFiles) {
        if (f is Map<String, dynamic>) {
          filesList.add(MVPFileEntryModel.fromJson(f));
        }
      }
    }

    return MVPBuildModel(
      buildId: json['build_id']?.toString() ?? '',
      solutionId: json['solution_id']?.toString() ?? '',
      buildNumber: json['build_number'] is int ? json['build_number'] : 1,
      status: json['status']?.toString() ?? 'pending',
      workspacePath: json['workspace_path']?.toString() ?? '',
      fileCount: json['file_count'] is int ? json['file_count'] : 0,
      repoUrl: json['repo_url']?.toString(),
      renderServiceUrl: json['render_service_url']?.toString(),
      frontendUrl: json['frontend_url']?.toString(),
      backendUrl: json['backend_url']?.toString(),
      renderDeployStatus: json['render_deploy_status']?.toString(),
      files: filesList,
    );
  }
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
      slug: json['slug']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString() ?? '',
      appName: json['app_name']?.toString() ?? '',
      industry: json['industry']?.toString() ?? '',
    );
  }
}
