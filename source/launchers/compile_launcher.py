"""Publish the modified Lantern UI as a self-contained Atlas launcher."""
import argparse, os, subprocess
from pathlib import Path

def compile_launcher(source:Path, output:Path, dotnet:Path, cache:Path):
    output.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update(DOTNET_CLI_HOME=str(cache/'dotnet-home'),NUGET_PACKAGES=str(cache/'nuget'),
        DOTNET_CLI_TELEMETRY_OPTOUT='1',DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',DOTNET_NOLOGO='1')
    project=source/'launcher/windows/BloodborneLauncher/BloodborneLauncher.csproj'
    with (output/'publish.log').open('wb') as log:
        result=subprocess.run([str(dotnet),'publish',str(project),'-c','Release','-r','win-x64',
            '--self-contained','true','-p:PublishSingleFile=true','-p:IncludeNativeLibrariesForSelfExtract=true',
            '-p:NuGetAudit=false','-p:Version=3.1.0','-o',str(output)],env=env,
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        print((output/'publish.log').read_text(errors='replace')[-7000:]);raise RuntimeError('Atlas launcher publish failed')
    print(output/'HuntersAtlas.exe')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dotnet',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);a=p.parse_args()
    compile_launcher(a.source.resolve(),a.output.resolve(),a.dotnet.resolve(),a.cache.resolve())
