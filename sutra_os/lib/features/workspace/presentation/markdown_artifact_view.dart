import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_text_styles.dart';

/// Dart port of the web app's `MarkdownRenderer`. Same block parsing (fenced
/// code, pipe tables, text groups) and the same heading / quote / list /
/// inline-code / bold / italic treatment, so an artifact reads identically on
/// both platforms instead of as a wall of raw monospace.
class MarkdownArtifactView extends StatelessWidget {
  const MarkdownArtifactView({super.key, required this.content});

  final String content;

  @override
  Widget build(BuildContext context) {
    if (content.trim().isEmpty) return const SizedBox.shrink();
    final blocks = _parseBlocks(content);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < blocks.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: _block(context, blocks[i]),
          ),
      ],
    );
  }

  Widget _block(BuildContext context, _Block block) {
    switch (block.kind) {
      case _BlockKind.code:
        return _CodeBlock(language: block.language, code: block.content);
      case _BlockKind.table:
        return _TableBlock(headers: block.headers, rows: block.rows);
      case _BlockKind.text:
        return _TextGroup(text: block.content);
    }
  }
}

enum _BlockKind { text, code, table }

class _Block {
  _Block.text(this.content)
      : kind = _BlockKind.text,
        language = '',
        headers = const [],
        rows = const [];

  _Block.code(this.language, this.content)
      : kind = _BlockKind.code,
        headers = const [],
        rows = const [];

  _Block.table(this.headers, this.rows)
      : kind = _BlockKind.table,
        content = '',
        language = '';

  final _BlockKind kind;
  final String content;
  final String language;
  final List<String> headers;
  final List<List<String>> rows;
}

/// A GFM separator row is `|---|---|`, `--- | ---` or a bare `---` / `:---:`.
/// It is only consulted when the previous line was a pipe-delimited header,
/// so a lone `---` horizontal rule is never mistaken for one.
bool _isTableSeparator(String line) {
  final t = line.trim();
  if (!t.contains('-')) return false;
  return RegExp(r'^[\s|:-]+$').hasMatch(t);
}

/// Splits the document into fenced-code, table and text runs, in order.
List<_Block> _parseBlocks(String source) {
  final lines = source.split('\n');
  final blocks = <_Block>[];
  final textBuffer = <String>[];

  void flushText() {
    if (textBuffer.isEmpty) return;
    blocks.add(_Block.text(textBuffer.join('\n')));
    textBuffer.clear();
  }

  for (var i = 0; i < lines.length; i++) {
    final line = lines[i];
    final trimmed = line.trim();

    // Fenced code: ```lang ... ```
    if (trimmed.startsWith('```')) {
      final language = trimmed.length > 3 ? trimmed.substring(3).trim() : '';
      final body = <String>[];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        body.add(lines[i]);
        i++;
      }
      flushText();
      blocks.add(_Block.code(language, body.join('\n')));
      continue;
    }

    // Pipe table: a header row followed by a |---|---| separator.
    if (trimmed.startsWith('|') &&
        i + 1 < lines.length &&
        _isTableSeparator(lines[i + 1])) {
      final headers = _splitRow(trimmed);
      i += 2;
      final rows = <List<String>>[];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.add(_splitRow(lines[i].trim()));
        i++;
      }
      // `i` now sits on the first line after the table (or past the end);
      // step back once so the for-loop increment lands on it instead of
      // silently dropping a paragraph.
      i--;
      flushText();
      blocks.add(_Block.table(headers, rows));
      continue;
    }

    textBuffer.add(line);
  }

  flushText();
  return blocks;
}

List<String> _splitRow(String row) {
  var r = row.trim();
  if (r.startsWith('|')) r = r.substring(1);
  if (r.endsWith('|')) r = r.substring(0, r.length - 1);
  return r.split('|').map((c) => c.trim()).toList();
}

class _CodeBlock extends StatelessWidget {
  const _CodeBlock({required this.language, required this.code});

