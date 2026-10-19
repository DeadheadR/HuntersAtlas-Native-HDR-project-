param([ValidatePattern('^[a-z0-9_-]+$')][string]$Label='batch03',[string]$RunRoot='')
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
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
$taskDeathRu = -join (0x432,0x44B,0x20,0x43F,0x43E,0x433,0x438,0x431,0x43B,0x438 | ForEach-Object { [char]$_ })
$terms=@('continue','new game','load game','press','online','offline','ok','network','confirm','start','settings','data','agreement','corrupt','failed','error','you died',$taskDeathRu,'loading')
$found=@($terms | Where-Object {$result.Text -match [regex]::Escape($_)})
@{recognized_length=$result.Text.Length;generic_terms=$found;languages=@($engine.RecognizerLanguage.LanguageTag)} | ConvertTo-Json -Compress
