# Windows 작업 스케줄러 자동화 실전 가이드

이 문서 하나만으로 로그인한 Windows 사용자의 CLI 작업을 **콘솔 창 없이, 매일 반복 가능하고, 중복 실행과 비밀정보 노출을 막으며, 장애 원인을 확인할 수 있게** 구성하는 방법을 설명한다. 특정 프로젝트나 외부 문서를 전제로 하지 않는다.

## 1. 권장 구조

```text
Windows 작업 스케줄러
  -> wscript.exe //B //NoLogo
  -> hidden-launcher.vbs (창 스타일 0, 종료 코드 대기)
  -> powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden
  -> runner.ps1 (절대 경로, 실행 제한, 안전 로그)
  -> 실제 애플리케이션
```

작업 스케줄러에서 `powershell.exe`를 직접 실행하면 로그인된 사용자 화면에 콘솔 창이 뜨거나 잠깐 깜빡일 수 있다. `-WindowStyle Hidden`은 PowerShell이 시작된 뒤 적용되므로 이것만으로는 부족하다. 콘솔 자체가 없는 `wscript.exe`를 첫 프로세스로 사용하고, VBS에서 PowerShell을 창 스타일 `0`으로 시작한다.

권장 디렉터리 구조는 다음과 같다.

```text
C:\Automation\MyJob\
  hidden-launcher.vbs
  runner.ps1
  config.toml
  secrets.env
  state\
  logs\
```

모든 경로는 절대 경로를 사용한다. 작업 스케줄러의 기본 작업 디렉터리와 `PATH`는 대화형 터미널과 다를 수 있다.

## 2. 콘솔 없는 실행기

다음 내용을 `hidden-launcher.vbs`로 저장한다. VBS는 같은 폴더의 `runner.ps1`을 숨김 실행하고 그 종료 코드를 작업 스케줄러에 반환한다.

```vbscript
Option Explicit

Dim shell, fso, baseDir, runner, command, exitCode
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
runner = fso.BuildPath(baseDir, "runner.ps1")

If Not fso.FileExists(runner) Then WScript.Quit 66

command = Chr(34) & _
  fso.BuildPath(shell.ExpandEnvironmentStrings("%SystemRoot%"), _
  "System32\WindowsPowerShell\v1.0\powershell.exe") & Chr(34) & _
  " -NoProfile -NonInteractive -ExecutionPolicy Bypass" & _
  " -WindowStyle Hidden -File " & Chr(34) & runner & Chr(34)

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode
```

작업 스케줄러 action은 다음 형태로 등록한다.

```text
Program:   C:\Windows\System32\wscript.exe
Arguments: //B //NoLogo "C:\Automation\MyJob\hidden-launcher.vbs"
Start in:  C:\Automation\MyJob
```

`//B`는 VBS 오류 대화상자를 막고, `//NoLogo`는 배너 출력을 막는다. `shell.Run(..., 0, True)`의 `0`은 숨김 창, `True`는 자식 프로세스 종료 대기를 뜻한다. 대기하지 않으면 작업 스케줄러가 실제 작업이 끝나기 전에 성공으로 판단한다.

## 3. runner의 최소 안전 골격

다음은 `runner.ps1`의 일반형이다. 실제 애플리케이션 실행 부분만 교체한다.

```powershell
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSCommandPath
$logDir = Join-Path $root "logs"
$logFile = Join-Path $logDir ("job-{0}.jsonl" -f (Get-Date -Format "yyyyMMdd"))
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$exitCode = 70
$status = "launcher_failure"

try {
    # 실제 명령으로 교체한다. 실행 파일과 설정은 절대 경로를 사용한다.
    & "C:\absolute\path\app.exe" run --config (Join-Path $root "config.toml")
    $exitCode = $LASTEXITCODE
    $status = if ($exitCode -eq 0) { "success" } else { "application_failure" }
}
catch {
    $exitCode = 70
    $status = "launcher_failure"
}

[ordered]@{
    timestamp = (Get-Date).ToString("o")
    status = $status
    exitCode = $exitCode
} | ConvertTo-Json -Compress |
    Add-Content -LiteralPath $logFile -Encoding utf8

exit $exitCode
```

로그에는 시각, 상태 분류, 종료 코드, 처리 건수 같은 숫자 요약만 기록한다. 인증값, 환경변수, 원문 데이터, URL, 생성된 메시지, 원본 예외 전체는 기록하지 않는다. 애플리케이션 stdout/stderr에도 민감정보가 포함될 수 있으므로 그대로 파일에 리다이렉트하지 않는다.

## 4. 반복 트리거 설정

매일 08:00부터 22:00까지 30분마다 실행한다면 다음 값을 사용한다.