  final String language;
  final String code;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppColors.darkBackground,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.sm,
              vertical: 5,
            ),
            decoration: const BoxDecoration(
              color: AppColors.lightSurfaceSubtle,
              border: Border(bottom: BorderSide(color: AppColors.lightBorder)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    (language.isEmpty ? 'code' : language).toUpperCase(),
                    style: AppTextStyles.smallCapsLabel(
                      fontSize: 9,
                      color: AppColors.lightTextPrimary,
                    ),
                  ),
                ),
                GestureDetector(
                  onTap: () => Clipboard.setData(ClipboardData(text: code)),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.copy,
                        size: 11,
                        color: AppColors.lightTextMuted,
                      ),
                      const SizedBox(width: 3),
                      Text(
                        'COPY',
                        style: AppTextStyles.smallCapsLabel(
                          fontSize: 8,
                          color: AppColors.lightTextMuted,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.all(AppSpacing.sm),
            child: Text(
              code,
              style: AppTextStyles.mono(
                fontSize: 11,
                color: AppColors.darkTextPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TableBlock extends StatelessWidget {
  const _TableBlock({required this.headers, required this.rows});

  final List<String> headers;
  final List<List<String>> rows;

  @override
  Widget build(BuildContext context) {
    if (headers.isEmpty) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: AppColors.lightSurface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusXs),
        border: Border.all(color: AppColors.lightBorder),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                for (final h in headers)
                  Container(
                    constraints: const BoxConstraints(minWidth: 110),
                    padding: const EdgeInsets.all(AppSpacing.sm),
                    color: AppColors.lightSurfaceSubtle,
                    child: _InlineText(h, header: true),
                  ),
              ],
            ),
            for (final row in rows)
              Container(
                decoration: const BoxDecoration(
                  border: Border(
                    top: BorderSide(color: AppColors.lightBorder),
                  ),
                ),
                child: Row(
                  children: [
                    for (var i = 0; i < headers.length; i++)
                      Container(
                        constraints: const BoxConstraints(minWidth: 110),
                        padding: const EdgeInsets.all(AppSpacing.sm),
                        child: _InlineText(
                          i < row.length ? row[i] : '',
                        ),
                      ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _TextGroup extends StatelessWidget {
  const _TextGroup({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final widgets = <Widget>[];
    for (final raw in text.split('\n')) {
      final line = raw.trim();
      if (line.isEmpty) {
        widgets.add(const SizedBox(height: AppSpacing.xs));
        continue;
      }
      if (line.startsWith('#### ')) {
        widgets.add(_heading(line.substring(5), 11, FontWeight.w700, true));
      } else if (line.startsWith('### ')) {
        widgets.add(_heading(line.substring(4), 14, FontWeight.w600, true));
      } else if (line.startsWith('## ')) {
        widgets.add(_SerifDivider(child: _heading(line.substring(3), 17, FontWeight.w400, false)));
      } else if (line.startsWith('# ')) {
        widgets.add(_heading(line.substring(2), 19, FontWeight.w400, false));
      } else if (line.startsWith('> ')) {
        widgets.add(_quote(line.substring(2)));
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        widgets.add(_bullet(line.substring(2)));
      } else {
        final numbered = RegExp(r'^(\d+)\.\s+(.*)$').firstMatch(line);
        if (numbered != null) {
          widgets.add(_numbered(numbered.group(1)!, numbered.group(2)!));
        } else {
          widgets.add(Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: _InlineText(raw),
          ));
        }
      }
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: widgets,
    );
  }

  Widget _heading(
    String value,
    double size,
    FontWeight weight,
    bool uppercase,
  ) {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md, bottom: AppSpacing.xs),
      child: Text(
        uppercase ? value.toUpperCase() : value,
        style: uppercase
            ? AppTextStyles.smallCapsLabel(
                fontSize: size - 2,
                color: AppColors.lightTextPrimary,
                fontWeight: weight,
              )
            : AppTextStyles.serifHeading(fontSize: size),
      ),
    );
  }

  Widget _quote(String value) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: const BoxDecoration(
        color: AppColors.lightSurfaceSubtle,
        border: Border(
          left: BorderSide(color: AppColors.gold, width: 2),
        ),
      ),
      child: _InlineText(
        value,
        italic: true,
        color: AppColors.lightTextSecondary,
      ),
    );
  }

  Widget _bullet(String value) {
    return Padding(
      padding: const EdgeInsets.only(left: 14, top: 2, bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 5, right: 7),
            child: Text('•', style: TextStyle(color: AppColors.gold, fontSize: 12)),
          ),
          Expanded(child: _InlineText(value)),
        ],
      ),
    );
  }

  Widget _numbered(String marker, String value) {
    return Padding(
      padding: const EdgeInsets.only(left: 14, top: 2, bottom: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 18,
            child: Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Text(
                '$marker.',
                style: AppTextStyles.mono(fontSize: 11, color: AppColors.gold),
              ),
            ),
          ),
          Expanded(child: _InlineText(value)),
        ],
      ),
    );
  }
}

/// `## Heading` gets the web view's bottom rule.
class _SerifDivider extends StatelessWidget {
  const _SerifDivider({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.lightBorder)),
      ),
      child: Padding(
        padding: const EdgeInsets.only(top: AppSpacing.md, bottom: AppSpacing.xs),
        child: child,
      ),
    );
  }
}

/// Inline `code`, **bold** and *italic* within one paragraph. A widget rather
/// than a String so a whole wrapped paragraph stays a single text node.
class _InlineText extends StatelessWidget {
  const _InlineText(
    this.source, {
    this.header = false,
    this.italic = false,
    this.color,
  });

  final String source;
  final bool header;
  final bool italic;
  final Color? color;

  static final _token = RegExp(r'(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)');

  @override
  Widget build(BuildContext context) {
    final base = header
        ? AppTextStyles.smallCapsLabel(
            fontSize: 9,
            color: color ?? AppColors.lightTextPrimary,
            fontWeight: FontWeight.w700,
          )
        : AppTextStyles.bodySmall(
            fontSize: 12,
            color: color ?? AppColors.lightTextPrimary,
          ).copyWith(fontStyle: italic ? FontStyle.italic : FontStyle.normal);

    final spans = <TextSpan>[];
    var index = 0;
    for (final match in _token.allMatches(source)) {
      if (match.start > index) {
        spans.add(TextSpan(text: source.substring(index, match.start)));
      }
      final token = match.group(0)!;
      if (token.startsWith('`')) {
        spans.add(TextSpan(
          text: token.substring(1, token.length - 1),
          style: AppTextStyles.mono(
            fontSize: base.fontSize ?? 12,
            color: AppColors.goldDark,
          ),
        ));
      } else if (token.startsWith('**')) {
        spans.add(TextSpan(
          text: token.substring(2, token.length - 2),
          style: base.copyWith(fontWeight: FontWeight.w700),
        ));
      } else {
        spans.add(TextSpan(
          text: token.substring(1, token.length - 1),
          style: base.copyWith(fontStyle: FontStyle.italic),
        ));
      }
      index = match.end;
    }
    if (index < source.length) {
      spans.add(TextSpan(text: source.substring(index)));
    }

    return Text.rich(TextSpan(style: base, children: spans));
  }
}
