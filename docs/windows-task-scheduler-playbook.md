# Windows 작업 스케줄러 자동화 실전 가이드

이 문서는 로그인한 Windows 사용자의 CLI 인증과 로컬 비밀파일을 사용하는 작업을 **콘솔 창 없이, 매일 반복 가능하고, 진단 가능한 형태**로 운영할 때의 기준이다. `x2telegram`에서 실제로 발생한 문제와 해결책을 일반화했다.

## 권장 실행 구조

```text
작업 스케줄러
  -> wscript.exe //B //NoLogo
  -> 숨김 VBS 실행기 (창 스타일 0, 종료 코드 대기)
  -> powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden
  -> 실제 runner (절대 경로, 제한된 입력, 안전 로그)
  -> 애플리케이션
```

`powershell.exe`를 작업 스케줄러에서 직접 실행하면 로그인된 세션에 콘솔 창이 뜨거나 잠깐 깜빡일 수 있다. `-WindowStyle Hidden`만 믿지 말고 콘솔이 없는 `wscript.exe`를 첫 실행기로 사용한다. VBS는 PowerShell 프로세스가 끝날 때까지 기다렸다가 같은 종료 코드를 작업 스케줄러에 반환해야 한다.

## 반드시 지킬 설정

| 영역 | 기준 | 이유 |
|---|---|---|
| 반복 | `CalendarTrigger`, `DaysInterval=1` | 단발성 시간 트리거가 되는 것을 방지 |
| 종료일 | 날짜가 들어간 `EndBoundary`를 두지 않음 | 설치 당일 이후 작업이 영구 중단되는 문제 방지 |
| 시간창 | 반복 `Duration = 종료시각 - 시작시각 + Interval` | 종료시각 실행까지 포함하고 그 뒤에는 중단 |
| 실행 계정 | `InteractiveToken`, `LeastPrivilege` | 로그인된 사용자의 Codex/CLI 인증을 그대로 사용 |
| 중복 실행 | 작업의 `IgnoreNew`와 애플리케이션 OS 잠금을 함께 사용 | 수동 실행과 예약 실행의 동시 상태 변경 방지 |
| 장애 복구 | `StartWhenAvailable`, 네트워크 요구, 5분 간격 2회 재시도 | 절전·네트워크 단절·일시 오류 대응 |
| 실행 제한 | 예: `ExecutionTimeLimit=PT15M` | 멈춘 CLI나 에이전트 프로세스가 계속 남는 것을 방지 |
| 전원 | 배터리 실행 허용 여부와 `WakeToRun`을 제품 요구에 맞게 명시 | Windows 기본값에 의한 누락 방지 |
| 경로 | 실행기·설정·작업 폴더 모두 절대 경로 | 작업 스케줄러의 다른 작업 디렉터리와 PATH 차이 방지 |

`InteractiveToken` 작업은 사용자가 완전히 로그아웃한 상태에서는 실행되지 않는다. 이를 해결하려고 SYSTEM 계정으로 바꾸거나 Windows 암호를 스크립트에 넣으면 사용자 CLI 인증이 사라지고 보안 위험이 커진다. 로그아웃 실행이 정말 필요하면 별도 서비스 계정과 비대화형 인증 구조를 새로 설계한다.

## 안전한 설치 순서

1. 필요한 실행 파일, 설정, runner, 숨김 실행기의 존재를 확인한다.
2. 로컬 비밀파일 권한을 현재 사용자, SYSTEM, Administrators로 제한한다.
3. 읽기 전용 인증·목적지 점검을 실행한다.
4. 실제 예약 범위와 동일한 `count`로 dry-run한다. 이 단계에서는 전송과 상태 변경을 금지한다.
5. 최초 자동화라면 사람이 승인한 수동 실행으로 중복 방지 상태를 먼저 만든다. 상태가 없을 때의 초기 backlog 전송은 별도 명시적 승인을 요구한다.
6. 모든 사전검사가 성공한 뒤에만 기존 작업을 교체한다. 실패하면 기존 작업을 그대로 둔다.
7. 등록 후 XML과 실제 action을 다시 읽어 설정 불변식을 검증한다.

이 프로젝트의 설치 예:

```powershell
.\scripts\install-windows-scheduled-task.ps1 `
  -ProjectRoot (Get-Location).Path `
  -StartTime "08:00" `
  -EndTime "22:00" `
  -IntervalMinutes 30 `
  -Count 10 `
  -Enable
```

