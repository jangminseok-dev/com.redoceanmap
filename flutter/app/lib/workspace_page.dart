// 주식·상권 워크스페이스 자리. 화면은 아직 없고 진입 경로만 먼저 뚫어둔다.
// www의 /stock · /market에 대응한다.

import 'package:flutter/material.dart';

import 'package:app/theme.dart';

class WorkspacePage extends StatelessWidget {
  const WorkspacePage({
    super.key,
    required this.title,
    required this.description,
  });

  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: Text(title, style: text.titleMedium),
        backgroundColor: AppColors.background,
        surfaceTintColor: Colors.transparent,
        foregroundColor: AppColors.foreground,
        elevation: 0,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(description, style: text.bodyMedium),
              const SizedBox(height: 8),
              Text(
                '아직 만들지 않은 화면입니다.',
                style: text.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
