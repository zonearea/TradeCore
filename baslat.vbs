' TradeCore Terminal — sessiz baslatici (VBScript)
' ------------------------------------------------------------
' Ne yapar?
' 1) FastAPI ve Next.js'i gizli pencerede (WindowStyle=0) baslatir.
' 2) Kisa bir beklemeden sonra dist\TradeCore.exe penceresini acar.
'
' Kullanim:
' - Bu dosyayi masaustune kopyalayip cift tiklayabilirsiniz.
' - Veya proje kokundeki TradeCore.exe / TradeCore.bat ile ayni isi exe kendisi de yapar.
' ------------------------------------------------------------

Option Explicit

Dim shell, fso, root, venvPy, exePath, env

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' VBS hangi klasordeyse proje koku odur (masaustune kopyalanirsa yolu guncelleyin)
root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root

venvPy = root & "\server\.venv\Scripts\python.exe"
exePath = root & "\dist\TradeCore.exe"

If Not fso.FileExists(venvPy) Then
  MsgBox "Sanal ortam bulunamadi:" & vbCrLf & venvPy, vbCritical, "TradeCore"
  WScript.Quit 1
End If

' Process ortamına PYTHONPATH ekle ki `server.main:app` import edilebilsin
Set env = shell.Environment("Process")
env("PYTHONPATH") = root

' 0 = pencere gizli (siyah konsol yok)
shell.Run """" & venvPy & """ -m uvicorn server.main:app --host 127.0.0.1 --port 5080", 0, False
shell.Run "cmd /c cd /d """ & root & "\frontend"" && npm run dev -- -p 3010", 0, False

' Next.js ilk derleme suresi icin kisa bekleme (sn)
WScript.Sleep 8000

If fso.FileExists(exePath) Then
  shell.Run """" & exePath & """", 1, False
Else
  ' exe henuz yoksa ayni venv ile desktop.py'yi konsolsuz calistir
  shell.Run """" & venvPy & """w """ & root & "\desktop.py""", 1, False
End If
