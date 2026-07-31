// 홈 화면 — www의 `app/(seoul)/page.tsx` 구성을 네이티브로 옮긴 것.
// 인사말 → 헤드라인 → 데이터 요약 → 채팅 입력 → 퀵 칩 → 워크스페이스 카드 → 1위 상권 리스트.

import 'package:flutter/material.dart';

import 'package:app/api.dart';
import 'package:app/format.dart';
import 'package:app/stopwatch_page.dart';
import 'package:app/theme.dart';
import 'package:app/workspace_page.dart';

/// www의 quickChips와 같은 문구·프롬프트
const _quickChips = [
  (Icons.storefront_outlined, '업종으로 찾기', '어떤 업종이 잘 될까요?'),
  (Icons.account_balance_wallet_outlined, '예산으로 찾기',
      '3000만원으로 시작할 수 있는 곳 알려주세요'),
  (Icons.place_outlined, '동네로 찾기', '성수동 상권 어때요?'),
  (Icons.bar_chart, '상권 비교', '성수동이랑 연남동 비교해주세요'),
  (Icons.auto_awesome_outlined, '추천받기', '지금 가장 핫한 동네 추천해주세요'),
  (Icons.trending_up, '주식 물어보기', '삼성전자 주가 어때요?'),
];

/// www의 workspaceCards
const _workspaceCards = [
  (Icons.candlestick_chart_outlined, '주식 분석', '캔들차트 · 지표 · 뉴스 · 펀더멘털'),
  (Icons.map_outlined, '상권 분석', '지도 · 매출 추이 · 유동인구 · 점포'),
];

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late Future<Showcase> _future = fetchShowcase();
  final _promptController = TextEditingController();

  bool _asking = false;
  String? _answer;
  String? _chatError;

  @override
  void dispose() {
    _promptController.dispose();
    super.dispose();
  }

  void _reload() => setState(() => _future = fetchShowcase());

  Future<void> _send(String prompt) async {
    if (prompt.trim().isEmpty || _asking) return;
    _promptController.text = prompt;
    setState(() {
      _asking = true;
      _answer = null;
      _chatError = null;
    });
    try {
      final result = await askChat(prompt);
      if (!mounted) return;
      setState(() => _answer = result.answer);
    } on ApiException catch (e) {
      if (!mounted) return;
      // 401이면 백엔드가 주는 "인증이 필요합니다."가 그대로 보인다.
      setState(() => _chatError = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _chatError = '$e');
    } finally {
      if (mounted) setState(() => _asking = false);
    }
  }

  void _openWorkspace(String title, String description) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => WorkspacePage(title: title, description: description),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: FutureBuilder<Showcase>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(
                child: CircularProgressIndicator(color: AppColors.brand),
              );
            }
            if (snapshot.hasError) {
              return _ErrorView(error: '${snapshot.error}', onRetry: _reload);
            }
            final showcase = snapshot.data!;
            return RefreshIndicator(
              color: AppColors.brand,
              onRefresh: () async => _reload(),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(24, 32, 24, 40),
                children: [
                  _Hero(showcase: showcase),
                  const SizedBox(height: 24),
                  _ChatInput(
                    controller: _promptController,
                    disabled: _asking,
                    onSubmit: _send,
                  ),
                  if (_asking) ...[
                    const SizedBox(height: 12),
                    Text(
                      '분석 중이에요…',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  if (_answer != null) ...[
                    const SizedBox(height: 12),
                    _AnswerBox(text: _answer!),
                  ],
                  if (_chatError != null) ...[
                    const SizedBox(height: 12),
                    _ChatErrorBox(message: _chatError!),
                  ],
                  const SizedBox(height: 16),
                  _QuickChips(disabled: _asking, onTap: _send),
                  const SizedBox(height: 24),
                  for (final (icon, title, desc) in _workspaceCards) ...[
                    _WorkspaceCard(
                      icon: icon,
                      title: title,
                      description: desc,
                      onTap: () => _openWorkspace(title, desc),
                    ),
                    const SizedBox(height: 12),
                  ],
                  _WorkspaceCard(
                    icon: Icons.timer_outlined,
                    title: '스톱워치',
                    description: '랩 기록 · 최장·최단 랩 표시',
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const StopwatchPage(),
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  const _SectionTitle('자치구별 점포당 매출 1위 상권'),
                  const SizedBox(height: 4),
                  Text(
                    '${formatQuarter(showcase.yearQuarter)} 집계 · 점포 10개 이상',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 16),
                  for (var i = 0; i < showcase.rows.length; i++) ...[
                    _AreaCard(row: showcase.rows[i], rank: i + 1),
                    if (i != showcase.rows.length - 1)
                      const SizedBox(height: 12),
                  ],
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

/// www 홈 상단 — 인사말 + 헤드라인 + 보유 데이터 한 줄
class _Hero extends StatelessWidget {
  const _Hero({required this.showcase});

  final Showcase showcase;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(greetingFor(DateTime.now().hour), style: text.bodySmall),
        const SizedBox(height: 12),
        Text.rich(
          TextSpan(
            children: [
              const TextSpan(text: '상권과 주식,\n'),
              const TextSpan(
                text: '지금 상황',
                style: TextStyle(color: AppColors.brand),
              ),
              const TextSpan(text: '을 빠르게 읽어드릴게요'),
            ],
          ),
          style: text.displaySmall,
        ),
        const SizedBox(height: 16),
        Text(
          '서울 상권 ${formatCount(showcase.areaCount)}곳 · '
          '${formatQuarter(showcase.quarterFrom)}부터 '
          '${formatQuarter(showcase.yearQuarter)}까지 매출·점포 데이터',
          style: text.bodySmall,
        ),
      ],
    );
  }
}

/// www의 ChatInput — 입력 + 엔진 라벨 + 전송 버튼
class _ChatInput extends StatelessWidget {
  const _ChatInput({
    required this.controller,
    required this.disabled,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final bool disabled;
  final void Function(String) onSubmit;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: cardDecoration,
      padding: const EdgeInsets.fromLTRB(16, 8, 12, 8),
      child: Column(
        children: [
          TextField(
            controller: controller,
            enabled: !disabled,
            minLines: 1,
            maxLines: 4,
            textInputAction: TextInputAction.send,
            onSubmitted: onSubmit,
            decoration: InputDecoration(
              border: InputBorder.none,
              hintText: '예산이랑 하고 싶은 업종을 알려주세요',
              hintStyle: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          Row(
            children: [
              Text('ROM 1.0', style: Theme.of(context).textTheme.bodySmall),
              const Spacer(),
              IconButton(
                onPressed: disabled ? null : () => onSubmit(controller.text),
                icon: const Icon(Icons.arrow_forward),
                color: AppColors.brand,
                tooltip: '보내기',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AnswerBox extends StatelessWidget {
  const _AnswerBox({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: cardDecoration,
      padding: const EdgeInsets.all(16),
      child: Text(text, style: Theme.of(context).textTheme.bodyMedium),
    );
  }
}

class _ChatErrorBox extends StatelessWidget {
  const _ChatErrorBox({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.brand.withValues(alpha: 0.06),
        border: Border.all(color: AppColors.brand.withValues(alpha: 0.25)),
        borderRadius: BorderRadius.circular(AppRadius.card),
      ),
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          const Icon(Icons.lock_outline, size: 18, color: AppColors.brand),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(fontSize: 13, color: AppColors.brandDeep),
            ),
          ),
        ],
      ),
    );
  }
}

/// www의 rounded-full 칩
class _QuickChips extends StatelessWidget {
  const _QuickChips({required this.disabled, required this.onTap});

  final bool disabled;
  final void Function(String) onTap;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: [
        for (final (icon, label, prompt) in _quickChips)
          OutlinedButton.icon(
            onPressed: disabled ? null : () => onTap(prompt),
            icon: Icon(icon, size: 15, color: AppColors.brand),
            label: Text(label),
            style: OutlinedButton.styleFrom(
              foregroundColor: AppColors.foreground,
              backgroundColor: AppColors.surface,
              side: const BorderSide(color: AppColors.border),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              shape: const StadiumBorder(),
              textStyle: const TextStyle(fontSize: 13),
            ),
          ),
      ],
    );
  }
}

/// www의 워크스페이스 카드 — 아이콘 박스 + 제목 + 설명 + 화살표
class _WorkspaceCard extends StatelessWidget {
  const _WorkspaceCard({
    required this.icon,
    required this.title,
    required this.description,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String description;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(AppRadius.card),
      child: Container(
        decoration: cardDecoration,
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.brand.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(AppRadius.icon),
              ),
              child: Icon(icon, size: 20, color: AppColors.brand),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(title, style: text.titleMedium),
                      const SizedBox(width: 4),
                      const Icon(Icons.north_east,
                          size: 14, color: AppColors.foregroundMuted),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(description, style: text.bodySmall),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);

  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(Icons.trending_up, size: 18, color: AppColors.brand),
        const SizedBox(width: 8),
        Text(
          title,
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

/// www의 `bg-surface border border-border rounded-xl p-4` 카드
class _AreaCard extends StatelessWidget {
  const _AreaCard({required this.row, required this.rank});

  final ShowcaseRow row;
  final int rank;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    return Container(
      decoration: cardDecoration,
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: AppColors.brand.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(AppRadius.icon),
            ),
            child: Text(
              '$rank',
              style: const TextStyle(
                color: AppColors.brand,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  row.trdarName,
                  style: text.titleMedium,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  '${row.districtName} · ${row.divisionName}',
                  style: text.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                formatEok(row.salesPerStore),
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: AppColors.brandDeep,
                ),
              ),
              const SizedBox(height: 2),
              Text('점포 ${formatCount(row.storeCount)}개',
                  style: text.bodySmall),
            ],
          ),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.error, required this.onRetry});

  final String error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.cloud_off, size: 48, color: AppColors.foregroundMuted),
          const SizedBox(height: 12),
          Text('불러오지 못했습니다\n$error', textAlign: TextAlign.center),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: onRetry,
            style: FilledButton.styleFrom(backgroundColor: AppColors.brand),
            child: const Text('다시 시도'),
          ),
        ],
      ),
    );
  }
}
