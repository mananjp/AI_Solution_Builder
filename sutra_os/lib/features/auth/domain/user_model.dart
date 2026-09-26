import '../../../core/network/json_utils.dart';

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
      id: asId(json['id']),
      email: pick(json, ['email'], asString, ''),
      fullName: pick(json, ['full_name', 'name'], asString, 'Sutra User'),
      role: pick(json, ['role'], asString, 'member'),
      orgId: asStringOrNull(json['org_id']),
      isAnonymous: asBool(json['is_anonymous']),
      createdAt: asStringOrNull(json['created_at']),
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
