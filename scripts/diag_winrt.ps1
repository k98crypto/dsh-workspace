$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$ext = [System.WindowsRuntimeSystemExtensions]
$asTaskOp = ($ext.GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null

$p = $env:DSH_PDF_IN
Write-Output ("path = " + $p + "  len=" + $p.Length)
function Step($name, $scriptblock) {
    try { Write-Output ("[$name] " + (& $scriptblock)) }
    catch {
        Write-Output "[$name] FAILED: " + $_.Exception.Message
        $e = $_.Exception; $d = 0
        while ($e -and $d -lt 6) { Write-Output ("   [$d] " + $e.GetType().FullName + " :: " + $e.Message); $e = $e.InnerException; $d++ }
    }
}
$file = $null
Step "GetFile" {
    $op = [Windows.Storage.StorageFile]::GetFileFromPathAsync($p)
    $nt = $asTaskOp.MakeGenericMethod([Windows.Storage.StorageFile]).Invoke($null, @($op))
    $nt.Wait(-1) | Out-Null
    $script:file = $nt.Result
    "ok " + $nt.Result.Path
}
Step "Load" {
    $op = [Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($script:file)
    $nt = $asTaskOp.MakeGenericMethod([Windows.Data.Pdf.PdfDocument]).Invoke($null, @($op))
    $nt.Wait(-1) | Out-Null
    $script:doc = $nt.Result
    "ok pages=" + $nt.Result.PageCount
}
