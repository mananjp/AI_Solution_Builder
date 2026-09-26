import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

/// Writes a downloaded artifact to disk and hands it to the Android share
/// sheet, which is how a user actually gets a build archive out of the app.
///
/// Previously the billing invoice dialog and nothing else claimed a file had
/// been "saved to Downloads" without writing a byte.
class FileDelivery {
    /// Saves [bytes] under [fileName] and returns the absolute path. Throws if
    /// the write fails.
    static Future<String> save(Uint8List bytes, String fileName) async {
      // Existence of /storage/emulated/0/Download says nothing about whether we
      // may write there: on Android 10+ scoped storage rejects the write even
      // though the folder shows up in a directory listing. So try it, and fall
      // back to app storage on an actual permission failure.
      if (Platform.isAndroid) {
        final shared = Directory('/storage/emulated/0/Download');
        if (await shared.exists()) {
          try {
            final file = File('${shared.path}/$fileName');
            await file.writeAsBytes(bytes, flush: true);
            return file.path;
          } catch (_) {
            // Fall through to app-private storage.
          }
        }
      }
      final dir = await _appDirectory();
      final file = File('${dir.path}/$fileName');
      await file.writeAsBytes(bytes, flush: true);
      return file.path;
    }

  static Future<Directory> _appDirectory() async {
    final docs = await getApplicationDocumentsDirectory();
    return Directory('${docs.path}/downloads')..createSync(recursive: true);
  }

  /// Saves then opens the system share sheet so the user can send the file
  /// somewhere (Drive, Slack, Files).
  static Future<void> saveAndShare(
    Uint8List bytes,
    String fileName, {
    String? subject,
  }) async {
    final path = await save(bytes, fileName);
    await Share.shareXFiles(
      [XFile(path)],
      subject: subject,
    );
  }
}


