import 'package:flutter/material.dart';

import 'package:app/intro_page.dart';
import 'package:app/theme.dart';

void main() => runApp(const RedoceanmapApp());

class RedoceanmapApp extends StatelessWidget {
  const RedoceanmapApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'redoceanmap',
      theme: buildAppTheme(),
      home: const IntroPage(),
    );
  }
}
