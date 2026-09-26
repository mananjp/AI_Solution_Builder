class ApiEndpoints {
  /// Base URL of the deployed backend.
  ///
  /// Defaults to the Render deployment. Override per build without editing
  /// code: `flutter run --dart-define=API_BASE_URL=https://your-host`.
  /// Never point this at `localhost` from a physical device or emulator — use
  /// the host's LAN address (`10.0.2.2` for the Android emulator) instead.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://ai-solution-builder.onrender.com',
  );

  // System / Diagnostic
  static const String health = '/health';
  static const String ready = '/ready';
  static const String openapi = '/openapi.json';
  static const String engineHealth = '/api/v1/opencode/health';
  static const String engineDiagnose = '/api/v1/opencode/diagnose';
  static const String systemResources = '/api/v1/system/resources';

  // Authentication
  static const String register = '/api/v1/auth/register';
  static const String login = '/api/v1/auth/login';
  static const String anonymous = '/api/v1/auth/anonymous';
  static const String me = '/api/v1/auth/me';
  static const String providers = '/api/v1/auth/providers';
  static const String upgradeAnonymous = '/api/v1/auth/upgrade-anonymous';
  static String oauthAuthorize(String provider) =>
      '/api/v1/auth/oauth/$provider/authorize';
  static String oauthCallback(String provider) =>
      '/api/v1/auth/oauth/$provider/callback';
  static const String meSettings = '/api/v1/auth/me/settings';

  // Workspaces
  static const String workspaces = '/api/v1/workspaces/';
  static String workspace(String id) => '/api/v1/workspaces/$id';

  // Solutions
  static const String solutions = '/api/v1/solutions/';
  static String solutionsByWorkspace(String workspaceId) =>
      '/api/v1/solutions/workspace/$workspaceId';
  static String solution(String id) => '/api/v1/solutions/$id';
  static String solutionDecisions(String id) =>
      '/api/v1/solutions/$id/decisions';
  static String solutionApprove(String id) => '/api/v1/solutions/$id/approve';
  static String solutionRequestChanges(String id) =>
      '/api/v1/solutions/$id/request-changes';
  static String solutionRegenerate(String id) =>
      '/api/v1/solutions/$id/regenerate';
  static String solutionTheme(String id) => '/api/v1/solutions/$id/theme';

  // Artifacts
  static String artifactHistory(String solutionId, String artifactType) =>
      '/api/v1/artifacts/$solutionId/history/$artifactType';
  static const String artifactRegenerate = '/api/v1/artifacts/regenerate';
  static String artifactExplain(String artifactId) =>
      '/api/v1/artifacts/$artifactId/explain';

  // Export (json / markdown / zip)
  static String exportArtifact(String solutionId, String format) =>
      '/api/v1/export/$solutionId/$format';

  // Chat / Multi-Agent Pipeline
  static const String chatSend = '/api/v1/chat/send';
  static const String chatConfirmRecommendations =
      '/api/v1/chat/confirm-recommendations';
  static const String openCodeChat = '/api/v1/opencode/chat';

  // MVP & Deploy
  static const String mvpTemplates = '/api/v1/mvp/templates';
  static const String mvpQuickBuild = '/api/v1/mvp/quick-build';
  static String mvpBuild(String solutionId) => '/api/v1/mvp/$solutionId/build';
  static String mvpBuilds(String solutionId) => '/api/v1/mvp/$solutionId/builds';
  static String mvpBuildStatus(String buildId) =>
      '/api/v1/mvp/builds/$buildId/status';
  static String mvpDownload(String buildId) =>
      '/api/v1/mvp/builds/$buildId/download';
  static String mvpSpec(String solutionId) => '/api/v1/mvp/$solutionId/spec';
  static String mvpBuildFile(String buildId, String path) =>
      '/api/v1/mvp/builds/$buildId/files/$path';
  static String mvpConfigure(String buildId) =>
      '/api/v1/mvp/builds/$buildId/configure';
  static String mvpDeploy(String buildId) => '/api/v1/mvp/builds/$buildId/deploy';
  static String mvpEnvPlan(String buildId) =>
      '/api/v1/mvp/builds/$buildId/env-plan';
  static String mvpDeployStatus(String buildId) =>
      '/api/v1/mvp/builds/$buildId/deploy/status';
  static String mvpEdit(String buildId) => '/api/v1/mvp/builds/$buildId/edit';
  static String mvpPreview(String buildId) =>
      '/api/v1/mvp/builds/$buildId/preview';
  static String mvpPreviewDestroy(String buildId) =>
      '/api/v1/mvp/builds/$buildId/preview/destroy';
  static String mvpSandboxChat(String buildId) =>
      '/api/v1/mvp/builds/$buildId/sandbox/chat';
  static String mvpDeleteBuild(String buildId) =>
      '/api/v1/mvp/builds/$buildId';

  // Workable Systems (Mounted Live App)
  static String workableProvision(String solutionId) =>
      '/api/v1/workable/$solutionId/provision';

  static String workableModules(String solutionId) =>
      '/api/v1/workable/$solutionId/modules';
  static String workableSeed(String solutionId, {int rows = 5}) =>
      '/api/v1/workable/$solutionId/seed?rows=$rows';
  static String workableModuleIndex(String solutionId, String moduleName) =>
      '/api/v1/workable/$solutionId/$moduleName';
  static String workableRecords(String solutionId, String moduleName, String entity) =>
      '/api/v1/workable/$solutionId/$moduleName/$entity';
  static String workableRecord(
          String solutionId, String moduleName, String entity, String rowId) =>
      '/api/v1/workable/$solutionId/$moduleName/$entity/$rowId';

  // Upload / Ingestion Pipeline
  static const String uploadDocument = '/api/v1/upload/document';
  static const String uploadUrl = '/api/v1/upload/url';
  static const String uploadImage = '/api/v1/upload/image';
  static const String uploadAudio = '/api/v1/upload/audio';

  // Billing & Credits
  static const String billingPlans = '/api/v1/billing/plans';
  static const String billingUsage = '/api/v1/billing/usage';
  static const String billingTransactions = '/api/v1/billing/transactions';
  static const String billingTopup = '/api/v1/billing/topup';
  static const String billingQuote = '/api/v1/billing/quote';
  static const String billingCheckout = '/api/v1/billing/checkout';

  // Admin & Governance
  static const String adminStats = '/api/v1/admin/stats';
  static const String adminUsers = '/api/v1/admin/users';
  static const String adminAuditLogs = '/api/v1/admin/audit-logs';
}
