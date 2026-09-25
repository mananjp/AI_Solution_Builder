import 'package:dio/dio.dart';

void main() async {
  print('==================================================');
  print('SUTRA OS: LIVE BACKEND CONNECTIVITY CHECK');
  print('Target: https://ai-solution-builder.onrender.com');
  print('==================================================');

  final dio = Dio(
    BaseOptions(
      baseUrl: 'https://ai-solution-builder.onrender.com',
      connectTimeout: const Duration(seconds: 65),
      receiveTimeout: const Duration(seconds: 65),
    ),
  );

  final stopwatch = Stopwatch()..start();

  try {
    print('\n[1/3] Probing health endpoint (/health)...');
    final healthRes = await dio.get('/health');
    print('  Status: ${healthRes.statusCode}');
    print('  Response: ${healthRes.data}');

    print('\n[2/3] Fetching OpenAPI schema (/openapi.json)...');
    final openapiRes = await dio.get('/openapi.json');
    print('  Status: ${openapiRes.statusCode}');
    final info = openapiRes.data['info'];
    print('  API Title: ${info?['title']}');
    print('  API Version: ${info?['version']}');
    final paths = (openapiRes.data['paths'] as Map?)?.keys.length ?? 0;
    print('  Discovered Paths Count: $paths');

    print('\n[3/3] Checking Auth Providers (/api/v1/auth/providers)...');
    final providersRes = await dio.get('/api/v1/auth/providers');
    print('  Status: ${providersRes.statusCode}');
    print('  Response: ${providersRes.data}');

    stopwatch.stop();
    print('\n==================================================');
    print('SUCCESS: Live Render backend reached in ${stopwatch.elapsedMilliseconds}ms!');
    print('==================================================');
  } catch (e) {
    stopwatch.stop();
    print('\nFAILED: $e in ${stopwatch.elapsedMilliseconds}ms');
  }
}
