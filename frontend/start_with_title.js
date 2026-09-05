import { spawn } from 'child_process';
import os from 'os';

// 콘솔 타이틀 설정 함수
const setTitle = () => {
    process.stdout.write('\x1b]0;Vue Frontend\x07');
};

// 최초 설정
setTitle();

// Vite가 타이틀을 변경하는 것에 대비하여 주기적으로 재설정
setInterval(setTitle, 1000);

// Windows 환경에서 npm 명령어 처리
const npmCmd = os.platform() === 'win32' ? 'npm.cmd' : 'npm';

console.log(`[*] Starting Vite via ${npmCmd}...`);

const vite = spawn(npmCmd, ['run', 'dev', '--', '--force'], {
    stdio: 'inherit',
    shell: true
});

vite.on('error', (err) => {
    console.error('Failed to start Vite:', err);
});

vite.on('close', (code) => {
    console.log(`[*] Vite process exited with code ${code}`);
    process.exit(code);
});
