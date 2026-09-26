import '../../../core/network/json_utils.dart';

/// Mirrors `GET /api/v1/admin/stats`.
class AdminStatsModel {
  final int totalUsers;
  final int totalOrganizations;
  final int totalWorkspaces;
  final int totalSolutions;
  final int totalCreditsConsumed;
  final String activeLlmModel;
  final String systemStatus;

  const AdminStatsModel({
    required this.totalUsers,
    required this.totalOrganizations,
    required this.totalWorkspaces,
    required this.totalSolutions,
    required this.totalCreditsConsumed,
    required this.activeLlmModel,
    required this.systemStatus,
  });

  factory AdminStatsModel.fromJson(Map<String, dynamic> json) {
    return AdminStatsModel(
      totalUsers: asInt(json['total_users']),
      totalOrganizations: asInt(json['total_organizations']),
      totalWorkspaces: asInt(json['total_workspaces']),
      totalSolutions: asInt(json['total_solutions']),
      // The API names this `total_ai_credits_consumed`.
      totalCreditsConsumed: asInt(
        pick(json, ['total_ai_credits_consumed', 'total_credits_consumed'], asInt, 0),
      ),
      activeLlmModel: pick(json, ['active_llm_model'], asString, 'unknown'),
      systemStatus: pick(json, ['system_status'], asString, 'unknown'),
    );
  }
}

class AdminUserModel {
  final String id;
  final String email;
  final String fullName;
  final String role;
  final String? orgName;
  final String? createdAt;

  AdminUserModel({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    this.orgName,
    this.createdAt,
  });

  factory AdminUserModel.fromJson(Map<String, dynamic> json) {
    return AdminUserModel(
      id: asId(json['id']),
      email: pick(json, ['email'], asString, ''),
      fullName: pick(json, ['full_name', 'name'], asString, 'User'),
      role: pick(json, ['role'], asString, 'member'),
      orgName: asStringOrNull(json['org_name']),
      createdAt: asDisplayDate(json['created_at'], fallback: 'Unknown'),
    );
  }
}

/// Mirrors `GET /api/v1/admin/audit-logs`, which reports credit transactions
/// rather than per-user IP events. There is no user or IP on the payload, so
/// none is invented here.
class AdminAuditLogModel {
  final String id;
  final String? orgId;
  final String action;
  final String? description;
  final int amount;
  final String status;
  final String timestamp;

  AdminAuditLogModel({
    required this.id,
    this.orgId,
    required this.action,
    this.description,
    required this.amount,
    required this.status,
    required this.timestamp,
  });

  factory AdminAuditLogModel.fromJson(Map<String, dynamic> json) {
    return AdminAuditLogModel(
      id: asId(json['id']),
      orgId: asStringOrNull(json['org_id']),
      action: pick(json, ['action'], asString, 'system_event'),
      description: asStringOrNull(json['description']),
      amount: asInt(json['amount']),
      status: pick(json, ['status'], asString, 'UNKNOWN'),
      timestamp: asDisplayDate(
        pick(json, ['timestamp', 'created_at'], asString, ''),
        fallback: 'Recent',
      ),
    );
  }

  /// Signed credit delta: positive is a top-up, negative is consumption.
  String get amountLabel => amount >= 0 ? '+$amount' : '$amount';
}
