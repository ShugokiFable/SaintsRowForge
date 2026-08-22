@echo off
rem Saints Row Forge launcher - status + help, no admin.
setlocal
set FORGE=%~dp0
set PY=python

echo ============================================
echo   SAINTS ROW FORGE
echo ============================================
echo.

%PY% "%FORGE%src\srforge_cli.py" doctor
echo.
echo --------------------------------------------
echo Quickstart:
echo   srforge discover                         find installed games
echo   srforge asset find weapons.xtbl --game sriv --json
echo   srforge xtbl query --file weapons.xtbl --record Pistol-Revolver ^
         --field Ragdoll_Force_Shoot --game sriv
echo   srforge mod new MyMod --game sriv        create a workspace
echo   srforge mod extract^|patch^|diff^|build --workspace <path>
echo.
echo Workspaces: %LOCALAPPDATA%\SaintsRowForge\Workspaces
echo MCP server: %PY% %FORGE%mcp_server\server.py
echo Docs:       README.md  AI-INTEGRATION.md
endlocal
pause
