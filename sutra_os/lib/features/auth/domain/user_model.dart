class UserModel {
  final String id;
  final String email;
  final String fullName;
  final String role;
  final String? orgId;
  final bool isAnonymous;
  final String? createdAt;

  UserModel({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
    this.orgId,
    this.isAnonymous = false,
    this.createdAt,
  });

  bool get isAdmin => role.toLowerCase() == 'admin';
  bool get isGuest => isAnonymous || role.toLowerCase() == 'guest';
  bool get isMember => role.toLowerCase() == 'member' || isAdmin;

  String get roleDisplayName {
    if (isAdmin) return 'Admin Architect';
    if (isGuest) return 'Guest Architect';
    return 'Architect Member';
  }

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      fullName: json['full_name']?.toString() ?? 'Sutra User',
      role: json['role']?.toString() ?? 'member',
      orgId: json['org_id']?.toString(),
      isAnonymous: json['is_anonymous'] == true,
      createdAt: json['created_at']?.toString(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'full_name': fullName,
        'role': role,
        'org_id': orgId,
        'is_anonymous': isAnonymous,
        'created_at': createdAt,
      };
}
