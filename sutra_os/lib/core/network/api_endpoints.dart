class ApiEndpoints {
  static const String baseUrl = 'https://ai-solution-builder.onrender.com';
  
  // System / Diagnostic
  static const String health = '/health';
  static const String ready = '/ready';
  static const String openapi = '/openapi.json';
  
  // Authentication
  static const String register = '/api/v1/auth/register';
  static const String login = '/api/v1/auth/login';
  static const String anonymous = '/api/v1/auth/anonymous';
  static const String me = '/api/v1/auth/me';
  static const String providers = '/api/v1/auth/providers';
  
  // Workspaces
  static const String workspaces = '/api/v1/workspaces/';
  static String workspace(String id) => '/api/v1/workspaces/$id';
  
  // Solutions
  static const String solutions = '/api/v1/solutions/';
  static String solutionsByWorkspace(String workspaceId) => '/api/v1/solutions/workspace/$workspaceId';
  static String solution(String id) => '/api/v1/solutions/$id';
  static String solutionDecisions(String id) => '/api/v1/solutions/$id/decisions';
  
  // Chat / Multi-Agent Pipeline
  static const String chatSend = '/api/v1/chat/send';
  static const String confirmRecommendations = '/api/v1/chat/confirm-recommendations';
  
  // MVP & Deploy
  static const String mvpTemplates = '/api/v1/mvp/templates';
  static const String mvpQuickBuild = '/api/v1/mvp/quick-build';
  static String mvpBuild(String solutionId) => '/api/v1/mvp/$solutionId/build';
  static String mvpBuilds(String solutionId) => '/api/v1/mvp/$solutionId/builds';
  static String mvpBuildStatus(String buildId) => '/api/v1/mvp/builds/$buildId/status';
  static String mvpDownload(String buildId) => '/api/v1/mvp/builds/$buildId/download';
  static String mvpSpec(String solutionId) => '/api/v1/mvp/$solutionId/spec';
  
  // Workable Systems (Mounted Live App)
  static String workableModules(String solutionId) => '/api/v1/workable/$solutionId/modules';
  static String workableModuleIndex(String solutionId, String moduleName) => 
      '/api/v1/workable/$solutionId/$moduleName';
  static String workableRecords(String solutionId, String moduleName, String entity) => 
      '/api/v1/workable/$solutionId/$moduleName/$entity';

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

  // Deployer / User Profile Settings
  static const String meSettings = '/api/v1/auth/me/settings';

  // Admin & Governance
  static const String adminStats = '/api/v1/admin/stats';
  static const String adminUsers = '/api/v1/admin/users';
  static const String adminAuditLogs = '/api/v1/admin/audit-logs';
}