```text
Trigger type:         CalendarTrigger
DaysInterval:         1
StartBoundary:        오늘 날짜의 08:00:00
EndBoundary:          없음
Repetition Interval:  PT30M
Repetition Duration:  PT14H30M
StopAtDurationEnd:    true
```

반복 시간은 다음 공식으로 계산한다.

```text
Duration = 종료시각 - 시작시각 + 반복간격
         = 22:00 - 08:00 + 00:30
         = 14시간 30분 (PT14H30M)
```

마지막 반복 간격을 더해야 22:00 실행을 포함하고 22:30부터 중단된다. 날짜가 들어간 `EndBoundary`를 설정하면 그 날짜 이후 작업 전체가 만료되므로 일일 자동화에는 두지 않는다.

작업의 핵심 설정은 다음과 같다.

| 설정 | 권장값 | 목적 |
|---|---|---|
| LogonType | `InteractiveToken` | 로그인한 사용자의 CLI 인증 사용 |
| RunLevel | `LeastPrivilege` | 불필요한 관리자 권한 방지 |
| MultipleInstancesPolicy | `IgnoreNew` | 이전 실행이 끝나지 않았으면 새 실행 무시 |
| StartWhenAvailable | `true` | 예약 시각을 놓친 경우 가능한 시점에 실행 |
| RunOnlyIfNetworkAvailable | `true` | 네트워크 작업의 불필요한 실패 방지 |
| WakeToRun | 필요 시 `true` | 절전 상태에서 깨워 실행 |
| ExecutionTimeLimit | 예: `PT15M` | 멈춘 프로세스 강제 종료 |
| RestartOnFailure | `PT5M`, 2회 | 일시적인 네트워크·서비스 장애 대응 |
| 배터리 설정 | 운영 요구에 맞게 명시 | Windows 기본값에 따른 실행 누락 방지 |

`InteractiveToken` 작업은 사용자가 완전히 로그아웃하면 실행되지 않는다. 이를 피하려고 SYSTEM 계정으로 바꾸거나 Windows 암호를 스크립트에 넣으면 사용자 CLI 인증이 사라지고 보안 위험이 커진다. 로그아웃 실행이 필수라면 별도 서비스 계정과 비대화형 인증 구조를 설계해야 한다.

## 5. 안전한 설치 순서

1. 실행 파일, 설정, runner, VBS 실행기가 모두 존재하는지 확인한다.
2. 비밀파일 ACL을 제한한다.
3. 인증과 외부 목적지를 읽기 전용 API로 확인한다.
4. 실제 예약 작업과 같은 처리 건수로 dry-run한다. 전송과 상태 변경은 금지한다.
5. 최초 실행이라면 사람이 승인한 수동 실행으로 중복 방지 상태를 먼저 만든다.
6. 상태가 없는데 과거 데이터를 자동 전송하는 초기 backlog는 별도 명시적 승인을 요구한다.
7. 모든 사전검사가 성공한 뒤에만 작업을 등록하거나 교체한다. 실패하면 기존 작업을 유지한다.
8. 등록된 작업을 다시 읽어 action, trigger, 실행 계정, 제한값을 검증한다.

애플리케이션에도 OS 수준 잠금을 둔다. 작업 스케줄러의 `IgnoreNew`는 같은 예약 작업끼리만 막으므로 사용자가 수동으로 실행한 프로세스와는 겹칠 수 있다. 잠금 획득 실패는 상태를 변경하지 않고 종료해야 한다.

## 6. 비밀파일 ACL

비밀파일은 ACL 상속을 끄고 다음 세 SID에만 `FullControl`을 부여한다.

- 현재 사용자 SID
- SYSTEM: `S-1-5-18`
- Administrators: `S-1-5-32-544`

다음 PowerShell 함수는 접근 권한(DACL) 영역만 수정하므로 반복 실행해도 `SeSecurityPrivilege` 오류를 만들지 않는다.

```powershell
function Protect-SecretFile([string]$Path) {
    $file = [System.IO.FileInfo]::new((Resolve-Path -LiteralPath $Path).Path)
    $section = [System.Security.AccessControl.AccessControlSections]::Access
    $acl = [System.IO.FileSystemAclExtensions]::GetAccessControl($file, $section)
    $acl.SetAccessRuleProtection($true, $false)

    $rules = $acl.GetAccessRules(
        $true, $true, [System.Security.Principal.SecurityIdentifier]
    )
    foreach ($rule in $rules) {
        [void]$acl.RemoveAccessRuleSpecific($rule)
    }

    $current = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $system = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18")
    $admins = [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544")

    foreach ($sid in @($current, $system, $admins)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        [void]$acl.AddAccessRule($rule)
    }
    [System.IO.FileSystemAclExtensions]::SetAccessControl($file, $acl)
}
```

