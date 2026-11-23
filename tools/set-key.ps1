# Usage: powershell -ExecutionPolicy Bypass -File tools/set-key.ps1 -Name KIE_API_KEY
param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Z][A-Z0-9_]*$')]
  [string]$Name
)
$cred = Get-Credential -UserName $Name -Message "Paste $Name in the password field"
if (-not $cred) { "cancelled"; exit 1 }
$value = $cred.GetNetworkCredential().Password.Trim().TrimStart([char]0xFEFF).Trim()
if (-not $value) { "empty, nothing saved"; exit 1 }
[Environment]::SetEnvironmentVariable($Name, $value, "User")
Remove-Variable value, cred
"$Name saved as a user environment variable. Close every terminal, then restart Codex."
