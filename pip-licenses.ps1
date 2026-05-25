# PowerShell -NoProfile -ExecutionPolicy Bypass -Command ".\pip-licenses.ps1"

# 除外したいもの（必要に応じて増減）
$exclude = @(
  "pyinstaller",
  "pyinstaller-hooks-contrib",
  "altgraph",
  "pefile",
  "pywin32-ctypes",
  "packaging",
  "pipdeptree"
) | ForEach-Object { $_.ToLowerInvariant() }

function Norm([string]$n) {
  if ([string]::IsNullOrWhiteSpace($n)) { return "" }
  return (($n -replace "_","-").ToLowerInvariant())
}

function Get-LicenseBody([string]$path) {
  if ([string]::IsNullOrWhiteSpace($path) -or !(Test-Path -LiteralPath $path)) { return "-" }
  try { (Get-Content -LiteralPath $path -Raw -ErrorAction Stop).TrimEnd() }
  catch { "(failed to read: $path)" }
}

$all = pip-licenses --format=json --with-urls --with-license-file | Out-String | ConvertFrom-Json

# 除外が効いてるか確認したい場合（任意）
# $all | Select-Object Name | ForEach-Object { Norm $_.Name } | Sort-Object -Unique | Where-Object { $_ -like "pyinstaller*" }

$pkgs = $all |
  Where-Object { $exclude -notcontains (Norm $_.Name) } |
  Sort-Object Name

$lines = foreach ($p in $pkgs) {
  $body = Get-LicenseBody $p.LicenseFile
  $indented = ($body -split "`r?`n" | ForEach-Object { "  $_" }) -join "`r`n"

  @(
    "Package: $($p.Name)"
    "Version: $($p.Version)"
    "License: $($p.License)"
    "URL: " + ($(if ($p.URL) { $p.URL } else { "-" }))
    "LicenseFile:"
    $indented
    ""
  )
}

$lines | Set-Content .\THIRD_PARTY_NOTICES.txt -Encoding utf8