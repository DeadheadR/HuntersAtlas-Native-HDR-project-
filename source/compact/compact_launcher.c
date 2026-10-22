// SPDX-License-Identifier: GPL-2.0-or-later
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR ignored,int show){
 WCHAR root[32768],python[32768],command[32768];if(!GetModuleFileNameW(NULL,root,32768))return 2;WCHAR* slash=wcsrchr(root,L'\\');if(!slash)return 2;*slash=0;
 const WCHAR* args=GetCommandLineW();if(*args==L'"'){++args;while(*args&&*args!=L'"')++args;if(*args)++args;}else while(*args&&*args!=L' '&&*args!=L'\t')++args;while(*args==L' '||*args==L'\t')++args;
 if(swprintf(python,32768,L"%ls\\runtime\\python\\pythonw.exe",root)<0||swprintf(command,32768,L"\"%ls\" -I -B \"%ls\\owned\\app.py\" %ls",python,root,args)<0)return 2;
 STARTUPINFOW startup={0};startup.cb=sizeof(startup);startup.dwFlags=STARTF_USESHOWWINDOW;startup.wShowWindow=SW_SHOWNORMAL;PROCESS_INFORMATION process;
 if(!CreateProcessW(python,command,NULL,NULL,FALSE,0,NULL,root,&startup,&process)){MessageBoxW(NULL,L"Hunter's Atlas runtime is missing. Extract the complete ZIP again.",L"Hunter's Atlas",MB_OK|MB_ICONERROR);return 2;}
 CloseHandle(process.hThread);WaitForSingleObject(process.hProcess,INFINITE);DWORD result=2;GetExitCodeProcess(process.hProcess,&result);CloseHandle(process.hProcess);return (int)result;
}
