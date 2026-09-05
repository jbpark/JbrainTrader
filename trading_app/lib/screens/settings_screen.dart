import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/trading_provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _hostController;
  late TextEditingController _portController;
  bool _isTesting = false;
  bool? _connectionResult;
  bool _isCheckingApk = false;

  @override
  void initState() {
    super.initState();
    final provider = context.read<TradingProvider>();
    _hostController = TextEditingController(text: provider.serverHost);
    _portController = TextEditingController(text: provider.serverPort.toString());
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('설정', style: TextStyle(fontWeight: FontWeight.bold)),
      ),
      body: Consumer<TradingProvider>(
        builder: (context, provider, _) {
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 서버 연결 설정
              _buildSectionHeader(Icons.dns, '서버 연결 설정'),
              Card(
                color: const Color(0xFF161B22),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      TextField(
                        controller: _hostController,
                        decoration: const InputDecoration(
                          labelText: '서버 IP 주소',
                          hintText: '예: 192.168.0.1',
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.computer),
                        ),
                        style: const TextStyle(color: Colors.white),
                        keyboardType: TextInputType.url,
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _portController,
                        decoration: const InputDecoration(
                          labelText: '포트 번호',
                          hintText: '예: 5000',
                          border: OutlineInputBorder(),
                          prefixIcon: Icon(Icons.numbers),
                        ),
                        style: const TextStyle(color: Colors.white),
                        keyboardType: TextInputType.number,
                      ),
                      const SizedBox(height: 16),

                      // 연결 테스트 결과 표시
                      if (_connectionResult != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            children: [
                              Icon(
                                _connectionResult! ? Icons.check_circle : Icons.error,
                                color: _connectionResult! ? const Color(0xFF00D084) : Colors.redAccent,
                                size: 18,
                              ),
                              const SizedBox(width: 8),
                              Text(
                                _connectionResult! ? '연결 성공!' : '연결 실패 - IP/포트를 확인하세요',
                                style: TextStyle(
                                  color: _connectionResult! ? const Color(0xFF00D084) : Colors.redAccent,
                                  fontSize: 13,
                                ),
                              ),
                            ],
                          ),
                        ),

                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              style: OutlinedButton.styleFrom(
                                foregroundColor: Colors.white70,
                                side: const BorderSide(color: Colors.white30),
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                              onPressed: _isTesting ? null : () => _testConnection(provider),
                              icon: _isTesting
                                  ? const SizedBox(
                                      width: 14, height: 14,
                                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
                                    )
                                  : const Icon(Icons.wifi_find, size: 18),
                              label: const Text('연결 테스트'),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: ElevatedButton.icon(
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF00D084),
                                foregroundColor: Colors.black,
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                              ),
                              onPressed: () => _saveSettings(provider),
                              icon: const Icon(Icons.save, size: 18),
                              label: const Text('저장', style: TextStyle(fontWeight: FontWeight.bold)),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 현재 연결 상태
              _buildSectionHeader(Icons.info_outline, '연결 상태'),
              Card(
                color: const Color(0xFF161B22),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _InfoRow('서버 주소', provider.baseUrl),
                      _InfoRow('연결 상태', provider.isConnected ? '연결됨 ✅' : '연결 안됨 ❌'),
                      _InfoRow('엔진 상태', provider.engineStatus),
                      _InfoRow('등록 종목', '${provider.tickers.length}개'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 앱 정보
              _buildSectionHeader(Icons.info, '앱 정보'),
              Card(
                color: const Color(0xFF161B22),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: const Padding(
                  padding: EdgeInsets.all(16),
                  child: Column(
                    children: [
                      _InfoRow('앱 이름', '자동매매 컨트롤'),
                      _InfoRow('버전', '1.0.0'),
                      _InfoRow('플랫폼', 'Flutter (Windows)'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // 앱 업데이트 (APK 다운로드)
              _buildSectionHeader(Icons.system_update, '앱 업데이트'),
              Card(
                color: const Color(0xFF161B22),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        '서버에 빌드된 최신 APK를 내려받아 앱을 업데이트합니다.',
                        style: TextStyle(color: Colors.grey, fontSize: 13),
                      ),
                      const SizedBox(height: 12),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF238636),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: _isCheckingApk ? null : () => _downloadApk(provider),
                        icon: _isCheckingApk
                            ? const SizedBox(
                                width: 14, height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70),
                              )
                            : const Icon(Icons.android, size: 18),
                        label: const Text('APK 다운로드', style: TextStyle(fontWeight: FontWeight.bold)),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildSectionHeader(IconData icon, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Icon(icon, color: const Color(0xFF00D084), size: 18),
          const SizedBox(width: 8),
          Text(
            title,
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 15,
              color: Colors.white70,
            ),
          ),
        ],
      ),
    );
  }

  // 서버에 빌드된 APK를 확인하고 브라우저로 다운로드한다 (앱 업데이트용).
  Future<void> _downloadApk(TradingProvider provider) async {
    setState(() => _isCheckingApk = true);
    Map<String, dynamic> info;
    try {
      info = await provider.getApkInfo();
    } catch (e) {
      _toast('APK 정보 조회 실패: $e');
      setState(() => _isCheckingApk = false);
      return;
    }
    setState(() => _isCheckingApk = false);
    if (!mounted) return;

    if (info['exists'] != true) {
      _toast('서버에 빌드된 APK가 없습니다. PC에서 flutter build apk로 빌드하세요.');
      return;
    }

    final sizeMb = ((info['size'] ?? 0) as num) / (1024 * 1024);
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        title: const Text('APK 다운로드', style: TextStyle(color: Colors.white)),
        content: Text(
          'jbrain_trader.apk\n'
          '크기: ${sizeMb.toStringAsFixed(1)} MB\n'
          '빌드: ${info['mtime'] ?? '-'}\n\n'
          '브라우저로 다운로드합니다. 설치하면 앱이 업데이트됩니다.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('취소')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('다운로드')),
        ],
      ),
    );
    if (ok != true || !mounted) return;

    final url = '${provider.baseUrl}/apk';
    final launched = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    if (!launched) _toast('브라우저를 열지 못했습니다.');
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _testConnection(TradingProvider provider) async {
    setState(() {
      _isTesting = true;
      _connectionResult = null;
    });

    // 임시로 현재 입력값으로 테스트
    final host = _hostController.text.trim();
    final port = int.tryParse(_portController.text.trim()) ?? provider.serverPort;
    await provider.saveServerSettings(host, port);

    final result = await provider.testConnection();
    setState(() {
      _isTesting = false;
      _connectionResult = result;
    });
  }

  Future<void> _saveSettings(TradingProvider provider) async {
    final host = _hostController.text.trim();
    final port = int.tryParse(_portController.text.trim()) ?? 5000;

    if (host.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('서버 IP를 입력하세요'), backgroundColor: Colors.red),
      );
      return;
    }

    await provider.saveServerSettings(host, port);

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('설정이 저장되었습니다'),
          backgroundColor: Color(0xFF00D084),
        ),
      );
    }
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey, fontSize: 13)),
          Text(value,
              style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
