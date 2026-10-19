Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\Engineering_Projects\02_tools\youtube_video-summarize_automation"
WshShell.Run "cmd.exe /c start_server.bat", 0, False
