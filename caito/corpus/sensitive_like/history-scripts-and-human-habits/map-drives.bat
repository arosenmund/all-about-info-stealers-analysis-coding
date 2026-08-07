@echo off
REM map-drives.bat -- logon script on \\contoso.com\netlogon. Inline domain
REM passwords in a batch file readable by every authenticated user.

net use H: \\fileserver02.contoso.com\home /user:CONTOSO\%USERNAME% * /persistent:yes
net use S: \\fileserver02.contoso.com\shared /user:CONTOSO\svc_fileshare Sh@re-Contoso-2026 /persistent:yes
net use P: \\appsrv02.contoso.com\payroll /user:CONTOSO\svc_payroll P@yroll-Contoso-2026! /persistent:no

REM push a scheduled task using an inline password
schtasks /create /s appsrv02.contoso.com /u CONTOSO\svc_deploy /p Contoso!Deploy26 ^
  /tn "SyncJob" /tr "cscript \\contoso.com\netlogon\sync.vbs" /sc daily /st 03:00 /f

REM legacy service install with account password
sc \\appsrv02.contoso.com create SyncSvc binPath= "C:\svc\sync.exe" ^
  obj= "CONTOSO\svc_deploy" password= "Contoso!Deploy26"
