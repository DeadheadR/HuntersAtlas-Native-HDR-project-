param([ValidatePattern('^[a-z0-9_-]+$')][string]$Label='batch03',[string]$RunRoot='')
$taskWorkspace=(Resolve-Path -LiteralPath "$PSScriptRoot\..\..").Path
$taskOcrRoot=if($RunRoot){(Resolve-Path -LiteralPath $RunRoot).Path}else{"$taskWorkspace\.local\atlas2\qa\runs"}
if(!$taskOcrRoot.StartsWith($taskWorkspace+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'OCR paths must remain in this workspace'}
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1)
function Wait-Result($operation,$resultType) {
  $task=$asTask.MakeGenericMethod($resultType).Invoke($null,@($operation))
  $task.Wait(); $task.Result
}
$capture=Get-ChildItem -LiteralPath "$taskOcrRoot\$Label\map-qa\captures" -Filter '*.png' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$file=Wait-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($capture.FullName)) ([Windows.Storage.StorageFile])
$stream=Wait-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder=Wait-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap=Wait-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$result=Wait-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
$result.Text | Set-Content -LiteralPath "$taskOcrRoot\$Label\private-ocr.txt"
$terms=@('continue','new game','load game','press','online','offline','ok','network','confirm','start','settings','data','agreement','corrupt','failed','error','you died','loading')
$found=@($terms | Where-Object {$result.Text -match [regex]::Escape($_)})
@{recognized_length=$result.Text.Length;generic_terms=$found;languages=@($engine.RecognizerLanguage.LanguageTag)} | ConvertTo-Json -Compress
