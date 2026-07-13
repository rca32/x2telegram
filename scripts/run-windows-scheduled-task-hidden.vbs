Option Explicit

Dim shell, fileSystem, scriptDirectory, projectRoot
Dim runnerPath, configPath, powerShellPath
Dim count, validateOnly, index, argument, command, exitCode

count = 10
validateOnly = False

For index = 0 To WScript.Arguments.Count - 1
    argument = LCase(CStr(WScript.Arguments(index)))
    If argument = "-validateonly" Then
        validateOnly = True
    ElseIf argument = "-count" Then
        If index + 1 >= WScript.Arguments.Count Then
            WScript.Quit 64
        End If
        count = WScript.Arguments(index + 1)
    End If
Next

If Not IsNumeric(count) Then
    WScript.Quit 64
End If
count = CLng(count)
If count < 1 Or count > 1000 Then
    WScript.Quit 64
End If

Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
scriptDirectory = fileSystem.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fileSystem.GetParentFolderName(scriptDirectory)
runnerPath = fileSystem.BuildPath(scriptDirectory, "run-windows-scheduled-task.ps1")
configPath = fileSystem.BuildPath(projectRoot, "config.toml")
powerShellPath = fileSystem.BuildPath(shell.ExpandEnvironmentStrings("%SystemRoot%"), "System32\WindowsPowerShell\v1.0\powershell.exe")

If Not fileSystem.FileExists(runnerPath) Then
    WScript.Quit 66
End If
If Not fileSystem.FileExists(configPath) Then
    WScript.Quit 66
End If
If Not fileSystem.FileExists(powerShellPath) Then
    WScript.Quit 69
End If

If validateOnly Then
    WScript.Quit 0
End If

command = QuoteArgument(powerShellPath) & _
    " -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File " & _
    QuoteArgument(runnerPath) & " -ProjectRoot " & QuoteArgument(projectRoot) & _
    " -ConfigPath " & QuoteArgument(configPath) & " -Count " & CStr(count)

exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArgument(value)
    QuoteArgument = Chr(34) & CStr(value) & Chr(34)
End Function
