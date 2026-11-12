$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$PdfPath = $env:DSH_PDF_IN
$OutPng  = $env:DSH_PNG_OUT
if (-not $PdfPath -or -not $OutPng) { throw "env DSH_PDF_IN / DSH_PNG_OUT required" }
$Scale = if ($env:DSH_SCALE) { [double]$env:DSH_SCALE } else { 1.0 }

$ext = [System.WindowsRuntimeSystemExtensions]
$asTaskOp = ($ext.GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
$asTaskAct = ($ext.GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
    })[0]

function AwaitOp($op, $t) {
    $nt = $asTaskOp.MakeGenericMethod($t).Invoke($null, @($op))
    $nt.Wait(-1) | Out-Null
    $nt.Result
}
function AwaitAct($act) {
    $nt = $asTaskAct.Invoke($null, @($act))
    $nt.Wait(-1) | Out-Null
}

[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

$file = AwaitOp ([Windows.Storage.StorageFile]::GetFileFromPathAsync($PdfPath)) ([Windows.Storage.StorageFile])
$doc = AwaitOp ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
Write-Output ("pages={0}" -f $doc.PageCount)
$page = $doc.GetPage(0)
$opts = New-Object Windows.Data.Pdf.PdfPageRenderOptions
$opts.DestinationWidth = [uint32][math]::Round($page.Size.Width * $Scale)
$opts.DestinationHeight = [uint32][math]::Round($page.Size.Height * $Scale)
Write-Output ("size={0}x{1} -> {2}x{3}" -f $page.Size.Width, $page.Size.Height, $opts.DestinationWidth, $opts.DestinationHeight)

$stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
AwaitAct ($page.RenderToStreamAsync($stream, $opts))
$size = [int]$stream.Size
$stream.Seek(0)
$reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
AwaitOp ($reader.LoadAsync([uint32]$size)) ([uint32]) | Out-Null
$bytes = New-Object byte[] $size
$reader.ReadBytes($bytes)
[System.IO.File]::WriteAllBytes($OutPng, $bytes)
$reader.Dispose(); $stream.Dispose()
Write-Output ("OK {0} {1} bytes" -f $OutPng, $bytes.Length)
