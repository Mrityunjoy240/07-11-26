$python = 'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\venv\Scripts\python.exe'
$workdir = 'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend'
$logfile = "$workdir\server_err.log"
$args = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8001', '--log-level', 'info')
Start-Process -NoNewWindow -FilePath $python -ArgumentList $args -WorkingDirectory $workdir -RedirectStandardOutput 'NUL' -RedirectStandardError $logfile
