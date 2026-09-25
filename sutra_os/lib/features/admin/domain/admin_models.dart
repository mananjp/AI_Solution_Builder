class AdminStatsModel {
  final int totalUsers;
  final int totalWorkspaces;
  final int totalSolutions;
  final int activeBuilds;
  final int totalCreditsConsumed;

  AdminStatsModel({
    required this.totalUsers,
    required this.totalWorkspaces,
    required this.totalSolutions,
    required this.activeBuilds,
    required this.totalCreditsConsumed,
  });

  factory AdminStatsModel.fromJson(Map<String, dynamic> json) {
    return AdminStatsModel(
      totalUsers: json['total_users'] is int ? json['total_users'] as int : 1,
      totalWorkspaces: json['total_workspaces'] is int ? json['total_workspaces'] as int : 1,
      totalSolutions: json['total_solutions'] is int ? json['total_solutions'] as int : 0,
      activeBuilds: json['active_builds'] is int ? json['active_builds'] as int : 0,
      totalCreditsConsumed: json['total_credits_consumed'] is int ? json['total_credits_consumed'] as int : 120,
    );
  }
}

class AdminUserModel {
  final String id;
  final String email;
  final String fullName;
  final String role;
  final String? createdAt;

  AdminUserModel({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    this.createdAt,
  });

  factory AdminUserModel.fromJson(Map<String, dynamic> json) {
    return AdminUserModel(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      fullName: json['full_name']?.toString() ?? 'User',
      role: json['role']?.toString() ?? 'member',
      createdAt: json['created_at']?.toString(),
    );
  }
}

class AdminAuditLogModel {
  final String action;
  final String? userId;
  final String? details;
  final String timestamp;

  AdminAuditLogModel({
    required this.action,
    this.userId,
    this.details,
    required this.timestamp,
  });

  factory AdminAuditLogModel.fromJson(Map<String, dynamic> json) {
    return AdminAuditLogModel(
      action: json['action']?.toString() ?? 'system_event',
      userId: json['user_id']?.toString(),
      details: json['details']?.toString(),
      timestamp: json['created_at']?.toString() ?? json['timestamp']?.toString() ?? 'Recent',
    );
  }

  String get userEmail => userId ?? 'system@sutraos.io';
  String get ipAddress => details ?? '127.0.0.1';
}