## 로그와 진단 원칙

- runner는 날짜별 JSONL 로그에 `timestamp`, 상태 분류, 종료 코드, 제한 개수, 숫자 실행 요약만 기록한다.
- 인증값, 환경변수, 타임라인 원문, URL, 요약문, 원본 예외 전체는 기록하지 않는다.
- 진단은 관리 상태 스크립트, `LastTaskResult`, 안전 로그로 한다. 라이브 작업 action을 임시 명령으로 바꾸지 않는다.
- `LastTaskResult=0`만으로 충분하지 않다. 최신 로그 시각과 다음 실행 시각도 함께 본다.
- 숨김 실행기가 runner 시작 전에 실패하면 안전 로그가 없을 수 있으므로 작업 스케줄러 종료 코드도 유지한다.

```powershell
.\scripts\get-windows-scheduled-task-status.ps1 -ProjectRoot (Get-Location).Path
```

## 비밀파일 ACL 노하우

ACL 보호 스크립트는 반복 실행해도 같은 결과가 나와야 한다. `Get-Acl`/`Set-Acl`로 전체 보안 설명자를 다시 쓰면 이미 보호된 파일에서 SACL까지 건드려 `SeSecurityPrivilege` 오류가 날 수 있다. `.NET FileSystemAclExtensions`로 `AccessControlSections.Access`만 읽고 써서 DACL만 변경한다.

최종 규칙은 상속을 끄고 다음 세 주체에만 `FullControl`을 부여한다.

- 현재 사용자 SID
- SYSTEM (`S-1-5-18`)
- Administrators (`S-1-5-32-544`)

토큰이나 비밀값은 명령 인자, 로그, 채팅, 프로세스 목록에 노출하지 않는다. 예약 프로세스는 대화형 셸의 환경변수를 상속한다고 가정하지 말고, 애플리케이션이 보호된 로컬 env 파일을 직접 로드하게 한다.

## 이번에 확인된 실패 패턴

| 증상 | 원인 | 재발 방지 |
|---|---|---|
| 설치 당일만 실행됨 | 날짜가 있는 `EndBoundary` | 매일 CalendarTrigger, 종료일 없음 |
| 미리보기보다 많은 글 처리 | action에 명시적 count 누락 | 설치·dry-run·runner에 같은 count 고정 |
| 예약 실행에서 X 인증 실패 | 대화형 환경변수 미상속 | 보호된 로컬 인증 파일 자동 로드 |
| 30분마다 콘솔 창 표시 | `powershell.exe` 직접 action | `wscript.exe` 숨김 실행기 사용 |
| 실패 원인을 알 수 없음 | stdout 폐기, 이벤트 로그 비활성 | 민감정보 없는 JSONL 상태 로그 |
| 최초 실행에서 과거 글 대량 전송 | 중복 방지 상태 없음 | 승인된 수동 실행 선행, backlog opt-in |
| 상태 파일 손상 또는 중복 전송 | 동시 실행 | `IgnoreNew` + OS 파일 잠금 |
| 재설치 때 ACL 오류 | 전체 보안 설명자 재적용 | DACL Access 영역만 멱등 갱신 |

## 배포 전 최종 체크리스트

- [ ] action이 `wscript.exe //B //NoLogo`와 저장소의 숨김 실행기를 사용한다.
- [ ] `DaysInterval=1`, 종료일 없음, 반복 간격과 시간창이 의도와 일치한다.
- [ ] runner에 제한 개수가 명시되어 있고 dry-run과 동일하다.
- [ ] 사용자 로그인 필요 여부를 운영자가 알고 있다.
- [ ] 네트워크, 절전, 배터리, 재시도, 실행 제한이 명시되어 있다.
- [ ] 중복 실행 방지 작업 설정과 애플리케이션 잠금이 모두 있다.
- [ ] 비밀파일 ACL 스크립트를 연속 두 번 실행해도 성공한다.
- [ ] 사전검사와 dry-run은 외부 메시지를 보내거나 상태를 변경하지 않는다.
- [ ] 상태 스크립트가 숨김 실행기, 다음 실행, 최근 결과, 안전 로그를 보고한다.

관련 구현은 `scripts/install-windows-scheduled-task.ps1`, `scripts/run-windows-scheduled-task-hidden.vbs`, `scripts/run-windows-scheduled-task.ps1`, `scripts/get-windows-scheduled-task-status.ps1`, `scripts/protect-local-secrets.ps1`을 기준으로 삼는다.
