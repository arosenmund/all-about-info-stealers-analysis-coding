<#
    deploy-backup.ps1  — the classic "hardcoded creds in an ops script" find.
    Lives in share roots, C:\Scripts, scheduled-task action paths, git repos.
#>

$ErrorActionPreference = 'Stop'

# --- hardcoded service credentials ---------------------------------------
$SqlUser = 'sa'
$SqlPass = 'S3rver-SQL-2026#Payroll'
$SmtpUser = 'noreply@example.com'
$SmtpPass = 'Sm7p-Relay-2026!'
$ApiToken = 'ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789'

# mapped drive using an inline domain credential
net use \\fileserver01.example.com\backups /user:EXAMPLE\svc_backup 'W1nt3r-Backup-2026!' | Out-Null

$secure = ConvertTo-SecureString $SqlPass -AsPlainText -Force
$cred   = New-Object System.Management.Automation.PSCredential("EXAMPLE\svc_sql", $secure)

Invoke-Sqlcmd -ServerInstance 'sqlprod01.example.com' -Username $SqlUser -Password $SqlPass `
    -Query "BACKUP DATABASE Payroll TO DISK='\\fileserver01.example.com\backups\payroll.bak'"

Send-MailMessage -SmtpServer smtp.example.com -Port 587 -UseSsl `
    -Credential (New-Object PSCredential($SmtpUser, (ConvertTo-SecureString $SmtpPass -AsPlainText -Force))) `
    -From $SmtpUser -To 'ops@example.com' -Subject 'Backup complete' -Body 'OK'
