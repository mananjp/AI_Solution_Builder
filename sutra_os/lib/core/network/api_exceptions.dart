import 'package:dio/dio.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;
  final bool isColdStart;

  ApiException({
    required this.message,
    this.statusCode,
    this.data,
    this.isColdStart = false,
  });

  factory ApiException.fromDioException(DioException dioException) {
    switch (dioException.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiException(
          message: 'Connection timed out. The server may be warming up from cold sleep (Render free tier). Please try again in a few moments.',
          statusCode: null,
          isColdStart: true,
        );

      case DioExceptionType.badResponse:
        final response = dioException.response;
        final statusCode = response?.statusCode;
        String errorMessage = 'Server error ($statusCode)';

        if (response?.data is Map) {
          final data = response!.data as Map;
          if (data['detail'] is String) {
            errorMessage = data['detail'];
          } else if (data['detail'] is List) {
            final details = data['detail'] as List;
            if (details.isNotEmpty && details.first is Map) {
              errorMessage = details.first['msg'] ?? errorMessage;
            }
          } else if (data['message'] is String) {
            errorMessage = data['message'];
          }
        }

        if (statusCode == 401) {
          return ApiException(
            message: 'Session expired or unauthenticated. Please sign in.',
            statusCode: 401,
            data: response?.data,
          );
        } else if (statusCode == 403) {
          return ApiException(
            message: 'Access forbidden. You do not have permission for this resource.',
            statusCode: 403,
            data: response?.data,
          );
        } else if (statusCode == 404) {
          return ApiException(
            message: 'Requested resource not found.',
            statusCode: 404,
            data: response?.data,
          );
        } else if (statusCode == 422) {
          return ApiException(
            message: errorMessage.isNotEmpty ? errorMessage : 'Validation error. Please verify input fields.',
            statusCode: 422,
            data: response?.data,
          );
        }

        return ApiException(
          message: errorMessage,
          statusCode: statusCode,
          data: response?.data,
        );

      case DioExceptionType.connectionError:
        return ApiException(
          message: 'Unable to reach Sutra OS backend. Check internet connection or wait for Render cold-boot.',
          statusCode: null,
          isColdStart: true,
        );

      case DioExceptionType.cancel:
        return ApiException(
          message: 'Request was cancelled.',
          statusCode: null,
        );

      case DioExceptionType.badCertificate:
        return ApiException(
          message: 'SSL Certificate error. Strict HTTPS failed.',
          statusCode: null,
        );

      case DioExceptionType.unknown:
      default:
        return ApiException(
          message: dioException.message ?? 'An unexpected network error occurred.',
          statusCode: null,
        );
    }
  }

  @override
  String toString() => message;
}