예약 프로세스가 대화형 셸의 환경변수를 상속한다고 가정하지 않는다. 비밀값은 명령 인자로 전달하지 말고, 보호된 로컬 파일을 애플리케이션이 직접 읽게 한다. 토큰을 로그, 채팅, 명령 기록, 프로세스 목록에 노출해서는 안 된다.

## 7. 상태 확인과 장애 진단

외부 도구 없이 기본 명령으로 상태를 확인할 수 있다.

```powershell
$name = "My Scheduled Job"
$task = Get-ScheduledTask -TaskName $name
$info = Get-ScheduledTaskInfo -TaskName $name
[xml]$xml = Export-ScheduledTask -TaskName $name

[pscustomobject]@{
    State = [string]$task.State
    Enabled = $task.Settings.Enabled
    Execute = $task.Actions[0].Execute
    Arguments = $task.Actions[0].Arguments
    NextRunTime = $info.NextRunTime
    LastRunTime = $info.LastRunTime
    LastTaskResult = $info.LastTaskResult
    StartWhenAvailable = $task.Settings.StartWhenAvailable
    NetworkRequired = $task.Settings.RunOnlyIfNetworkAvailable
    WakeToRun = $task.Settings.WakeToRun
    ExecutionTimeLimit = $task.Settings.ExecutionTimeLimit
    RestartCount = $task.Settings.RestartCount
}
```

확인 순서는 `State/Enabled → 다음 실행 시각 → 최근 실행 시각 → LastTaskResult → 최신 안전 로그`다. `LastTaskResult=0`만으로 성공을 단정하지 않는다. 로그 시각이 갱신됐고 기대한 처리 건수와 상태가 기록됐는지도 확인한다. VBS가 runner 시작 전에 실패하면 애플리케이션 로그가 없을 수 있으므로 작업 스케줄러 종료 코드도 반드시 보존한다.

## 8. 자주 발생하는 실패와 해결책

| 증상 | 원인 | 해결책 |
|---|---|---|
| 설치 당일만 실행됨 | 날짜가 있는 `EndBoundary` | 매일 CalendarTrigger, 종료일 제거 |
| 미리보기보다 많은 데이터 처리 | action의 제한 개수 누락 | 사전검사와 runner에 같은 제한값 명시 |
| 예약 실행에서 인증 실패 | 대화형 환경변수 미상속 | 보호된 로컬 인증 파일 직접 로드 |
| 실행 때마다 콘솔 창 표시 | PowerShell 직접 실행 | `wscript.exe` 숨김 실행기 사용 |
| 실패 원인을 알 수 없음 | 출력 폐기, 이벤트 로그 비활성 | 민감정보 없는 JSONL 상태 로그 |
| 최초 실행에서 과거 데이터 대량 처리 | 중복 방지 상태 없음 | 승인된 수동 실행 또는 backlog 명시 승인 |
| 중복 전송·상태 파일 손상 | 예약과 수동 실행이 겹침 | `IgnoreNew`와 OS 잠금 병행 |
| 재설치 때 ACL 권한 오류 | 전체 보안 설명자 재적용 | DACL Access 영역만 멱등 갱신 |
| 작업은 성공인데 로그가 없음 | VBS/runner 시작 전 실패 | VBS 종료 코드를 기다려 그대로 반환 |
| 간헐적으로 영원히 실행 중 | CLI 또는 네트워크 호출 정지 | 실행 제한과 제한된 재시도 설정 |

## 9. 배포 전 체크리스트

- [ ] action이 `wscript.exe //B //NoLogo`를 사용한다.
- [ ] VBS가 창 스타일 `0`으로 실행하고 종료 코드를 기다린다.
- [ ] PowerShell은 `-NoProfile -NonInteractive -WindowStyle Hidden`으로 실행된다.
- [ ] 모든 실행 파일, 설정, 작업 폴더가 절대 경로다.
- [ ] `DaysInterval=1`, 종료일 없음, 반복 간격과 Duration이 의도와 일치한다.
- [ ] 실행 계정과 “로그아웃 시 실행되지 않음” 제약을 운영자가 알고 있다.
- [ ] 네트워크, 절전, 배터리, 재시도, 실행 제한이 명시되어 있다.
- [ ] `IgnoreNew`와 애플리케이션 잠금이 모두 있다.
- [ ] 비밀파일 ACL 함수를 연속 두 번 실행해도 성공한다.
- [ ] 사전검사와 dry-run은 외부 메시지를 보내거나 상태를 변경하지 않는다.
- [ ] 최초 backlog 처리 여부가 사람에게 확인됐다.
- [ ] 상태 확인 시 action, 다음 실행, 최근 결과, 종료 코드, 안전 로그를 함께 본다.
