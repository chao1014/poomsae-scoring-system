@echo off
set retry=0
:loop
ping 127.0.0.1 -n 2 > nul
echo test copy
if %errorlevel% equ 0 goto success
set /a retry+=1
if %retry% geq 10 goto success
goto loop

:success
echo success
